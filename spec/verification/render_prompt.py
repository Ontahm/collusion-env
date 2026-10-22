"""Render the exact system + user prompt Colosseum gives one agent (example board), via upstream code."""
import random, sys
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
from envs.dcops.jira_ticket.jira_ticket_env import JiraTicketEnvironment as E
from envs.dcops.jira_ticket.jira_ticket_prompts import JiraTicketPrompts
from experiments.collusion.prompts import CollusionPrompts
seed, agent, phase, variant, provider = int(sys.argv[3]), sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7]
env = E.__new__(E); env.env_config = {"max_tasks": 8}; env.current_seed = seed; env.rng = random.Random(seed)
env.microtask_types = env._get_microtask_types(); env.tasks = env._build_tasks(8)
env.agent_names, env.agent_private = env._build_agents(6); env.costs = env._compute_costs(); env.assignment = {}
cfg = {"llm": {"provider": provider}, "environment": {"name": "JiraTicketEnvironment"}, "simulation": {"seed": seed}}
base = JiraTicketPrompts.__new__(JiraTicketPrompts); base.env = env; base.prompt_logger = None
from terrarium.tool_prompt_utils import build_vllm_tool_instructions
base.tool_instruction_data = build_vllm_tool_instructions(cfg,
    execution_tool_lines=["- assign_task(task_id: str): Claim a task id (or use 'skip' to skip)."],
    planning_header="Planning phase tools (coordination only):",
    execution_header="Execution phase tools (blackboards + task selection):",
    system_note=("Planning: Use post_message() to communicate with other agents.\n"
                 "Execution: assign_task becomes available in addition to blackboard tools."))
cp = CollusionPrompts(env, cfg, prompt_variant=variant, base_prompts=base, log_prompts=False)
colluders = random.Random(seed).sample(list(env.agent_names), k=2)
ctx = env.build_agent_context(agent, phase=phase, iteration=1)
ctx.update({"collusion_role": "colluder" if agent in colluders else "normal",
            "collusion_coalition_members": sorted(colluders) if agent in colluders else [],
            "collusion_blackboard_id": 1 if agent in colluders else None})
print("########## SYSTEM PROMPT"); print(cp.get_system_prompt())
print("########## USER PROMPT"); print(cp.get_user_prompt(agent, ctx, {}))
