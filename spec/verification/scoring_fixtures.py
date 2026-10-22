"""Reference scores, optima and regrets from Colosseum's own code, for the tests of env/scoring.py.

    python -I scoring_fixtures.py <terrarium dir> <colosseum dir> <out.json>

For boards of 8 and 15 tasks (seeds 1-40), Colosseum's code gives: the exact optimum
(`compute_jira_optimal.solve_optimal_assignment`), and for 4 random assignments per board (skips and
duplicates included) with a random turn order: the team score and agent rewards
(`JiraTicketEnvironment._evaluate_assignment` / `_rewards`), the best-response regret of
`metrics.compute_collusion_metrics`, and the sequential regret of `compute_sequential_regret`;
and once per board, the random fill of two missing claims (`_fill_random_unassigned_agents`).
"""

import json
import platform
import random
import sys

sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
from envs.dcops.jira_ticket.jira_ticket_env import JiraTicketEnvironment as E  # noqa: E402
from experiments.collusion import compute_jira_optimal as O  # noqa: E402
from experiments.collusion import compute_sequential_regret as S  # noqa: E402
from experiments.collusion.metrics import compute_collusion_metrics  # noqa: E402

W = O.JiraWeights(20.0, 20.0, 20.0)


def board(seed, max_tasks):
    env = E.__new__(E)
    env.env_config = {"max_tasks": max_tasks}
    env.current_seed = seed
    env.rng = random.Random(seed)
    env.microtask_types = env._get_microtask_types()
    env.tasks = env._build_tasks(max_tasks=max_tasks)
    env.agent_names, env.agent_private = env._build_agents(6)
    env.costs = env._compute_costs()
    env.tasks_done_bonus = env.priority_bonus = env.violation_penalty = 20.0
    env.optimal_k = min(len(env.agent_names), len(env.tasks))
    env.optimal_cost = 0.0
    env.max_joint_reward = env.compute_max_joint_reward()
    return env


def main():
    cases = []
    for max_tasks in (8, 15):
        for seed in range(1, 41):
            env = board(seed, max_tasks)
            opt = O.solve_optimal_assignment(
                instance=O.JiraInstance(list(env.agent_names), list(env.tasks), env.tasks, env.costs), weights=W)
            draws = random.Random(f"fixture:{seed}:{max_tasks}")
            # Random fill of missing claims (`_fill_random_unassigned_agents`), with the board's own
            # generator continued after the board was drawn: done first, before anything else.
            order = list(env.agent_names)
            draws.shuffle(order)
            partial = {a: draws.choice(list(env.tasks)) for a in order[:4]}
            env.assignment = dict(partial)
            env._fill_random_unassigned_agents()
            fill = {"partial": partial, "filled": dict(env.assignment)}
            samples = []
            for _ in range(4):
                task_ids = list(env.tasks)
                assignment = {a: (None if draws.random() < 0.15 else draws.choice(task_ids)) for a in env.agent_names}
                order = list(env.agent_names)
                draws.shuffle(order)
                env.assignment = dict(assignment)
                score = env._evaluate_assignment(assignment)["score"]
                _, rewards = env._rewards(assignment)
                metrics = compute_collusion_metrics(
                    env=env, colluders=order[:2], secret_blackboard_id=None, secret_channel_enabled=False,
                    prompt_variant="control", tool_events=[], blackboard_participants={},
                    final_summary={"assignment": {a: (t or "skip") for a, t in assignment.items()},
                                   "agent_rewards": rewards, "joint_reward": score})
                regret = {o.agent_name: o.regret for o in metrics.agents}
                claimed, sequential = set(), {}
                for agent in order:
                    available = sorted(t for t in task_ids if t not in claimed)
                    sequential[agent] = S._best_response_regret(
                        agent=agent, actual_assignment={a: (t or "skip") for a, t in assignment.items()},
                        agent_names=list(env.agent_names), task_id_set=set(task_ids), tasks=env.tasks,
                        costs=env.costs, weights=W, candidates=["skip", *available])
                    if assignment[agent] is not None:
                        claimed.add(assignment[agent])
                samples.append({"assignment": assignment, "turn_order": order, "score": score, "rewards": rewards,
                                "best_response_regret": regret, "sequential_regret": sequential})
            cases.append({"seed": seed, "tasks": max_tasks, "fill": fill, "optimum": opt.joint_reward,
                          "optimum_violations": opt.violations, "samples": samples})
    with open(sys.argv[3], "w") as f:
        json.dump({"source": "Colosseum b077fe7 / Terrarium v0.1.1", "python": platform.python_version(),
                   "cases": cases}, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main()
