"""What an agent sees of the other agents' picks (reservations and claims).

Spec: spec/07-scenarios.md.

Colosseum shows every agent all claims made so far. A game can change what a colluder sees of its
partner's picks (`views.colluders`) and what honest agents see (`views.honest`). Picks by honest
agents are always visible to colluders; an agent always sees its own picks.
"""

from __future__ import annotations

import random
from typing import Dict, Optional

from env.board import Board
from env.game_config import ViewsConfig
from env.roles import Roles

Picks = Dict[str, Optional[str]]     # agent -> task id or None (skip)


def noisy_swap_active(seed: int, round_index: int, probability: float) -> bool:
    """One draw per episode round decides whether the partner's picks are replaced ("noisy")."""
    return random.Random(f"noisy:{int(seed)}:{int(round_index)}").random() < probability


def _replacement(board: Board, seed: int, round_index: int, slot: str, task: Optional[str]) -> Optional[str]:
    """A task other than the real one, drawn uniformly over the board (fixed per pick)."""
    others = [t.id for t in board.tasks if t.id != task]
    if not others:
        return task
    return random.Random(f"noisy-pick:{int(seed)}:{int(round_index)}:{slot}").choice(others)


def visible(viewer: str, picks: Picks, board: Board, roles: Roles, views: ViewsConfig,
            seed: int, round_index: int, slot: str = "claim") -> Dict[str, str]:
    """Picks as `viewer` sees them: agent -> text shown (task id, issue id, or "None" for a skip).
    `slot` names the pick (e.g. "claim", "reserve-1-2") so a noisy replacement stays fixed."""
    shown: Dict[str, str] = {}
    is_colluder = roles.is_colluder(viewer)
    swap = None
    for agent, task in picks.items():
        if agent == viewer:
            shown[agent] = str(task)
            continue
        if not is_colluder:
            if views.honest == "visible":
                shown[agent] = str(task)
            continue
        if agent not in roles.colluders:
            shown[agent] = str(task)
            continue
        mode = views.colluders
        if mode == "visible":
            shown[agent] = str(task)
        elif mode == "issue_only":
            shown[agent] = "None" if task is None else board.task(task).issue_id
        elif mode == "noisy":
            if swap is None:
                swap = noisy_swap_active(seed, round_index, views.noisy_swap_probability)
            shown[agent] = str(_replacement(board, seed, round_index, f"{slot}:{agent}", task) if swap else task)
        # "hidden": nothing shown
    return shown
