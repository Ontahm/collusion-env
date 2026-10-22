"""Build one Colosseum Jira board with the upstream code (no LLM) and print it as JSON."""
import json, random, sys
sys.path.insert(0, sys.argv[1])            # vendor/terrarium
sys.path.insert(0, sys.argv[2])            # vendor/colosseum
from envs.dcops.jira_ticket.jira_ticket_env import JiraTicketEnvironment as E
from experiments.collusion import compute_jira_optimal as O

seed, max_tasks, n_agents = int(sys.argv[3]), int(sys.argv[4]), 6
env = E.__new__(E)                          # skip __init__ (needs protocol/logging); call the real methods
env.env_config = {"max_tasks": max_tasks}
env.current_seed = seed
env.rng = random.Random(seed)
env.microtask_types = env._get_microtask_types()
env.tasks = env._build_tasks(max_tasks)
env.agent_names, env.agent_private = env._build_agents(n_agents)
env.costs = env._compute_costs()
env.tasks_done_bonus = env.priority_bonus = env.violation_penalty = 20.0   # code defaults

# colluders + turn order exactly as upstream run.py (_run_single, colluder_selection=random, agent_order=random)
rng = random.Random(seed)
colluders = [str(x) for x in rng.sample(list(env.agent_names), k=2)]
order = list(env.agent_names); rng.shuffle(order)

inst = O.JiraInstance(agent_names=list(env.agent_names), task_ids=list(env.tasks), tasks=env.tasks, costs=env.costs)
opt = O.solve_optimal_assignment(instance=inst, weights=O.JiraWeights(20.0, 20.0, 20.0))
_, rewards = env._rewards(opt.assignment)
print(json.dumps({
  "tasks": env.tasks, "agents": env.agent_private, "names": env.agent_names,
  "costs": {a: {t: round(c, 2) for t, c in env.costs[a].items()} for a in env.agent_names},
  "colluders": colluders, "turn_order": order,
  "optimum": {"joint_reward": round(opt.joint_reward, 2), "assignment": opt.assignment,
              "tasks_done": opt.tasks_done, "total_cost": round(opt.total_cost, 2),
              "priority_sum": opt.priority_sum, "agent_rewards": {a: round(r, 2) for a, r in rewards.items()}},
}, indent=1, default=str))
