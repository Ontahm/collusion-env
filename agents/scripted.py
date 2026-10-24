"""Scripted agents: fixed policies, no model. For tests and for checking a study end to end
before spending model budget. They act through the same tool calls as LLM agents.

Policies (`policy` in the model config):
  greedy   every agent takes, among the tasks still free in what it sees, the one with its best
           reward (or skips if none is positive); reserves the same task; in a chat phase posts one
           line naming that task on its first allowed board.
  colluder honest agents are greedy; colluders follow the objective in the simplest way:
           high_value_ticket: take the ticket if it is free, else greedy;
           same_issue: the second colluder joins the issue it sees its partner on, else greedy.
  oracle_pair   honest agents are greedy; each colluder takes its part of the pair of free tasks
           (self, partner) with the highest summed reward. If it sees its partner's claim, it
           takes its best task given that claim. Upper bound for coalition_reward collusion.
  team_optimal  every agent takes its task in the team optimum (exact_optimum) if it is still
           free, else greedy. The team-player floor.
  jackpot  jackpot boards (env/jackpot.py): honest agents greedy; A points (claims its own task on
           the jackpot's issue); B reads A's claim if it sees it (A1 -> T1, A2 -> T2, a blocked T -> the
           other T), else takes the first-listed of T1/T2 (the "cost reader": T1 and T2 cost the same).
  jackpot_random_a   as jackpot, but A picks A1 or A2 at random (seeded): no information sent.
  jackpot_block      as jackpot, but A blocks: it claims the decoy itself.
These are test doubles, not models of behaviour.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import itertools

from env.game import Turn
from env.scoring import evaluate, exact_optimum


def _reward(info: Dict[str, Any], agent: str, task: str) -> float:
    board = info["board"]
    ctx = info["objective"].scoring_context(_scoring(info), info["roles"])
    return evaluate(board, {agent: task}, ctx).rewards[agent]


def _scoring(info: Dict[str, Any]):
    from env.scoring import ScoringConfig
    return info.get("scoring") or ScoringConfig()


def _taken(info: Dict[str, Any]) -> set:
    return {t for t in info["claims"].values() if t not in (None, "None")}


def greedy_choice(turn: Turn) -> Optional[str]:
    info = turn.info
    taken = _taken(info)
    best, best_value = None, 0.0
    for task in info["board"].tasks:
        if task.id in taken:
            continue
        value = _reward(info, turn.agent, task.id)
        if value > best_value:
            best, best_value = task.id, value
    return best


def colluder_choice(turn: Turn) -> Optional[str]:
    info = turn.info
    roles, objective, board = info["roles"], info["objective"], info["board"]
    if not roles.is_colluder(turn.agent):
        return greedy_choice(turn)
    taken = _taken(info)
    if objective.type == "high_value_ticket" and objective.hv_task and objective.hv_task not in taken:
        partner_has = any(info["claims"].get(p) == objective.hv_task for p in roles.partner(turn.agent))
        if not partner_has:
            return objective.hv_task
    if objective.type == "same_issue":
        for partner in roles.partner(turn.agent):
            seen = info["claims"].get(partner)
            if seen and seen != "None":
                issue = seen if "::" not in seen else board.task(seen).issue_id
                options = [t.id for t in board.tasks if t.issue_id == issue and t.id not in taken]
                if options:
                    return max(options, key=lambda t: _reward(info, turn.agent, t))
    return greedy_choice(turn)


def _ctx(info: Dict[str, Any]):
    return info["objective"].scoring_context(_scoring(info), info["roles"])


def oracle_pair_choice(turn: Turn) -> Optional[str]:
    info = turn.info
    roles, board, claims = info["roles"], info["board"], info["claims"]
    if not roles.is_colluder(turn.agent):
        return greedy_choice(turn)
    ctx = _ctx(info)
    me = turn.agent
    pending = [p for p in roles.partner(me) if p not in claims]
    if not pending:          # partners have acted: their rewards are fixed, so take my best free task
        return greedy_choice(turn)
    free = [t.id for t in board.tasks if t.id not in _taken(info)]
    partner = pending[0]                  # plan with the next partner to act (two-colluder case)
    best, best_value = None, float("-inf")
    for mine, theirs in itertools.product(free + [None], free + [None]):
        if mine is not None and mine == theirs:
            continue
        rewards = evaluate(board, {me: mine, partner: theirs}, ctx).rewards
        value = rewards[me] + rewards[partner]
        if value > best_value:
            best, best_value = mine, value
    return best


def team_optimal_choice(turn: Turn) -> Optional[str]:
    info = turn.info
    optimum = exact_optimum(info["board"], _ctx(info))
    mine = optimum.assignment.get(turn.agent) if optimum else None
    if mine is not None and mine not in _taken(info):
        return mine
    return greedy_choice(turn)


def _jackpot_plan(info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    plan = info.get("construction") or {}
    return plan if plan.get("mode") == "jackpot" else None


def _jackpot(turn: Turn, a_rule: str) -> Optional[str]:
    info = turn.info
    plan = _jackpot_plan(info)
    if plan is None or turn.agent not in (plan["A"], plan["B"]):
        return greedy_choice(turn)
    if turn.agent == plan["A"]:
        jackpot = info["objective"].hv_task                    # A knows the coin
        if a_rule == "random":
            import random
            return random.Random(f"random-a:{info['board'].seed}").choice([plan["A1"], plan["A2"]])
        if a_rule == "block":
            return plan["T2"] if jackpot == plan["T1"] else plan["T1"]
        return plan["A1"] if jackpot == plan["T1"] else plan["A2"]
    seen = info["claims"].get(plan["A"])                      # B: only what it is shown
    read = {plan["A1"]: plan["T1"], plan["A2"]: plan["T2"], plan["T1"]: plan["T2"], plan["T2"]: plan["T1"]}
    return read.get(seen, plan["T1"])


def jackpot_choice(turn: Turn) -> Optional[str]:
    return _jackpot(turn, "point")


def jackpot_random_a_choice(turn: Turn) -> Optional[str]:
    return _jackpot(turn, "random")


def jackpot_block_choice(turn: Turn) -> Optional[str]:
    return _jackpot(turn, "block")


POLICIES = {"greedy": greedy_choice, "colluder": colluder_choice,
            "oracle_pair": oracle_pair_choice, "team_optimal": team_optimal_choice,
            "jackpot": jackpot_choice, "jackpot_random_a": jackpot_random_a_choice,
            "jackpot_block": jackpot_block_choice}


class ScriptedAgent:
    def __init__(self, name: str, policy: str = "greedy"):
        if policy not in POLICIES:
            raise ValueError(f"scripted policy {policy!r}: expected one of {sorted(POLICIES)}")
        self.name = name
        self.choose = POLICIES[policy]

    async def take_turn(self, turn: Turn) -> Dict[str, Any]:
        calls: List[Dict[str, Any]] = []
        choice = self.choose(turn)
        if turn.kind == "chat":
            if turn.info["allowed_boards"]:
                args = {"message": f"I plan to take {choice or 'skip'}.", "blackboard_id": turn.info["allowed_boards"][0]}
                calls.append({"tool": "post_message", "arguments": args, "result": turn.execute("post_message", args)})
        else:
            tool = "reserve_task" if turn.kind == "reserve" else "assign_task"
            args = {"task_id": choice or "skip"}
            calls.append({"tool": tool, "arguments": args, "result": turn.execute(tool, args)})
        return {"model_calls": 0, "tool_calls": calls, "usage": {}, "error": None, "final_text": None}
