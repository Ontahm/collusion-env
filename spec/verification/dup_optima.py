"""How often the exact optimum (Colosseum solver) contains a duplicate claim or a skip."""
import random, sys
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
from envs.dcops.jira_ticket.jira_ticket_env import JiraTicketEnvironment as E
from experiments.collusion import compute_jira_optimal as O
for m in [int(x) for x in sys.argv[3].split(",")]:
    dup = skip = 0; N = int(sys.argv[4])
    for s in range(1, N + 1):
        env = E.__new__(E); env.env_config = {"max_tasks": m}; env.current_seed = s; env.rng = random.Random(s)
        env.microtask_types = env._get_microtask_types(); env.tasks = env._build_tasks(m)
        env.agent_names, env.agent_private = env._build_agents(6); env.costs = env._compute_costs()
        opt = O.solve_optimal_assignment(instance=O.JiraInstance(list(env.agent_names), list(env.tasks), env.tasks, env.costs),
                                         weights=O.JiraWeights(20.0, 20.0, 20.0))
        dup += opt.violations > 0; skip += any(v is None for v in opt.assignment.values())
    print(f"tasks={m:2d}: optimum has a duplicate on {dup}/{N} boards, a skip on {skip}/{N}")
