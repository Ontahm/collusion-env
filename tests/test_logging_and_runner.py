"""Logging levels and items, .env settings, the runner's checks, and a full run through HTTP
against a stand-in OpenAI-compatible server (tests/fake_llm.py)."""

import io
import json
import os
import re
from pathlib import Path

import pytest

import fake_llm
import run
from env.board import make_board
from env.game import Episode
from env.game_config import load_game
from logs import LEVELS, LogSettings, RunLogger
from metrics import round_metrics


# --- settings ------------------------------------------------------------------------------------


def test_levels_items_and_env(monkeypatch):
    assert LEVELS["quiet"] == {"errors"} and "progress" in LEVELS["normal"] and "cot" in LEVELS["debug"]
    monkeypatch.setenv("COLLUSION_LOG_LEVEL", "normal")
    monkeypatch.setenv("COLLUSION_LOG_SHOW", "cot,metrics")
    monkeypatch.setenv("COLLUSION_LOG_HIDE", "progress")
    s = LogSettings.from_env()
    assert {"cot", "metrics", "plan"} <= s.show and "progress" not in s.show
    s = LogSettings.from_env("quiet")                       # command line wins over the env level
    assert "plan" not in s.show and "cot" in s.show          # env items still added
    with pytest.raises(ValueError, match="log items"):
        LogSettings.from_env(show=["cots"])
    with pytest.raises(ValueError, match="log level"):
        LogSettings.from_env("loud")


def test_logger_prints_only_enabled_items_and_clips():
    out = io.StringIO()
    log = RunLogger(LogSettings(level="normal", show={"plan"}, text_chars=10), stream=out)
    log.plan("the plan")
    log.summary("hidden")
    assert out.getvalue() == "the plan\n"
    assert log.clip("x" * 25).startswith("xxxxxxxxxx… [+15 chars]")


def test_env_file_parsing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('export A_KEY="quoted # not a comment"\nB_KEY=plain # a comment\n# C_KEY=no\nD_KEY=\'single\'\n')
    for k in ("A_KEY", "B_KEY", "C_KEY", "D_KEY"):
        monkeypatch.delenv(k, raising=False)
    run.load_env_file(env)
    assert os.environ["A_KEY"] == "quoted # not a comment" and os.environ["B_KEY"] == "plain"
    assert "C_KEY" not in os.environ and os.environ["D_KEY"] == "single"


# --- runner checks ------------------------------------------------------------------------------


def study_file(tmp_path, body: str) -> str:
    path = tmp_path / "s.yaml"
    path.write_text(body)
    return str(path)


def test_unknown_names_are_errors(tmp_path):
    s = run.build(run.StudyConfig, run.load_yaml(study_file(tmp_path,
        "name: t\nconditions: [{name: a, game: configs/games/colosseum_paper.yaml}]\nmodels: [configs/models/scripted.yaml]\n")), "study")
    with pytest.raises(ValueError, match="unknown conditions"):
        run.plan(s, only=["b"])
    with pytest.raises(ValueError, match="unknown labels"):
        run.plan(s, models=["nope"])
    dup = run.build(run.StudyConfig, {"name": "d", "conditions": [{"name": "a", "game": "configs/games/colosseum_paper.yaml"}],
                                      "models": ["configs/models/scripted.yaml", "configs/models/scripted.yaml"]}, "study")
    with pytest.raises(ValueError, match="share a label"):
        run.plan(dup)


def test_board_seed_overlap_warning(tmp_path):
    s = run.build(run.StudyConfig, {"name": "o", "seeds": [1, 1001], "models": ["configs/models/scripted.yaml"],
                                    "conditions": [{"name": "g", "game": "configs/games/team/game3_reserve_nochat.yaml",
                                                    "set": {"series.rounds": 2}}]}, "study")
    assert run.board_seed_overlaps(run.plan(s)) and not run.board_seed_overlaps(run.plan(s, seeds=[1, 2]))


def test_quiet_run_prints_nothing_and_normal_prints_progress(tmp_path, capsys):
    path = study_file(tmp_path, "name: t\nconditions: [{name: a, game: configs/games/colosseum_paper.yaml}]\n"
                                f"models: [configs/models/scripted.yaml]\nseeds: [1]\nout_dir: {tmp_path / 'q'}\n")
    assert run.main([path, "-q", "--no-summary"]) == 0
    assert capsys.readouterr().out == ""
    assert run.main([path, "--no-summary", "--out", str(tmp_path / "n")]) == 0
    out = capsys.readouterr().out
    assert "study t: 1 episodes" in out and "[1/1] a · scripted · seed 1 · complete" in out
    log = next((tmp_path / "n").glob("*/run.log")).read_text()
    assert "study t: 1 episodes" in log                              # the plan reaches run.log too


# --- through HTTP ---------------------------------------------------------------------------------


def http_study(tmp_path, port: int) -> str:
    (tmp_path / "m.yaml").write_text(f"label: fake\nbase_url: http://127.0.0.1:{port}/v1\nmodel: fake\n"
                                     "api_key_env: null\nsend_seed: true\nmax_retries: 0\n")
    return study_file(tmp_path, "name: h\nconditions:\n  - {name: g2, game: configs/games/team/game2_reserve_chat.yaml, "
                                f"set: {{series.rounds: 1}}}}\nmodels: [{tmp_path}/m.yaml]\nseeds: [1, 2]\n"
                                f"out_dir: {tmp_path / 'out'}\nmax_concurrency: 1\n")


def test_full_run_through_http_debug_log_and_distinct_seeds(tmp_path, capsys):
    server, requests = fake_llm.start()
    try:
        assert run.main([http_study(tmp_path, server.server_port), "-vv", "--no-summary"]) == 0
    finally:
        server.shutdown()
    out = capsys.readouterr().out
    assert "reserve_task(" in out and "thinking]" in out and "metrics:" in out
    calls = [json.loads(l) for f in tmp_path.glob("out/*/episodes/**/calls.jsonl") for l in f.read_text().splitlines()]
    seeds = [c["seed"] for c in calls]
    assert len(seeds) == len(requests) == len(set(seeds))            # one distinct seed per call
    turns = [json.loads(l) for f in tmp_path.glob("out/*/episodes/**/turns.jsonl") for l in f.read_text().splitlines()]
    assert all(t["steps"][0]["reasoning"] for t in turns)


def test_wrong_key_stops_the_model(tmp_path, capsys):
    server, requests = fake_llm.start(status=401)
    try:
        assert run.main([http_study(tmp_path, server.server_port), "--no-summary"]) == 3
    finally:
        server.shutdown()
    out = capsys.readouterr().out
    assert "stopping every episode of model 'fake'" in out and "not run (model unusable)" in out
    assert len(requests) == 1                                         # no retries, no second episode


def test_local_server_serving_another_model_is_not_used(tmp_path, capsys):
    server, requests = fake_llm.start()                               # serves the model "fake"
    try:
        study = http_study(tmp_path, server.server_port)
        (tmp_path / "m.yaml").write_text((tmp_path / "m.yaml").read_text().replace("model: fake", "model: other"))
        assert run.main([study, "--no-summary"]) == 3
    finally:
        server.shutdown()
    out = capsys.readouterr().out
    assert "serves ['fake'], not 'other'" in out and "not run (model unusable)" in out
    assert requests == []                                             # no episode ran under the wrong label


def test_resume_with_another_server_skips_finished_episodes(tmp_path, capsys):
    """The two-pass workflow of configs/studies/local_models.yaml: model a's server, then model b's."""
    def point(name, port, model):
        f = tmp_path / name
        f.write_text(re.sub(r"127\.0\.0\.1:\d+", f"127.0.0.1:{port}", f.read_text())
                     .replace("model: fake", f"model: {model}").replace("model: other", f"model: {model}"))

    server, _ = fake_llm.start()                                      # serves "fake": a's model
    try:
        study = Path(http_study(tmp_path, server.server_port))
        (tmp_path / "b.yaml").write_text((tmp_path / "m.yaml").read_text().replace("label: fake", "label: b"))
        point("b.yaml", server.server_port, "other")
        study.write_text(study.read_text().replace(f"models: [{tmp_path}/m.yaml]",
                                                   f"models: [{tmp_path}/m.yaml, {tmp_path}/b.yaml]"))
        assert run.main([str(study), "--no-summary"]) == 3            # pass 1: b is not served
        run_dir = next((tmp_path / "out").iterdir())
        assert len(list(run_dir.glob("episodes/g2/fake/*/episode.json"))) == 2
    finally:
        server.shutdown()
    server, requests = fake_llm.start()                               # pass 2: the server now serves b's model
    try:
        point("m.yaml", server.server_port, "gone")
        point("b.yaml", server.server_port, "fake")
        capsys.readouterr()
        assert run.main([str(study), "--resume", str(run_dir), "--no-summary"]) == 0
    finally:
        server.shutdown()
    out = capsys.readouterr().out
    assert "model unusable" not in out and out.count("· skipped ·") == 2 and out.count("· complete ·") == 2
    assert len(list(run_dir.glob("episodes/g2/b/*/episode.json"))) == 2


# --- metrics ignore random fills --------------------------------------------------------------------


def test_random_fill_is_not_a_capture():
    game = load_game("configs/games/team/game3_reserve_nochat.yaml", {"series.rounds": 1})

    class Silent:                                                     # never claims: everyone gets filled
        async def take_turn(self, turn):
            return {"model_calls": 0, "tool_calls": [], "usage": {}, "error": None}

    import asyncio
    for seed in range(1, 30):
        r = asyncio.run(Episode(game, seed, lambda n, roles: Silent()).play())[0]
        m = round_metrics(r)
        assert m["hv_captured_by_coalition"] is False and m["same_issue_match"] is False
        assert len(m["colluders_filled"]) == 2 and m["health"]["filled_claims"] == 6
