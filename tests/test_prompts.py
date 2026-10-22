"""Tests for env/prompts.py (spec/06-prompts.md).

The 144 reference prompts in fixtures/colosseum_prompts.json.gz were rendered by Colosseum's own
prompt classes from states built with Colosseum/Terrarium objects (spec/verification/prompt_fixtures.py).
Each test rebuilds the same state here and requires the identical text.
"""

import gzip
import json
from pathlib import Path

import pytest

from env.blackboards import format_events
from env.board import BoardConfig, make_board, with_size
from env.game_config import load_game
from env.prompts import TurnView, load_texts, system_prompt, template_values, user_prompt

CASES = json.load(gzip.open(Path(__file__).parent / "fixtures" / "colosseum_prompts.json.gz", "rt"))["cases"]


def game_for(case):
    overrides = {"board.n_tasks": case["tasks"]}
    if case["variant"] == "control":
        overrides["prompts.colluder"] = ""
    overrides["prompts.variant_name"] = case["variant"]
    overrides["prompts.text_tool_instructions"] = case["provider"] == "vllm"
    return load_game(None, overrides)


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"s{c['seed']}-t{c['tasks']}-{c['phase']}-{c['variant']}-{c['provider']}-{c['agent']}")
def test_identical_to_colosseum(case):
    game = game_for(case)
    texts = load_texts(game.prompts)
    board = make_board(case["seed"], with_size(BoardConfig(), case["tasks"]))
    agent = case["agent"]
    is_colluder = agent in case["colluders"]
    coalition = tuple(sorted(case["colluders"]))
    boards = [b for b in case["boards"] if agent in b["participants"]]
    contexts = {str(i): format_events(b["events"]) for i, b in enumerate(case["boards"]) if agent in b["participants"]}
    assert len(contexts) == len(boards)
    claims = {a: str(None if t == "skip" else t) for a, t in case["claims"]}
    view = TurnView(agent=agent, phase_kind="chat" if case["phase"] == "planning" else "claim", iteration=1,
                    claims=claims, board_contexts=contexts, is_colluder=is_colluder, coalition=coalition,
                    secret_board_id=1 if is_colluder else None,
                    template_values=template_values(agent, coalition, 1, None, 0, 0, 0, 1))
    assert system_prompt(texts, game) == case["system"]
    assert user_prompt(texts, game, board, view) == case["user"]


def test_unknown_placeholder_is_an_error(tmp_path):
    from env.prompts import fill
    with pytest.raises(KeyError, match="unknown placeholder"):
        fill("Hello {nobody}", {"agent": "x"})
