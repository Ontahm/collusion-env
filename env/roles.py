"""Roles: who colludes, and in which order agents act.

Spec: spec/03-agents.md 3.6.

Mirrors Colosseum's runner (`experiments/collusion/run.py`: `_select_colluders`,
`_order_agent_turns`, and the `rng.shuffle(agents)` that follows), including its use of one
generator `random.Random(seed)`: the colluders are drawn first, then the order is shuffled with
the same generator. With the same seed and settings, the same colluders and order come out.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence, Tuple

SELECTIONS = ("random", "first")
ORDERS = ("random", "colluders_first")


@dataclass(frozen=True)
class Roles:
    colluders: Tuple[str, ...]      # in selection order (Colosseum: the order `sample` returns)
    turn_order: Tuple[str, ...]     # who acts first, second, ...

    def is_colluder(self, name: str) -> bool:
        return name in self.colluders

    @property
    def honest(self) -> Tuple[str, ...]:
        return tuple(a for a in self.turn_order if a not in self.colluders)

    def partner(self, name: str) -> Tuple[str, ...]:
        """The other colluders of `name` (empty for an honest agent)."""
        return tuple(c for c in self.colluders if c != name) if name in self.colluders else ()


def draw_roles(agent_names: Sequence[str], seed: int, n_colluders: int = 2,
               selection: str = "random", order: str = "random") -> Roles:
    """Colluders and turn order for one episode, exactly as Colosseum's runner draws them.

    selection: "random" (Colosseum's default) draws `n_colluders` agents with `rng.sample`;
               "first" takes the first agents of the list and does not touch the generator.
    order:     "random" (Colosseum's default) shuffles all agents with the same generator;
               "colluders_first" puts the colluders first, then the others, each in list order.
    """
    if selection not in SELECTIONS:
        raise ValueError(f"colluder selection {selection!r}: expected one of {SELECTIONS}")
    if order not in ORDERS:
        raise ValueError(f"turn order {order!r}: expected one of {ORDERS}")
    names = [str(a) for a in agent_names]
    rng = random.Random(int(seed))
    count = min(max(int(n_colluders), 0), len(names))
    if count == 0:
        colluders: list = []
    elif selection == "random":
        colluders = [str(x) for x in rng.sample(list(names), k=count)]
    else:
        colluders = names[:count]
    if order == "random":
        turn_order = list(names)
        rng.shuffle(turn_order)
    else:
        members = set(colluders)
        turn_order = [a for a in names if a in members] + [a for a in names if a not in members]
    return Roles(colluders=tuple(colluders), turn_order=tuple(turn_order))


def reshuffled_order(roles: Roles, seed: int, round_index: int, order: str = "random") -> Roles:
    """A new turn order for round `round_index` (multi-round games with a fresh order each round).
    Round 0 keeps the episode's order; later rounds draw from a generator derived from the seed."""
    if round_index == 0 or order != "random":
        return roles
    rng = random.Random(f"order:{int(seed)}:{int(round_index)}")
    turn_order = list(roles.turn_order)
    rng.shuffle(turn_order)
    return Roles(colluders=roles.colluders, turn_order=tuple(turn_order))
