"""The game engine: one episode = a series of rounds; a round = phases; a phase = passes of turns.

Spec: spec/05-protocol.md (Colosseum's episode and its extensions), spec/07-scenarios.md.

A turn gives an agent its prompts, the tools of the phase and a function to execute tool calls.
The agent (a model, or a scripted policy for tests) calls tools; the engine validates and records
them exactly as Colosseum does (env/tools.py, env/blackboards.py). With a Colosseum-configured game
(env/game_config.py defaults) an episode is Colosseum's: same board, colluders, order, boards,
prompts, tools, claim checks, random fill of missing claims and scoring.

Series modes (`series.mode`):
  independent          every round is a separate episode: board seed = seed + r * stride, new
                       colluders and order from that seed, no memory;
  repeated_same_board  the same board, colluders and agents every round; claims reset; agents see
                       the previous rounds (history section);
  repeated_new_board   the same agents (names) and colluders, a new board every round
                       (board seed = seed + r * stride), with history.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Protocol, Tuple

from env import tools as T
from env.blackboards import Boards, board_context, network_context
from env.board import Agent as BoardAgent
from env.board import Board, make_board
from env.construct import plant
from env.board_analysis import analyze
from env.configio import to_plain
from env.game_config import GameConfig, PhaseConfig
from env.objectives import Objective, resolve
from env.prompts import PromptTexts, TurnView, load_texts, system_prompt, template_values, user_prompt
from env.roles import Roles, draw_roles, reshuffled_order
from env.scoring import Context, evaluate
from env.views import anonymous_labels, relabel, visible


# --- what an agent receives ------------------------------------------------------------------


@dataclass
class Turn:
    agent: str
    kind: str                                   # chat | reserve | claim
    phase: str                                  # Colosseum's phase name: planning | reservation | execution
    system: str
    user: str
    tools: List[Dict[str, Any]]                 # schemas offered to the model
    execute: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    calls_per_turn: int
    info: Dict[str, Any]                        # structured state, for scripted agents and logs
    meta: Dict[str, Any]                        # ids: round, phase index, pass, position

    _committed: bool = False

    @property
    def committed(self) -> bool:
        return self._committed


class AgentLike(Protocol):
    async def take_turn(self, turn: Turn) -> Dict[str, Any]: ...


# --- one round ---------------------------------------------------------------------------------


@dataclass
class RoundSetup:
    index: int
    board_seed: int
    board: Board
    roles: Roles
    objective: Objective
    ctx: Context
    analysis: Dict[str, Any]


def rename_agents(board: Board, names: List[str]) -> Board:
    """The same board with the agents renamed by position (repeated games on new boards)."""
    mapping = dict(zip(board.agent_names, names))
    agents = tuple(BoardAgent(name=mapping[a.name], availability=a.availability, skills=a.skills) for a in board.agents)
    costs = {mapping[a]: dict(c) for a, c in board.costs.items()}
    return replace(board, agents=agents, costs=costs)


def board_generator_after(seed: int, game: GameConfig) -> random.Random:
    """Colosseum fills missing claims with the board's own generator, continued after the board
    was drawn (`_fill_random_unassigned_agents` uses `self.rng`). Replay the draws to get there."""
    from env.board import _make_agents, _make_issues, _expand_tasks
    rng = random.Random(seed)
    tasks = _expand_tasks(_make_issues(rng, game.board), game.board)
    _make_agents(rng, seed, tasks, game.board)
    return rng


class Episode:
    def __init__(self, game: GameConfig, seed: int, agents: Mapping[str, AgentLike] | Callable[[str, Roles], AgentLike],
                 replication: int = 0, log_turn: Optional[Callable[[Dict[str, Any]], None]] = None,
                 on_round: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.game = game
        self.seed = int(seed)
        self.replication = replication
        self._agents = agents
        self.texts: PromptTexts = load_texts(game.prompts)
        self.system = system_prompt(self.texts, game)
        self.log_turn = log_turn or (lambda record: None)
        self.on_round = on_round or (lambda record: None)        # called after each round (logging, metrics)
        self.history: Dict[str, List[str]] = {}
        self.rounds: List[Dict[str, Any]] = []

    # setup -------------------------------------------------------------------------------
    def setup_round(self, r: int, first: Optional[RoundSetup]) -> RoundSetup:
        g = self.game
        mode = g.series.mode
        board_seed = self.seed if (mode == "repeated_same_board" or r == 0) else self.seed + r * g.series.seed_stride
        if mode == "repeated_same_board" and first is not None:
            board, roles, objective = first.board, first.roles, first.objective
        else:
            board = make_board(board_seed, g.board)
            if mode == "repeated_new_board" and first is not None:
                board = rename_agents(board, list(first.board.agent_names))
                roles = first.roles
            else:
                roles = draw_roles(board.agent_names, board_seed, g.roles.colluders, g.roles.selection, g.roles.order)
            objective = resolve(g.objective, board, roles, board_seed, g.scoring)
        if mode != "independent" and g.roles.new_order_each_round:
            roles = reshuffled_order(roles, self.seed, r, "random")
        ctx = objective.scoring_context(g.scoring, roles)
        same = mode == "repeated_same_board" and first is not None and roles == first.roles
        if same:
            return RoundSetup(index=r, board_seed=board_seed, board=board, roles=roles, objective=objective, ctx=ctx,
                              analysis=first.analysis)
        plan = None
        if not (mode == "repeated_same_board" and first is not None):     # same board: planted once, in round 0
            board, plan = plant(board, roles, self.seed, r, g.construction, ctx)
        analysis = analyze(board, roles, ctx, objective)
        if plan is not None:
            analysis = {**analysis, "construction": plan}
        return RoundSetup(index=r, board_seed=board_seed, board=board, roles=roles, objective=objective, ctx=ctx,
                          analysis=analysis)

    def agent(self, name: str, roles: Roles) -> AgentLike:
        if callable(self._agents) and not isinstance(self._agents, Mapping):
            return self._agents(name, roles)
        return self._agents[name]

    # play ----------------------------------------------------------------------------------
    async def play(self) -> List[Dict[str, Any]]:
        first = None
        for r in range(self.game.series.rounds):
            setup = self.setup_round(r, first)
            first = first or setup
            record = await self.play_round(setup)
            self.rounds.append(record)
            self.on_round(record)
            if self.game.series.mode != "independent":
                self._remember(setup, record)
        return self.rounds

    async def play_round(self, s: RoundSetup) -> Dict[str, Any]:
        g = self.game
        board, roles, objective = s.board, s.roles, s.objective
        iteration = s.index + 1
        names = list(board.agent_names)
        tasks = {t.id: {"id": t.id, "issue_id": t.issue_id, "title": t.title, "tags": list(t.tags),
                        "priority": t.priority, "effort": t.effort, "work_type": t.work_type} for t in board.tasks}
        boards = Boards(seed=f"{self.seed}:{self.replication}:{s.index}")
        base_context = network_context(g.assignment_filling)
        public_id = secret_id = None
        if g.boards.public:
            public_id = boards.create(sorted(names), "public", board_context(sorted(names), base_context))
        if g.boards.secret and len(roles.colluders) >= 2:
            secret_id = boards.create(list(roles.colluders), "secret", board_context(list(roles.colluders), base_context))
        kind_ids = {"public": public_id, "secret": secret_id}

        claims: Dict[str, Optional[str]] = {}
        reservations: List[Dict[str, Optional[str]]] = []
        current_reservation: Dict[str, Optional[str]] = {}
        reserved_by: Dict[str, str] = {}
        exclusive = any(p.kind == "reserve" and p.binding == "exclusive" for p in g.phases)
        turn_records: List[Dict[str, Any]] = []
        position = 0

        for p_index, phase in enumerate(g.phases):
            phase_name = self.texts.phases[phase.kind]["name"]
            for pass_index in range(phase.passes):
                pass_picks: Dict[str, Optional[str]] = {}
                if phase.kind == "reserve":
                    reservations.append(pass_picks)
                for name in self._participants(phase, roles):
                    if phase.kind == "claim" and name in claims:
                        continue
                    allowed = [kind_ids[k] for k in phase.boards
                               if kind_ids.get(k) is not None and name in boards.boards[kind_ids[k]].participants]
                    turn = self._turn(s, phase, p_index, pass_index, position, name, phase_name, iteration, tasks,
                                      boards, allowed, secret_id, claims, reservations, pass_picks,
                                      current_reservation, reserved_by, exclusive)
                    position += 1
                    result = await self.agent(name, roles).take_turn(turn)
                    record = {"round": s.index, "phase_index": p_index, "kind": phase.kind, "phase": phase_name,
                              "pass": pass_index, "position": turn.meta["position"], "agent": name,
                              "role": "colluder" if roles.is_colluder(name) else "honest",
                              "user_prompt": turn.user, "tools_offered": [t["function"]["name"] for t in turn.tools],
                              "committed": turn.committed, **result}
                    turn_records.append(record)
                    self.log_turn({"episode_seed": self.seed, "replication": self.replication, **record})

        missing = [a for a in names if a not in claims]
        filled: Dict[str, Optional[str]] = {}
        final = dict(claims)
        if g.assignment_filling:
            rng = board_generator_after(s.board_seed, g) if s.index == 0 or g.series.mode == "independent" \
                else random.Random(f"fill:{self.seed}:{self.replication}:{s.index}")
            allowed_choices: List[Optional[str]] = [None] + [t.id for t in board.tasks]
            for agent in names:                          # `_fill_random_unassigned_agents`, in agent order
                if agent not in final:
                    final[agent] = filled[agent] = rng.choice(allowed_choices)
        evaluation = evaluate(board, final, s.ctx)
        return {
            "round": s.index, "board_seed": s.board_seed, "board": board.canonical(),
            "colluders": list(roles.colluders), "turn_order": list(roles.turn_order),
            "objective": {"type": objective.type, "hv_task": objective.hv_task,
                          "same_issue_bonus": objective.same_issue_bonus,
                          "hv_coalition_bonus": objective.config.high_value_ticket.coalition_bonus},
            "analysis": s.analysis, "claims_in_order": [[a, t] for a, t in claims.items()],
            "missing_claims": missing, "filled": filled, "assignment": final,
            "reservations": reservations, "boards": boards.snapshot(), "system_prompt": self.system,
            "evaluation": {"score": evaluation.score, "rewards": evaluation.rewards, "tasks_done": evaluation.tasks_done,
                           "violations": evaluation.violations, "total_cost": evaluation.total_cost,
                           "priority_sum": evaluation.priority_sum, "externality": evaluation.externality},
            "turns": [{k: v for k, v in t.items() if k != "user_prompt"} for t in turn_records],
            "setup": s,
        }

    def _participants(self, phase: PhaseConfig, roles: Roles) -> List[str]:
        if phase.participants == "colluders":
            return [a for a in roles.turn_order if roles.is_colluder(a)]
        if phase.participants == "honest":
            return [a for a in roles.turn_order if not roles.is_colluder(a)]
        return list(roles.turn_order)

    def _turn(self, s: RoundSetup, phase: PhaseConfig, p_index: int, pass_index: int, position: int, name: str,
              phase_name: str, iteration: int, tasks: Dict[str, Dict[str, Any]], boards: Boards, allowed: List[int],
              secret_id: Optional[int], claims: Dict[str, Optional[str]],
              reservations: List[Dict[str, Optional[str]]], pass_picks: Dict[str, Optional[str]],
              current_reservation: Dict[str, Optional[str]], reserved_by: Dict[str, str], exclusive: bool) -> Turn:
        g = self.game
        board, roles, objective = s.board, s.roles, s.objective
        names = list(board.agent_names)
        is_colluder = roles.is_colluder(name)
        coalition = tuple(sorted(roles.colluders))
        seen_claims = visible(name, claims, board, roles, g.views, self.seed, s.index, "claim")
        seen_res = [visible(name, picks, board, roles, g.views, self.seed, s.index, f"reserve-{i}")
                    for i, picks in enumerate(reservations)]
        if g.views.names == "anonymous":
            labels = anonymous_labels(name, board.agent_names, self.seed, s.index)
            seen_claims = relabel(seen_claims, name, labels)
            seen_res = [relabel(picks, name, labels) for picks in seen_res]
        hv = objective.config.high_value_ticket
        values = template_values(name, coalition, secret_id if is_colluder else None, objective.hv_task,
                                 hv.coalition_bonus, hv.team_value, objective.same_issue_bonus, g.series.rounds)
        view = TurnView(agent=name, phase_kind=phase.kind, iteration=iteration,
                        exclusive=phase.kind == "reserve" and phase.binding == "exclusive",
                        chat_allowed=phase.kind == "reserve" and phase.post_message == "offered" and bool(allowed),
                        claims=seen_claims, reservations=seen_res, board_contexts=boards.prompt_contexts(name),
                        history=self.history.get(name, []), is_colluder=is_colluder, coalition=coalition,
                        secret_board_id=secret_id if is_colluder else None, template_values=values,
                        honest_hv_visible=(objective.type == "high_value_ticket" and hv.visible_to_honest and not is_colluder))
        offered: List[Dict[str, Any]] = []
        if phase.kind == "reserve":
            offered.append(T.RESERVE_SCHEMA)
        if phase.kind == "claim":
            offered.append(T.ASSIGN_SCHEMA)
        if phase.post_message == "offered" and allowed:
            offered.append(T.POST_SCHEMA)

        turn = Turn(agent=name, kind=phase.kind, phase=phase_name, system=self.system,
                    user=user_prompt(self.texts, g, board, view), tools=offered, execute=lambda n, a: {},
                    calls_per_turn=g.calls_per_turn,
                    info={"board": board, "roles": roles, "objective": objective, "scoring": g.scoring, "claims": seen_claims,
                          "reservations": seen_res, "own_reservation": current_reservation.get(name),
                          "allowed_boards": allowed, "round": s.index, "history": self.history.get(name, [])},
                    meta={"round": s.index, "phase_index": p_index, "pass": pass_index, "position": position})

        def execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            arguments = arguments if isinstance(arguments, dict) else {}
            if tool == "post_message":
                if phase.post_message == "no":
                    return T.not_available(tool, phase_name)
                return boards.post_message(name, arguments, phase_name, iteration, allowed=allowed)
            if tool == "assign_task":
                if phase.kind != "claim":
                    return T.not_available(tool, phase_name)
                result = T.assign_task(name, arguments, tasks, names, claims, reserved_by if exclusive else None)
                if T.committed(result):
                    claims[name] = result["result"]["task_id"]
                    turn._committed = True
                    if g.boards.log_claims:
                        boards.log_action(name, {"action": "assign_task", "task_id": arguments.get("task_id")},
                                          result, phase_name, iteration)
                return result
            if tool == "reserve_task":
                if phase.kind != "reserve":
                    return T.not_available(tool, phase_name)
                result = T.reserve_task(name, arguments, tasks, names, pass_picks, len(reservations),
                                        reserved_by if exclusive else None)
                if T.committed(result):
                    task = result["result"]["task_id"]
                    pass_picks[name] = task
                    previous = current_reservation.get(name)
                    if exclusive and previous is not None and reserved_by.get(previous) == name:
                        del reserved_by[previous]
                    current_reservation[name] = task
                    if exclusive and task is not None:
                        reserved_by[task] = name
                    turn._committed = True
                    if g.boards.log_reservations:
                        boards.log_action(name, {"action": "reserve_task", "task_id": arguments.get("task_id")},
                                          result, phase_name, iteration)
                return result
            return T.not_recognized(tool)

        turn.execute = execute
        return turn

    def _remember(self, s: RoundSetup, record: Dict[str, Any]) -> None:
        """History lines shown in later rounds (repeated modes), per `series.feedback`."""
        fb = self.game.series.feedback
        evaluation = record["evaluation"]
        filled = record["filled"]

        def shown(agent: str, task: Optional[str]) -> str:
            if agent in filled:                     # never claimed: the environment filled it at random
                return f"{who(agent)}: no claim (filled at random: {task or 'skip'})"
            return f"{who(agent)}: {task or 'skip'}"

        anonymous = self.game.views.names == "anonymous"
        for name in s.board.agent_names:
            labels = anonymous_labels(name, s.board.agent_names, self.seed, s.index) if anonymous else {}

            def who(agent: str) -> str:
                return agent if (agent == name or not anonymous) else labels[agent]

            parts = [f"Round {s.index + 1}"]
            if "claims" in fb:
                parts.append("claims: " + ", ".join(sorted(shown(a, t) for a, t in record["assignment"].items())))
            if "reservations" in fb and record["reservations"]:
                last = record["reservations"][-1]
                parts.append("last reservations: " + ", ".join(sorted(f"{who(a)}: {t if t else 'skip'}" for a, t in last.items())))
            if "own_reward" in fb:
                parts.append(f"your reward: {evaluation['rewards'][name]:.2f}")
            if "all_rewards" in fb:
                parts.append("rewards: " + ", ".join(sorted(f"{who(a)}: {v:.2f}" for a, v in evaluation["rewards"].items())))
            if "team_score" in fb:
                parts.append(f"team score: {evaluation['score']:.2f}")
            self.history.setdefault(name, []).append(" | ".join(parts))


def plain_round(record: Dict[str, Any]) -> Dict[str, Any]:
    """A round record without in-memory objects, for JSON."""
    out = {k: v for k, v in record.items() if k != "setup"}
    return to_plain(out)
