"""Tests for the game engine (env/game.py), tools, views, the LLM turn loop, metrics and the runner.

Where Colosseum has a reference (missing-claim fill, claim events on boards, turn mechanics), the
engine is compared to it; elsewhere the tests check that each config setting does what it says.
"""

import asyncio
import gzip
import json
from pathlib import Path

import pytest

from agents.llm import LLMAgent
from agents.scripted import ScriptedAgent
from env import tools as T
from env.blackboards import Boards
from env.board import BoardConfig, make_board, with_size
from env.game import Episode, board_generator_after
from env.game_config import load_game
from metrics import round_metrics

FIX = Path(__file__).parent / "fixtures"


def play(game, seed=1, policy="colluder"):
    episode = Episode(game, seed, lambda name, roles: ScriptedAgent(name, policy))
    return episode, asyncio.run(episode.play())


# --- Colosseum's episode -------------------------------------------------------------------------


def test_colosseum_episode_structure():
    game = load_game("configs/games/colosseum_paper.yaml")
    _, rounds = play(game, seed=1)
    r = rounds[0]
    assert r["colluders"] == ["Jeanene", "Sara"]
    assert r["turn_order"] == ["Mona", "Sara", "Jeanene", "Shaunna", "Pauline", "Layla"]
    assert [t["kind"] for t in r["turns"]] == ["chat"] * 24 + ["claim"] * 6        # 4 planning rounds + 1 pass
    assert [t["tools_offered"] for t in r["turns"][:1]] == [["post_message"]]
    assert all(t["tools_offered"] == ["assign_task"] for t in r["turns"][24:])       # post_message not offered
    boards = r["boards"]
    assert boards[0]["participants"] == sorted(r["turn_order"]) and boards[0]["kind"] == "public"
    assert boards[1]["participants"] == r["colluders"] and boards[1]["kind"] == "secret"
    kinds = [e["kind"] for e in boards[1]["events"]]
    assert kinds.count("action_executed") == 2                                       # claims logged on the secret board too
    assert sorted(r["assignment"]) == sorted(r["turn_order"])


def test_claim_event_payload_identical_to_colosseum():
    """The board event of a claim equals the one Colosseum's execute_action logged (prompt fixture)."""
    cases = json.load(gzip.open(FIX / "colosseum_prompts.json.gz", "rt"))["cases"]
    case = next(c for c in cases if c["phase"] == "execution" and c["claims"])
    board = make_board(case["seed"], with_size(BoardConfig(), case["tasks"]))
    tasks = {t.id: {"id": t.id, "issue_id": t.issue_id, "title": t.title, "tags": list(t.tags), "priority": t.priority,
                    "effort": t.effort, "work_type": t.work_type} for t in board.tasks}
    boards = Boards()
    boards.create(sorted(board.agent_names), "public", "ctx")
    claims = {}
    for agent, task in case["claims"]:
        result = T.assign_task(agent, {"task_id": task}, tasks, list(board.agent_names), claims)
        claims[agent] = result["result"]["task_id"]
        boards.log_action(agent, {"action": "assign_task", "task_id": task}, result, "execution", 1)
    ours = [e["payload"] for e in boards.boards[0].events if e["kind"] == "action_executed"]
    theirs = [e["payload"] for e in case["boards"][0]["events"] if e["kind"] == "action_executed"]
    assert ours == theirs


def test_missing_claims_filled_like_colosseum():
    cases = json.loads((FIX / "colosseum_scoring.json").read_text())["cases"]
    for case in cases:
        game = load_game(None, {"board.n_tasks": case["tasks"]})
        board = make_board(case["seed"], game.board)
        rng = board_generator_after(case["seed"], game)
        final = dict(case["fill"]["partial"])
        for agent in board.agent_names:
            if agent not in final:
                final[agent] = rng.choice([None] + [t.id for t in board.tasks])
        assert final == case["fill"]["filled"], case["seed"]


def test_turn_loop_matches_colosseum_mechanics():
    """Messages: system, user, then assistant + one tool message per call; stops at a commit; <= 3 calls."""
    game = load_game("configs/games/colosseum_paper.yaml", {"phases": [{"kind": "claim"}], "boards.public": False,
                                                             "boards.secret": False})
    seen = []

    class FakeClient:
        config = type("C", (), {"send_seed": False})()

        def __init__(self, replies):
            self.replies = list(replies)

        async def complete(self, messages, tools, seed=None):
            seen.append([m["role"] for m in messages])
            return {"response": {"choices": [{"message": self.replies.pop(0)}], "usage": {"prompt_tokens": 10, "completion_tokens": 2}}}

    def call(name, args, i):
        return {"role": "assistant", "content": None,
                "tool_calls": [{"id": f"c{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}

    logs = []

    def make(name, roles):
        if name == roles.turn_order[0]:     # first agent: a bad id, then a valid claim
            return LLMAgent(name, FakeClient([call("assign_task", {"task_id": "nope"}, 1),
                                              call("assign_task", {"task_id": "ISSUE-0001::review"}, 2)]), logs.append)
        if name == roles.turn_order[1]:     # second agent: three text answers, never claims
            return LLMAgent(name, FakeClient([{"role": "assistant", "content": "thinking"}] * 3), logs.append)
        return ScriptedAgent(name, "greedy")

    episode = Episode(game, 1, make)
    r = asyncio.run(episode.play())[0]
    first, second = r["turns"][0], r["turns"][1]
    assert first["model_calls"] == 2 and first["committed"]
    assert first["tool_calls"][0]["result"]["reason"] == "Unknown task_id nope"
    assert seen[1] == ["system", "user", "assistant", "tool"]
    assert second["model_calls"] == 3 and not second["committed"]
    assert second["agent"] in r["missing_claims"] and second["agent"] in r["filled"]     # assignment_filling
    assert len(logs) == 5


# --- the team's games ----------------------------------------------------------------------------


def test_game2_reservations_with_chat():
    game = load_game("configs/games/team/game2_reserve_chat.yaml", {"series.rounds": 1})
    _, rounds = play(game, seed=4)
    r = rounds[0]
    assert len(r["reservations"]) == 2
    kinds = [t["kind"] for t in r["turns"]]
    assert kinds == ["reserve"] * 12 + ["claim"] * 6
    for t in r["turns"][:12]:                     # public board for all (closest to Colosseum)
        assert t["tools_offered"] == ["reserve_task", "post_message"]
    assert all(t["tools_offered"] == ["assign_task"] for t in r["turns"][12:])
    assert r["objective"]["hv_task"] is not None
    m = round_metrics(r)
    assert m["hv_task"] == r["objective"]["hv_task"]
    assert len(m["reservation_colluders_same_issue"]) == 2


def test_game3_has_no_board_and_game1_is_colosseums_planning():
    g3 = load_game("configs/games/team/game3_reserve_nochat.yaml", {"series.rounds": 1})
    _, r3 = play(g3, seed=2)
    assert r3[0]["boards"] == [] and all("post_message" not in t["tools_offered"] for t in r3[0]["turns"])
    g1 = load_game("configs/games/team/game1_chat.yaml", {"series.rounds": 1})
    _, r1 = play(g1, seed=2)
    chats = [t for t in r1[0]["turns"] if t["kind"] == "chat"]
    assert len(chats) == 24 and {b["kind"] for b in r1[0]["boards"]} == {"public", "secret"}


def test_team_defaults_closest_to_colosseum():
    """Game 1 has Colosseum's phases: its system prompt is Colosseum's, word for word."""
    from env.prompts import load_texts, system_prompt
    paper = load_game("configs/games/colosseum_paper.yaml")
    g1 = load_game("configs/games/team/game1_chat.yaml")
    assert system_prompt(load_texts(g1.prompts), g1) == system_prompt(load_texts(paper.prompts), paper)
    for name in ("game1_chat", "game2_reserve_chat", "game3_reserve_nochat"):
        g = load_game(f"configs/games/team/{name}.yaml")
        assert (g.board, g.roles, g.scoring, g.assignment_filling, g.calls_per_turn) == \
               (paper.board, paper.roles, paper.scoring, paper.assignment_filling, paper.calls_per_turn)
        assert g.series.mode == "independent" and g.series.rounds == 20
        hv = g.objective.high_value_ticket
        assert (hv.team_value, hv.team_penalty) == (0, 0)          # Colosseum's team score unchanged


def test_cost_from_model_prices():
    from run import cost
    from agents import load_model
    gpt = load_model("configs/models/gpt-4.1-mini.yaml")
    assert cost(gpt, 1_000_000, 1_000_000) == pytest.approx(gpt.price_input_per_1m + gpt.price_output_per_1m)
    assert cost(load_model("configs/models/local-llama-server.yaml"), 10, 10) is None


def test_exclusive_reservations_block_others():
    game = load_game("configs/games/team/game3_reserve_nochat.yaml",
                     {"series.rounds": 1, "phases": [{"kind": "reserve", "passes": 1, "binding": "exclusive"}, {"kind": "claim"}]})
    _, rounds = play(game, seed=3, policy="greedy")
    reserved = {t: a for a, t in rounds[0]["reservations"][0].items() if t}
    for agent, task in rounds[0]["assignment"].items():
        if task in reserved:
            assert reserved[task] == agent


def test_series_modes():
    base = "configs/games/team/game3_reserve_nochat.yaml"
    _, ind = play(load_game(base, {"series.rounds": 3}), seed=5)
    assert [r["board_seed"] for r in ind] == [5, 1005, 2005]
    ep, same = play(load_game(base, {"series.mode": "repeated_same_board", "series.rounds": 3,
                                     "series.feedback": ["claims", "own_reward", "team_score"]}), seed=5)
    assert len({json.dumps(r["board"]) for r in same}) == 1 and len({tuple(r["colluders"]) for r in same}) == 1
    assert len(ep.history[same[0]["turn_order"][0]]) == 3 and "team score" in ep.history[same[0]["turn_order"][0]][0]
    _, new = play(load_game(base, {"series.mode": "repeated_new_board", "series.rounds": 3}), seed=5)
    names = [[a[0] for a in r["board"]["agents"]] for r in new]
    tasks = [[t[0] + t[4] for t in r["board"]["tasks"]] for r in new]
    assert names[0] == names[1] == names[2] and len({tuple(t) for t in tasks}) > 1


def test_history_appears_in_later_prompts():
    game = load_game("configs/games/team/game3_reserve_nochat.yaml",
                     {"series.mode": "repeated_same_board", "series.rounds": 2})
    prompts = []
    ep = Episode(game, 1, lambda n, r: ScriptedAgent(n, "greedy"), log_turn=lambda rec: prompts.append(rec))
    asyncio.run(ep.play())
    assert "=== PREVIOUS ROUNDS ===" not in prompts[0]["user_prompt"]
    assert "=== PREVIOUS ROUNDS ===" in prompts[-1]["user_prompt"]


# --- views -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("view", ["visible", "hidden", "issue_only", "noisy"])
def test_colluder_views(view):
    game = load_game("configs/games/action_channel.yaml", {"views.colluders": view, "views.noisy_swap_probability": 1.0})
    prompts = []
    ep = Episode(game, 2, lambda n, r: ScriptedAgent(n, "greedy"), log_turn=prompts.append)
    r = asyncio.run(ep.play())[0]
    first, second = r["colluders"][0], r["colluders"][1]
    assert r["turn_order"][:2] == [first, second] or r["turn_order"][:2] == [second, first]
    c1 = r["turn_order"][0]
    task = r["assignment"][c1]
    prompt = next(p["user_prompt"] for p in prompts if p["agent"] == r["turn_order"][1])
    line = next((l for l in prompt.splitlines() if l.startswith(f"- {c1}:") and "cost=" not in l), None)
    if view == "visible":
        assert line == f"- {c1}: {task}"
    elif view == "hidden":
        assert line is None
    elif view == "issue_only":
        assert line == f"- {c1}: {task.split('::')[0]}"
    else:
        assert line is not None and line != f"- {c1}: {task}"


def test_config_rejects_leaking_views():
    with pytest.raises(ValueError, match="log_claims"):
        load_game("configs/games/colosseum_paper.yaml", {"views.colluders": "hidden"})


# --- runner ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("study", sorted(str(p) for p in Path("configs/studies").glob("*.yaml")))
def test_every_study_plans(study):
    from run import build, load_yaml, plan, StudyConfig
    jobs = plan(build(StudyConfig, load_yaml(study), "study"), scripted="colluder")
    assert jobs


def test_scripted_run_end_to_end(tmp_path):
    import run
    from analysis import summarize
    study = tmp_path / "study.yaml"
    study.write_text("name: t\nconditions:\n  - {name: paper, game: configs/games/colosseum_paper.yaml}\n"
                     "  - {name: g2, game: configs/games/team/game2_reserve_chat.yaml, set: {series.rounds: 2}}\n"
                     f"models: [configs/models/scripted.yaml]\nseeds: 1-2\nout_dir: {tmp_path}\n")
    assert run.main([str(study)]) == 0
    run_dir = next(tmp_path.glob("*__t"))
    rows = (run_dir / "index.csv").read_text().strip().splitlines()
    assert len(rows) == 1 + 2 * 1 + 2 * 2                      # header + paper (2 seeds) + g2 (2 seeds x 2 rounds)
    assert summarize.main([str(run_dir)]) == 0 and (run_dir / "summary.md").exists()
    charts = {p.name for p in (run_dir / "figures").glob("*.png")}
    assert {"hv_capture.png", "by_board_kind.png", "by_round.png", "team_loss.png", "colosseum.png",
            "reservations.png", "health.png"} <= charts
    assert all((run_dir / "figures" / c.replace(".png", ".pdf")).exists() for c in charts)
    episode = json.loads(next(run_dir.glob("episodes/g2/scripted/seed1_rep0/episode.json")).read_text())
    assert episode["status"] == "complete" and len(episode["rounds"]) == 2
    assert run.main([str(study), "--resume", str(run_dir)]) == 0   # resume: everything skipped, same index
    assert len((run_dir / "index.csv").read_text().strip().splitlines()) == len(rows)


def test_board_study_writes_table_and_charts(tmp_path):
    from analysis import board_study
    assert board_study.main(["configs/board_study.yaml", "--seeds", "1-20", "--out", str(tmp_path)]) == 0
    out = next(tmp_path.iterdir())
    assert (out / "boards.csv").exists() and (out / "summary.md").exists()
    assert {"conflict_by_size.png", "price_distribution.png"} <= {p.name for p in (out / "figures").glob("*.png")}
