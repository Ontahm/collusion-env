"""The scenario catalogue (configs/scenarios.yaml): every scenario resolves, no two have the same
rules, studies only change the run size, old runs are recognised, and docs/reference/scenarios.md is up to date."""

import json

import pytest

import run
import scenarios
from env.configio import build, load_yaml, to_plain
from env.game_config import load_game


def test_every_scenario_resolves_and_is_unique():
    fps = scenarios._fingerprints()                     # raises if two scenarios have the same rules
    assert len(fps) == len(scenarios.catalogue())
    assert all(s.family in scenarios.FAMILIES for s in scenarios.catalogue().values())


def test_scenarios_md_is_up_to_date():
    assert scenarios.main(["--check"]) == 0, "run: make scenarios"


def test_a_study_may_only_change_the_run_size():
    ok = build(run.ConditionConfig, {"scenario": "HV-2", "set": {"series.rounds": 3}}, "c")
    name, game, sid = run.resolve_condition(ok)
    assert (name, sid, game.series.rounds) == ("hv_game2_reserve_chat", "HV-2", 3)
    with pytest.raises(ValueError, match="rules are fixed"):
        run.resolve_condition(build(run.ConditionConfig, {"scenario": "HV-2", "set": {"boards.public": False}}, "c"))
    with pytest.raises(ValueError, match="unknown scenario"):
        run.resolve_condition(build(run.ConditionConfig, {"scenario": "HV-99"}, "c"))


def test_rules_are_recognised_whatever_the_spelling_or_size():
    # ACT-2 is the action-channel game as written; the explicit view and another size change nothing
    assert scenarios.identify(to_plain(load_game("configs/games/action_channel.yaml"))) == "ACT-2"
    assert scenarios.identify(to_plain(load_game("configs/games/action_channel.yaml", {"series.rounds": 7}))) == "ACT-2"
    assert scenarios.identify(to_plain(load_game("configs/games/action_channel.yaml", {"views.colluders": "noisy"}))) == "ACT-4"
    assert scenarios.identify(to_plain(load_game("configs/games/action_channel.yaml", {"board.n_tasks": 10}))) is None
    # a config recorded before a setting existed: the missing setting takes its default
    old = to_plain(load_game("configs/games/team/game1_chat.yaml"))
    old.pop("calls_per_turn")
    assert scenarios.identify(old) == "HV-1"


def test_every_study_uses_catalogued_scenarios():
    import glob
    for f in glob.glob("configs/studies/*.yaml"):
        study = build(run.StudyConfig, load_yaml(f), "study")
        assert all(c.scenario for c in study.conditions), f"{f}: every condition should name its scenario"
        assert run.plan(study), f
