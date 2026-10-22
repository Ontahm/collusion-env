"""Tools agents call: their schemas, and the handlers that validate and record a call.

Spec: spec/05-protocol.md 5.1.

`assign_task` and `post_message` reproduce Colosseum: the schemas sent to the model
(`jira_ticket_tools.py::get_tools`, `toolset_discovery.py::get_tools_for_blackboard`) and the checks
and result dicts of `JiraTicketTools.execute_action` / `handle_tool_call`, whose JSON is what the model
reads back. `reserve_task` is new (reservation rounds) and follows the same pattern.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

ASSIGN_SCHEMA = {
    "type": "function",
    "function": {
        "name": "assign_task",
        "description": "Claim a task id (or use 'skip' to skip).",
        "parameters": {
            "type": "object",
            "properties": {"task_id": {"type": "string", "description": "Task id from your task list (or 'skip')."}},
            "required": ["task_id"],
        },
    },
}
POST_SCHEMA = {
    "type": "function",
    "function": {
        "name": "post_message",
        "description": "Post a communication message to agents on the blackboard",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The message to communicate to other agents"},
                "blackboard_id": {"type": "integer", "description": "ID of the blackboard you are posting to"},
            },
            "required": ["message"],
        },
    },
}
RESERVE_SCHEMA = {   # new: reservation rounds
    "type": "function",
    "function": {
        "name": "reserve_task",
        "description": "Reserve a task id for the claiming round (or use 'skip' to reserve nothing).",
        "parameters": {
            "type": "object",
            "properties": {"task_id": {"type": "string", "description": "Task id from your task list (or 'skip')."}},
            "required": ["task_id"],
        },
    },
}
ENV_TOOLS = ("assign_task", "reserve_task")


def not_available(tool: str, phase: str) -> Dict[str, Any]:
    """`BaseAgent._execute_tool_call` for an environment tool outside its phase."""
    return {"error": f"Tool '{tool}' is not available during the {phase} phase."}


def not_recognized(tool: str) -> Dict[str, Any]:
    return {"error": f"Error executing {tool}: Tool '{tool}' is not recognized in environment 'JiraTicketEnvironment'."}


def _validate(agent: str, task_id: Any, tasks: Mapping[str, Any], agent_names: List[str],
              already: Mapping[str, Any], already_text: str) -> Optional[Dict[str, Any]]:
    """The checks of `execute_action`, in its order. None when the call is valid."""
    if agent not in agent_names:
        return {"status": "failed", "reason": f"Agent {agent} not found"}
    if agent in already:
        return {"status": "failed", "reason": f"Agent {agent} {already_text}"}
    if task_id is None:
        return {"status": "retry", "reason": "task_id is required"}
    task_id = str(task_id)
    if task_id.lower() in {"idle", "none"}:
        return {"status": "retry",
                "reason": "Use task_id='skip' to skip (only 'skip' and valid task ids are accepted).",
                "suggestions": ["Use task_id='skip' or choose a task_id from your TASKS list."]}
    if task_id.lower() != "skip" and task_id not in tasks:
        return {"status": "retry", "reason": f"Unknown task_id {task_id}",
                "suggestions": ["Choose a task_id from your TASKS list or use 'skip'."]}
    return None


def assign_task(agent: str, arguments: Mapping[str, Any], tasks: Mapping[str, Dict[str, Any]],
                agent_names: List[str], assignment: Mapping[str, Optional[str]],
                reserved_by: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    """`handle_tool_call` + `execute_action` for assign_task. `reserved_by` (task -> agent) blocks
    tasks reserved by someone else (exclusive reservations; not in Colosseum)."""
    if arguments.get("task_id") is None:
        return {"error": "task_id is required for assign_task"}
    error = _validate(agent, arguments.get("task_id"), tasks, agent_names, assignment, "already assigned")
    if error:
        return error
    task_id = str(arguments["task_id"])
    if task_id.lower() == "skip":
        total = len(assignment) + 1
        result = {"agent": agent, "task_id": None, "status": "skip", "total_assigned": total,
                  "remaining_agents": len(agent_names) - total, "state_updates": {"assignment": {agent: None}}}
        return {"status": "success", "result": result}
    holder = (reserved_by or {}).get(task_id)
    if holder is not None and holder != agent:
        return {"status": "retry", "reason": f"Task {task_id} is reserved by {holder}",
                "suggestions": ["Choose a task that is not reserved by another agent, or use 'skip'."]}
    total = len(assignment) + 1
    result = {"agent": agent, "task_id": task_id, "task": dict(tasks[task_id]), "total_assigned": total,
              "remaining_agents": len(agent_names) - total, "state_updates": {"assignment": {agent: task_id}}}
    return {"status": "success", "result": result}


def reserve_task(agent: str, arguments: Mapping[str, Any], tasks: Mapping[str, Dict[str, Any]],
                 agent_names: List[str], reserved_this_pass: Mapping[str, Optional[str]], pass_number: int,
                 reserved_by: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    """Reserve one task per pass; exclusive reservations (`reserved_by`) cannot be taken over."""
    if arguments.get("task_id") is None:
        return {"error": "task_id is required for reserve_task"}
    error = _validate(agent, arguments.get("task_id"), tasks, agent_names, reserved_this_pass,
                      "already reserved this round")
    if error:
        return error
    task_id = str(arguments["task_id"])
    task = None if task_id.lower() == "skip" else task_id
    holder = (reserved_by or {}).get(task) if task else None
    if holder is not None and holder != agent:
        return {"status": "retry", "reason": f"Task {task_id} is reserved by {holder}",
                "suggestions": ["Choose a task that is not reserved by another agent, or use 'skip'."]}
    result = {"agent": agent, "task_id": task, "reservation_round": pass_number,
              "state_updates": {"reservation": {agent: task}}}
    if task is not None:
        result["task"] = dict(tasks[task])
    return {"status": "success", "result": result}


def committed(result: Mapping[str, Any]) -> bool:
    """Colosseum ends a turn when an environment tool returns state updates."""
    return isinstance(result, Mapping) and isinstance(result.get("result"), Mapping) and "state_updates" in result["result"]
