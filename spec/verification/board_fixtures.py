"""Reference boards from Colosseum's own code, for the bit-for-bit test of env/board.py.

    python -I board_fixtures.py <terrarium dir> <colosseum dir> <out.json>

For every (number of tasks, number of agents) case below and every seed, the board is built with
the upstream Jira environment, serialised in the canonical form defined here, and hashed
(SHA-256). Two full boards are also stored, so a failing test can show a readable difference.

Canonical form (the environment's tests must produce exactly the same):
    tasks : [[id, issue_id, title, [tags...], priority, effort, work_type], ...]  generation order
    agents: [[name, availability, [[tag, level], ...]], ...]                     agent order,
                                                                                   skills in draw order
    costs : [[cost of agent a for task t, for t in task order], for a in agent order]
JSON with separators (",", ":"); floats as Python's repr, which round-trips exactly.
"""

import hashlib
import json
import platform
import random
import sys

sys.path.insert(0, sys.argv[1])            # vendor/terrarium
sys.path.insert(0, sys.argv[2])            # vendor/colosseum
from envs.dcops.jira_ticket.jira_ticket_env import JiraTicketEnvironment as E  # noqa: E402

CASES = [(1, 6), (5, 6), (8, 6), (10, 6), (12, 6), (15, 6), (20, 6), (8, 3)]
SEEDS = range(1, 201)
FULL = [(1, 8, 6), (2, 15, 6)]


def colosseum_board(seed: int, max_tasks: int, n_agents: int):
    # Same calls, same order, same generator as JiraTicketEnvironment.__init__.
    env = E.__new__(E)
    env.env_config = {"max_tasks": max_tasks}
    env.current_seed = seed
    env.rng = random.Random(seed)
    env.microtask_types = env._get_microtask_types()
    env.tasks = env._build_tasks(max_tasks=max_tasks)
    env.agent_names, env.agent_private = env._build_agents(n_agents)
    env.costs = env._compute_costs()
    return env


def canonical(env) -> dict:
    return {
        "tasks": [[t["id"], t["issue_id"], t["title"], list(t["tags"]), t["priority"], t["effort"], t["work_type"]]
                  for t in env.tasks.values()],
        "agents": [[a, env.agent_private[a]["availability"], [[k, v] for k, v in env.agent_private[a]["skills"].items()]]
                   for a in env.agent_names],
        "costs": [[env.costs[a][t] for t in env.tasks] for a in env.agent_names],
    }


def digest(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    out = {
        "source": "Colosseum b077fe7 / Terrarium v0.1.1 (f9dbb5b), unmodified JiraTicketEnvironment",
        "python": platform.python_version(),
        "seeds": [SEEDS.start, SEEDS.stop - 1],
        "digests": {f"tasks={m},agents={n}": [digest(canonical(colosseum_board(s, m, n))) for s in SEEDS]
                    for m, n in CASES},
        "full": {f"seed={s},tasks={m},agents={n}": canonical(colosseum_board(s, m, n)) for s, m, n in FULL},
    }
    with open(sys.argv[3], "w") as f:
        json.dump(out, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main()
