"""Yield-to-partner boards (env/planted_yield.py, construction.mode: yield) and the oracle_pair /
team_optimal scripted policies."""

import asyncio

import pytest

from agents.scripted import ScriptedAgent
from env.game import Episode
from env.game_config import load_game
from env.planted_yield import check_structure
from metrics import round_metrics

GAME = "configs/games/yield_control.yaml"


def _rounds(policy, seeds, overrides=None):
    game = load_game(GAME, overrides) if overrides else load_game(GAME)
    out = []
    for seed in seeds:
        for record in asyncio.run(Episode(game, seed, lambda name, roles: ScriptedAgent(name, policy)).play()):
            out.append((record, round_metrics(record)))
    return out


def test_plan_targets_met_and_deterministic():
    first = _rounds("greedy", range(1, 6))
    again = _rounds("greedy", range(1, 6))
    for (rec, _), (rec2, _) in zip(first, again):
        plan = rec["setup"].analysis["construction"]
        assert plan["mode"] == "yield" and plan["targets_met"]
        assert plan["team_optimum_t_holder"] == plan["team_best_fit"]
        assert rec["board"] == rec2["board"]
        roles = rec["setup"].roles
        assert [plan["worse_colluder"], plan["better_colluder"]] == list(roles.turn_order[:2])


def test_oracle_ceiling_and_floors():
    seeds = range(1, 11)
    assert all(m["actions"]["better_alone_got_t"] for _, m in _rounds("oracle_pair", seeds))
    assert not any(m["actions"]["better_alone_got_t"] for _, m in _rounds("greedy", seeds))
    team = _rounds("team_optimal", seeds)
    assert not any(m["actions"]["better_alone_got_t"] for _, m in team)
    assert all(abs(m["team_loss"]) < 1e-9 for _, m in team)


def test_oracle_with_secret_chat_phase():
    chat = {"boards.secret": True, "prompts.colluder": "prompts/colluder/coalition_sum_structured_chat.txt",
            "prompts.colluder_header": True,
            "phases": [{"kind": "reserve", "passes": 2, "boards": ["secret"], "binding": "none"},
                       {"kind": "claim", "post_message": "no"}]}
    assert all(m["actions"]["better_alone_got_t"] for _, m in _rounds("oracle_pair", range(1, 6), chat))


def test_yield_needs_colluders_first_and_fixed_order():
    with pytest.raises(ValueError):
        load_game(GAME, {"roles.order": "random"})
    with pytest.raises(ValueError):
        load_game(GAME, {"roles.new_order_each_round": True})
