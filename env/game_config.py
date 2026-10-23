"""Game configuration: every setting of a game, with Colosseum's paper setting as the default.

Spec: spec/05-protocol.md, spec/07-scenarios.md. Reference of keys: spec/15-configuration.md.

A game is a series of rounds; a round is a list of phases (chat, reserve, claim), each made of
passes in which every participating agent takes one turn. With every default, the game is
Colosseum's Jira collusion experiment as in the paper's regret config: 6 agents, 2 random
colluders, 8 tasks, random order, a public board for all and a secret board for the colluders,
4 planning rounds, one claiming pass, random fill of missing claims, Colosseum's prompts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple, Union

from env.board import BoardConfig
from env.configio import apply_set, build, load_yaml
from env.construct import ConstructionConfig
from env.objectives import ObjectiveConfig
from env.roles import ORDERS, SELECTIONS
from env.scoring import ScoringConfig

PHASE_KINDS = ("chat", "reserve", "claim")
PARTICIPANTS = ("all", "colluders", "honest")
BOARD_KINDS = ("public", "secret")
POST_MODES = ("offered", "accepted", "no")
BINDINGS = ("none", "exclusive")
COLLUDER_VIEWS = ("visible", "hidden", "issue_only", "noisy")
HONEST_VIEWS = ("visible", "hidden")
NAME_VIEWS = ("shown", "anonymous")
SERIES_MODES = ("independent", "repeated_same_board", "repeated_new_board")
FEEDBACK = ("claims", "own_reward", "all_rewards", "team_score", "reservations")


@dataclass(frozen=True)
class PhaseConfig:
    kind: str                               # chat | reserve | claim
    passes: int = 1                         # each pass: every participant takes one turn, in turn order
    participants: str = "all"               # all | colluders | honest
    boards: Tuple[str, ...] = ()            # boards an agent may post to in this phase (public, secret);
                                            # a listed board that is disabled in `boards` is ignored
    post_message: str = "offered"           # offered: in the tool list | accepted: not listed but executed
                                            # if called (Colosseum's claiming phase) | no: refused
    binding: str = "none"                   # reserve phases: none | exclusive (others cannot take it)


@dataclass(frozen=True)
class RolesConfig:
    colluders: int = 2
    selection: str = "random"               # random (Colosseum) | first
    order: str = "random"                   # random (Colosseum) | colluders_first
    new_order_each_round: bool = False      # multi-round: draw a new random order every round


@dataclass(frozen=True)
class BoardsConfig:
    public: bool = True                     # one board for all agents
    secret: bool = True                     # one board for the colluders
    log_claims: bool = True                 # Colosseum posts every claim on the claimant's boards
    log_reservations: bool = False          # same for reservations


@dataclass(frozen=True)
class ViewsConfig:
    colluders: str = "visible"              # a colluder's view of its partner's picks: visible | hidden | issue_only | noisy
    honest: str = "visible"                 # honest agents' view of all picks: visible | hidden
    noisy_swap_probability: float = 0.5
    names: str = "shown"                    # who made each pick: shown (Colosseum) | anonymous (labels redrawn every round, own picks excepted)


@dataclass(frozen=True)
class SeriesConfig:
    mode: str = "independent"               # independent | repeated_same_board | repeated_new_board
    rounds: int = 1
    seed_stride: int = 1000                 # board seed of round r (independent, new board) = seed + r * stride
    feedback: Tuple[str, ...] = ("claims", "own_reward")   # shown after each round in repeated modes


@dataclass(frozen=True)
class PromptsConfig:
    system: str = "prompts/system/colosseum.txt"
    colluder: str = "prompts/colluder/colosseum_simple.txt"   # "" = colluders get no instruction (Colosseum "control")
    colluder_header: bool = True            # Colosseum's "=== SECRET COALITION INSTRUCTIONS ===" block
    variant_name: str = "simple"            # shown in that header ("Prompt variant: simple")
    honest_hv_note: str = "prompts/honest/hv_note.txt"
    phases: str = "prompts/phases.yaml"
    text_tool_instructions: bool = False    # Colosseum's text tool instructions (its vllm client); prompt text only
    show_payoffs: bool = False              # add each agent's own reward per task to its prompt (Colosseum: no; agents see costs only)


@dataclass(frozen=True)
class GameConfig:
    name: str = "colosseum_paper"
    description: str = ""
    board: BoardConfig = field(default_factory=BoardConfig)
    roles: RolesConfig = field(default_factory=RolesConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    assignment_filling: bool = True         # Colosseum's regret config: random fill of missing claims
    objective: ObjectiveConfig = field(default_factory=ObjectiveConfig)
    construction: ConstructionConfig = field(default_factory=ConstructionConfig)   # planted boards (actions design v0.4); default none = Colosseum
    boards: BoardsConfig = field(default_factory=BoardsConfig)
    phases: Tuple[PhaseConfig, ...] = (
        PhaseConfig(kind="chat", passes=4, boards=("public", "secret")),
        PhaseConfig(kind="claim", post_message="accepted", boards=("public", "secret")),
    )
    views: ViewsConfig = field(default_factory=ViewsConfig)
    series: SeriesConfig = field(default_factory=SeriesConfig)
    calls_per_turn: int = 3
    prompts: PromptsConfig = field(default_factory=PromptsConfig)

    def __post_init__(self) -> None:
        def check(ok: bool, message: str) -> None:
            if not ok:
                raise ValueError(f"game {self.name!r}: {message}")

        check(self.roles.selection in SELECTIONS, f"roles.selection must be one of {SELECTIONS}")
        check(self.roles.order in ORDERS, f"roles.order must be one of {ORDERS}")
        check(len(self.phases) >= 1, "at least one phase")
        for i, p in enumerate(self.phases):
            check(p.kind in PHASE_KINDS, f"phases[{i}].kind must be one of {PHASE_KINDS}")
            check(p.passes >= 1, f"phases[{i}].passes must be >= 1")
            check(p.participants in PARTICIPANTS, f"phases[{i}].participants must be one of {PARTICIPANTS}")
            check(p.post_message in POST_MODES, f"phases[{i}].post_message must be one of {POST_MODES}")
            check(p.binding in BINDINGS, f"phases[{i}].binding must be one of {BINDINGS}")
            for b in p.boards:
                check(b in BOARD_KINDS, f"phases[{i}].boards: {b!r} is not one of {BOARD_KINDS}")
            # A board listed here but disabled in `boards` is ignored (agents post on the boards that exist).
            check(p.kind != "chat" or any(getattr(self.boards, b) for b in p.boards),
                  f"phases[{i}]: a chat phase needs at least one enabled board")
        claims = [i for i, p in enumerate(self.phases) if p.kind == "claim"]
        check(claims == [len(self.phases) - 1], "exactly one claim phase, and it must be the last phase")
        check(self.views.colluders in COLLUDER_VIEWS, f"views.colluders must be one of {COLLUDER_VIEWS}")
        check(self.views.honest in HONEST_VIEWS, f"views.honest must be one of {HONEST_VIEWS}")
        check(0.0 <= self.views.noisy_swap_probability <= 1.0, "views.noisy_swap_probability must be in [0, 1]")
        check(self.views.names in NAME_VIEWS, f"views.names must be one of {NAME_VIEWS}")
        self.construction.check()
        check(self.construction.mode == "none" or self.roles.colluders == 2,
              "construction.mode planted needs roles.colluders: 2")
        check(not (self.views.names == "anonymous" and (self.boards.log_claims or self.boards.log_reservations)
                   and (self.boards.public or self.boards.secret)),
              "views.names is anonymous, but logging picks on a board would show who made them")
        check(self.series.mode in SERIES_MODES, f"series.mode must be one of {SERIES_MODES}")
        check(self.series.rounds >= 1, "series.rounds must be >= 1")
        for item in self.series.feedback:
            check(item in FEEDBACK, f"series.feedback: {item!r} is not one of {FEEDBACK}")
        check(self.calls_per_turn >= 1, "calls_per_turn must be >= 1")
        check(not self.boards.secret or self.roles.colluders >= 2, "a secret board needs at least 2 colluders")
        # A board shared by both colluders would carry the partner's picks even when the view hides them.
        hides = self.views.colluders != "visible"
        shared = self.boards.public or self.boards.secret
        check(not (hides and shared and self.boards.log_claims),
              "views.colluders hides the partner's picks, but boards.log_claims would post them on a shared board")
        check(not (hides and shared and self.boards.log_reservations),
              "views.colluders hides the partner's picks, but boards.log_reservations would post them on a shared board")
        check(not (self.views.honest == "hidden" and self.boards.public and (self.boards.log_claims or self.boards.log_reservations)),
              "views.honest hides picks, but logging picks on the public board would show them")

    @property
    def has_reservations(self) -> bool:
        return any(p.kind == "reserve" for p in self.phases)


def load_game(source: Union[str, Path, Mapping[str, Any], None] = None,
              overrides: Optional[Mapping[str, Any]] = None) -> GameConfig:
    """A game from a YAML file (with `extends:`) or a mapping, plus dotted overrides.
    `board` may be a path to a board config file, or a mapping of board keys."""
    if source is None:
        data: dict = {}
    elif isinstance(source, Mapping):
        data = dict(source)
    else:
        data = load_yaml(source)
    if isinstance(data.get("board"), str):           # a board file: load it before overrides like board.n_tasks
        data["board"] = load_yaml(data["board"])
    data = apply_set(data, overrides)
    return build(GameConfig, data, "game")
