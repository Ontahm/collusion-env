"""Tests for env/board.py (spec/02-board.md, spec/03-agents.md).

The central test compares our boards with Colosseum's, bit for bit, on 1,600 boards: the
reference hashes in fixtures/colosseum_boards.json were produced by Colosseum's own code
(spec/verification/board_fixtures.py), so these tests never need Colosseum installed.
"""

import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path

import pytest

from env.board import (DEFAULT_CONFIG_FILE, BoardConfig, load_board_config, make_board, with_size)

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "colosseum_boards.json").read_text())
SEEDS = range(FIXTURES["seeds"][0], FIXTURES["seeds"][1] + 1)


def digest(board) -> str:
    return hashlib.sha256(json.dumps(board.canonical(), separators=(",", ":")).encode()).hexdigest()


# --- equality with Colosseum ------------------------------------------------------------


@pytest.mark.parametrize("case", sorted(FIXTURES["digests"]))
def test_identical_to_colosseum(case):
    """Default config: every board equals Colosseum's, tasks, profiles and costs, to the last bit."""
    sizes = dict(part.split("=") for part in case.split(","))
    config = with_size(BoardConfig(), int(sizes["tasks"]), int(sizes["agents"]))
    expected = FIXTURES["digests"][case]
    mismatched = [seed for seed, ref in zip(SEEDS, expected) if digest(make_board(seed, config)) != ref]
    assert not mismatched, f"{case}: boards differ from Colosseum for seeds {mismatched[:10]}"


@pytest.mark.parametrize("key", sorted(FIXTURES["full"]))
def test_full_boards_match_colosseum(key):
    """Two boards compared in full, so a failure shows exactly which field differs."""
    params = dict(part.split("=") for part in key.split(","))
    config = with_size(BoardConfig(), int(params["tasks"]), int(params["agents"]))
    assert make_board(int(params["seed"]), config).canonical() == FIXTURES["full"][key]


# --- configuration ----------------------------------------------------------------------


def test_default_config_file_equals_code_defaults():
    """configs/board.yaml documents the defaults; it must say exactly what the code does."""
    assert load_board_config(DEFAULT_CONFIG_FILE) == BoardConfig()


def test_partial_config_file_overrides_only_its_keys(tmp_path):
    path = tmp_path / "board.yaml"
    path.write_text("n_tasks: 15\navailability: [6, 6]\n")
    config = load_board_config(path)
    assert config == replace(BoardConfig(), n_tasks=15, availability=(6, 6))
    board = make_board(3, config)
    assert len(board.tasks) == 15
    assert {a.availability for a in board.agents} == {6.0}


def test_unknown_key_is_rejected(tmp_path):
    path = tmp_path / "board.yaml"
    path.write_text("n_task: 15\n")
    with pytest.raises(ValueError, match="unknown keys"):
        load_board_config(path)


@pytest.mark.parametrize("bad", [{"n_tasks": 0}, {"issue_tags": (2, 1)}, {"issue_tags": (0, 2)},
                                 {"tag_pool": ()}, {"skill_eps": 0.0}])
def test_invalid_values_are_rejected(bad):
    with pytest.raises(ValueError):
        load_board_config(**bad)


def test_changed_parameter_changes_the_board_deterministically():
    config = load_board_config(skill_level=(0.9, 1.0))
    assert digest(make_board(5, config)) == digest(make_board(5, config))
    assert digest(make_board(5, config)) != digest(make_board(5))


# --- what the spec states -----------------------------------------------------------------


def test_worked_example_of_the_spec():
    """spec/02 2.5 and spec/03 3.3-3.4: seed 1, 8 tasks."""
    board = make_board(1)
    assert board.agent_names == ("Layla", "Jeanene", "Pauline", "Mona", "Sara", "Shaunna")
    assert board.issue_ids == ("ISSUE-0001", "ISSUE-0002")
    assert [t.id for t in board.tasks][-1] == "ISSUE-0002::test"            # issue 2 is cut after 3 tasks
    assert board.task("ISSUE-0002::test").effort == pytest.approx(5.6)
    layla = board.agent("Layla")
    assert layla.availability == 4.0
    assert layla.skill("mobile-development") == pytest.approx(0.77, abs=0.005)
    assert board.cost("Layla", "ISSUE-0001::implement") == pytest.approx(4 / (layla.skill("mobile-development") + 0.1))
    assert board.cost("Layla", "ISSUE-0002::implement") == pytest.approx(8 / (layla.skill("testing") / 2 + 0.1) + 4)
    assert board.cost("Mona", "ISSUE-0001::implement") == pytest.approx(40.0)  # no skill: 10 x effort


@pytest.mark.parametrize("n_tasks", [1, 5, 8, 12, 20])
def test_structure(n_tasks):
    """Invariants of spec/02 2.2 and spec/03 3.2-3.3, on many seeds."""
    config = with_size(BoardConfig(), n_tasks)
    for seed in range(1, 101):
        board = make_board(seed, config)
        assert len(board.tasks) == n_tasks
        assert len(board.issue_ids) == math.ceil(n_tasks / 5)
        for issue in board.issue_ids:
            tasks = [t for t in board.tasks if t.issue_id == issue]
            assert len({t.tags for t in tasks}) == 1 and len({t.priority for t in tasks}) == 1
            assert [t.work_type for t in tasks] == list(config.task_types[:len(tasks)])
            assert 1 <= len(tasks[0].tags) <= 2
        board_tags = {tag for t in board.tasks for tag in t.tags}
        assert len(set(board.agent_names)) == len(board.agents) == 6
        for agent in board.agents:
            assert 1 <= len(agent.skills) <= 2
            assert {tag for tag, _ in agent.skills} <= board_tags
            assert all(0.6 <= level <= 1.0 for _, level in agent.skills)
            assert agent.availability in {4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0}
            for task in board.tasks:
                assert math.isfinite(board.cost(agent.name, task.id)) and board.cost(agent.name, task.id) > 0


def test_same_seed_same_board_and_names_do_not_shift_draws():
    assert digest(make_board(7)) == digest(make_board(7))
    assert digest(make_board(7)) != digest(make_board(8))
    # The names come from their own generator: changing its offset changes the names only.
    other = make_board(7, load_board_config(name_seed_offset=1))
    assert other.agent_names != make_board(7).agent_names
    assert [t.id for t in other.tasks] == [t.id for t in make_board(7).tasks]
    assert [a.skills for a in other.agents] == [a.skills for a in make_board(7).agents]
