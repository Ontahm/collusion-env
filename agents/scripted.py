"""Scripted agents: fixed policies, no model. For tests and for checking a study end to end
before spending model budget. They act through the same tool calls as LLM agents.

Policies (`policy` in the model config):
  greedy   every agent takes, among the tasks still free in what it sees, the one with its best
           reward (or skips if none is positive); reserves the same task; in a chat phase posts one
           line naming that task on its first allowed board.
  colluder honest agents are greedy; colluders follow the objective in the simplest way:
           high_value_ticket: take the ticket if it is free, else greedy;
           same_issue: the second colluder joins the issue it sees its partner on, else greedy.
These are test doubles, not models of behaviour.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from env.game import Turn
from env.scoring import evaluate


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


POLICIES = {"greedy": greedy_choice, "colluder": colluder_choice}


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
