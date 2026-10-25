"""The repeated jackpot game (configs/games/jackpot_repeated.yaml): the colluders' bonus feedback, and
a server that stops mid-series (spending limit) keeping the finished rounds (no random fills)."""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fake_llm  # noqa: E402
import run  # noqa: E402


def study(tmp_path, condition: str, model: str) -> str:
    path = tmp_path / "s.yaml"
    path.write_text(f"name: r\nconditions:\n  - {condition}\nmodels: [{model}]\nseeds: [1]\n"
                    f"out_dir: {tmp_path / 'out'}\nmax_concurrency: 1\n")
    return str(path)


def test_bonus_feedback_reaches_colluders_only(tmp_path):
    assert run.main([study(tmp_path, "{scenario: JPR-2}", "configs/models/gpt-5-mini.yaml"),
                     "--scripted", "jackpot", "--no-summary"]) == 0
    ep = json.loads(next(tmp_path.glob("out/*/episodes/**/episode.json")).read_text())
    assert ep["status"] == "complete" and len(ep["rounds"]) == 5
    colluders = set(ep["rounds"][0]["colluders"])
    jackpots = [r["analysis"]["construction"]["jackpot_task"] for r in ep["rounds"]]
    turns = [json.loads(l) for l in next(tmp_path.glob("out/*/episodes/**/turns.jsonl")).read_text().splitlines()]
    last = {t["agent"]: t["user_prompt"] for t in turns if t.get("round") == 4}
    for agent, prompt in last.items():
        assert ("bonus task: " + jackpots[0]) in prompt if agent in colluders else "bonus task" not in prompt
    assert all(r["analysis"]["construction"]["A"] == ep["rounds"][0]["analysis"]["construction"]["A"] for r in ep["rounds"])


def test_stopped_server_keeps_finished_rounds_without_random_fills(tmp_path):
    server, _ = fake_llm.start(fail_after=12)                 # 6 agents x 1 call: rounds 1-2 answered, round 3 fails
    (tmp_path / "m.yaml").write_text(f"label: fake\nbase_url: http://127.0.0.1:{server.server_port}/v1\nmodel: fake\n"
                                     "api_key_env: null\nmax_retries: 0\nstop_on_error: true\n")
    try:
        assert run.main([study(tmp_path, "{scenario: JPR-2}", tmp_path / "m.yaml"), "--yes", "--no-summary"]) == 3
    finally:
        server.shutdown()
    run_dir = next(tmp_path.glob("out/*"))
    ep = json.loads(next(run_dir.glob("episodes/**/episode.json")).read_text())
    assert ep["status"] == "failed" and "ModelUnavailable" in ep["error"]
    assert [r["round"] for r in ep["rounds"]] == [0, 1] and not any(r["filled"] for r in ep["rounds"])
    assert not (run_dir / "index.csv").exists()
    assert len(list(csv.DictReader((run_dir / "index_partial.csv").open()))) == 2
