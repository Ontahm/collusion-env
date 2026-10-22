"""Tests for env/roles.py (spec/03-agents.md 3.6).

Reference draws in fixtures/colosseum_roles.json were produced by Colosseum's own
`_select_colluders` / `_order_agent_turns` (spec/verification/roles_fixtures.py).
"""

import json
from pathlib import Path

import pytest

from env.board import make_board
from env.roles import draw_roles, reshuffled_order

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "colosseum_roles.json").read_text())


@pytest.mark.parametrize("case", sorted(FIXTURES))
def test_identical_to_colosseum_runner(case):
    settings = dict(part.split("=") for part in case.split(","))
    for row in FIXTURES[case]:
        board = make_board(row["seed"])
        assert list(board.agent_names) == row["names"]
        roles = draw_roles(board.agent_names, row["seed"], 2, settings["selection"], settings["order"])
        assert list(roles.colluders) == row["colluders"], f"seed {row['seed']}"
        assert list(roles.turn_order) == row["turn_order"], f"seed {row['seed']}"


def test_spec_example():
    roles = draw_roles(make_board(1).agent_names, 1)
    assert roles.colluders == ("Jeanene", "Sara")
    assert roles.turn_order == ("Mona", "Sara", "Jeanene", "Shaunna", "Pauline", "Layla")
    assert roles.partner("Sara") == ("Jeanene",) and roles.partner("Mona") == ()
    assert roles.honest == ("Mona", "Shaunna", "Pauline", "Layla")


def test_reshuffle_keeps_round_zero_and_is_deterministic():
    roles = draw_roles(make_board(3).agent_names, 3)
    assert reshuffled_order(roles, 3, 0) == roles
    later = reshuffled_order(roles, 3, 4)
    assert later == reshuffled_order(roles, 3, 4)
    assert sorted(later.turn_order) == sorted(roles.turn_order) and later.colluders == roles.colluders


def test_bad_settings_raise():
    with pytest.raises(ValueError):
        draw_roles(["a", "b"], 1, selection="best")
    with pytest.raises(ValueError):
        draw_roles(["a", "b"], 1, order="alphabetical")
