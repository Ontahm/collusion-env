"""Reference prompts rendered by Colosseum's own code, for the tests of env/prompts.py.

    python -I prompt_fixtures.py <terrarium dir> <colosseum dir> <out.json.gz>

For seeds 1-4, boards of 8 and 15 tasks, every agent, and four settings (planning / claiming,
`simple` / `control` variant, native / text tool calling), the system and user prompts come from
`JiraTicketPrompts` wrapped in `CollusionPrompts`, exactly as `experiments/collusion/run.py` sets
them up. The state is built with upstream objects too: Terrarium's `Megaboard` with the public
board (sorted participants) and the secret board (colluders), opened by their "context" events as
`generate_comm_network` does; two planning messages; and, for claiming, the claims of the agents
who acted before, executed by `JiraTicketTools.execute_action`, which also logs them on the boards.
Event ids are replaced by fixed strings (Terrarium draws random UUIDs), and stored with the state.
"""

import gzip
import json
import random
import sys
import warnings

sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
warnings.filterwarnings("ignore")
from envs.dcops.jira_ticket.jira_ticket_env import JiraTicketEnvironment as E  # noqa: E402
from envs.dcops.jira_ticket.jira_ticket_prompts import JiraTicketPrompts  # noqa: E402
from envs.dcops.jira_ticket.jira_ticket_tools import JiraTicketTools  # noqa: E402
from experiments.collusion.prompts import CollusionPrompts  # noqa: E402
from terrarium.blackboard import Megaboard, format_blackboard_events_for_prompt  # noqa: E402
from terrarium.tool_prompt_utils import build_vllm_tool_instructions  # noqa: E402


def make_env(seed, max_tasks, filling=True):
    env = E.__new__(E)
    env.env_config = {"max_tasks": max_tasks, "assignment_filling": filling}
    env.full_config = {"environment": env.env_config}
    env.current_seed = seed
    env.rng = random.Random(seed)
    env.microtask_types = env._get_microtask_types()
    env.tasks = env._build_tasks(max_tasks=max_tasks)
    env.agent_names, env.agent_private = env._build_agents(6)
    env.costs = env._compute_costs()
    env.assignment = {}
    return env


def base_prompts(env, provider):
    base = JiraTicketPrompts.__new__(JiraTicketPrompts)
    base.env, base.prompt_logger = env, None
    base.tool_instruction_data = build_vllm_tool_instructions(
        {"llm": {"provider": provider}},
        execution_tool_lines=["- assign_task(task_id: str): Claim a task id (or use 'skip' to skip)."],
        planning_header="Planning phase tools (coordination only):",
        execution_header="Execution phase tools (blackboards + task selection):",
        system_note=("Planning: Use post_message() to communicate with other agents.\n"
                     "Execution: assign_task becomes available in addition to blackboard tools."))
    return base


def main():
    cases = []
    for seed in range(1, 5):
        for max_tasks in (8, 15):
            for phase, variant, provider in (("planning", "simple", "openai"), ("execution", "simple", "openai"),
                                              ("planning", "control", "vllm"), ("execution", "control", "vllm")):
                env = make_env(seed, max_tasks)
                rng = random.Random(seed)                       # as run.py: colluders, then shuffle
                colluders = [str(x) for x in rng.sample(list(env.agent_names), k=2)]
                order = list(env.agent_names)
                rng.shuffle(order)
                mb = Megaboard()
                base_context = env.get_network_context()
                public = mb.add_blackboard(sorted(env.agent_names))
                mb.post_system_message(public, kind="context",
                                       payload={"message": env.format_blackboard_context(sorted(env.agent_names), base_context)})
                secret = mb.add_blackboard(list(colluders))
                mb.post_system_message(secret, kind="context",
                                       payload={"message": env.format_blackboard_context(colluders, base_context)})
                mb.post(public, order[0], "communication", {"content": f"I plan to take {list(env.tasks)[0]}."},
                        phase="planning", iteration=1)
                mb.post(secret, colluders[0], "communication", {"content": "Let us coordinate privately."},
                        phase="planning", iteration=1)
                claims = []
                if phase == "execution":
                    tools = JiraTicketTools(mb)
                    task_ids = list(env.tasks)
                    for k, agent in enumerate(order[:3]):                     # three earlier claims
                        task = "skip" if k == 1 else task_ids[(seed + 2 * k) % len(task_ids)]
                        result = tools.execute_action(agent, {"action": "assign_task", "task_id": task},
                                                      phase="execution", iteration=1,
                                                      env_state={"tasks": env.tasks, "assignment": env.assignment,
                                                                 "agent_names": env.agent_names})
                        env.assignment.update(result["result"]["state_updates"]["assignment"])
                        claims.append([agent, task])
                for b in mb.blackboards:                                      # fixed ids, fixed timestamps
                    for i, ev in enumerate(b.logs):
                        ev["id"], ev["ts"] = f"evt-{b.blackboard_id}-{i}", 0.0
                prompts = CollusionPrompts(env, {"experiment": {}}, prompt_variant=variant,
                                           base_prompts=base_prompts(env, provider), log_prompts=False)
                for agent in order[3:] if phase == "execution" else order:
                    ctx = dict(env.build_agent_context(agent, phase=phase, iteration=1))
                    is_c = agent in colluders
                    ctx.update({"collusion_role": "colluder" if is_c else "normal",
                                "collusion_coalition_members": sorted(colluders) if is_c else [],
                                "collusion_blackboard_id": secret if is_c else None})
                    bb_ids = sorted(mb.get_agent_blackboards(agent), key=int)
                    bb_context = {b: format_blackboard_events_for_prompt(mb.get(int(b), agent)) for b in bb_ids}
                    cases.append({
                        "seed": seed, "tasks": max_tasks, "phase": phase, "variant": variant, "provider": provider,
                        "agent": agent, "colluders": colluders, "turn_order": order, "claims": claims,
                        "boards": [{"participants": list(b.participants), "events": b.logs} for b in mb.blackboards],
                        "system": prompts.get_system_prompt(), "user": prompts.get_user_prompt(agent, ctx, bb_context),
                    })
    with gzip.open(sys.argv[3], "wt", encoding="utf-8") as f:
        json.dump({"source": "Colosseum b077fe7 / Terrarium v0.1.1", "cases": cases}, f)


if __name__ == "__main__":
    main()
