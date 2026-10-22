"""Fraction of Colosseum Jira boards where colluders matching on one issue costs the team nothing.
price_of_collusion = F(optimum) - max F(assignment with both colluders on the same issue), exact.
Uses the upstream generator + reward code; colluders drawn as in upstream run.py (random)."""
import random, sys
import numpy as np
from scipy.optimize import linear_sum_assignment
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
from envs.dcops.jira_ticket.jira_ticket_env import JiraTicketEnvironment as E
from experiments.collusion import compute_jira_optimal as O
W = O.JiraWeights(20.0, 20.0, 20.0)
BIG = 1e9

def board(seed, max_tasks):
    env = E.__new__(E); env.env_config = {"max_tasks": max_tasks}; env.current_seed = seed
    env.rng = random.Random(seed); env.microtask_types = env._get_microtask_types()
    env.tasks = env._build_tasks(max_tasks); env.agent_names, env.agent_private = env._build_agents(6)
    env.costs = env._compute_costs(); env.tasks_done_bonus = env.priority_bonus = env.violation_penalty = 20.0
    colluders = random.Random(seed).sample(list(env.agent_names), k=2)
    return env, colluders

def best(env, allowed, nodup=()):  # allowed[agent] = set of task ids (None = skip allowed), mirrors compute_jira_optimal slots
    A, T = env.agent_names, list(env.tasks); n = len(A)
    C = np.zeros((n, n * (len(T) + 1)))
    for i, a in enumerate(A):
        for j, t in enumerate(T):
            base = W.tasks_done_bonus + W.priority_bonus * env._priority_weight(env.tasks[t]["priority"]) - env.costs[a][t]
            ok = t in allowed[a]
            C[i, j*n] = -base if ok else BIG
            C[i, j*n+1:(j+1)*n] = -(base - W.violation_penalty) if (ok and a not in nodup) else BIG
        if None not in allowed[a]: C[i, len(T)*n:] = BIG
    r, c = linear_sum_assignment(C)
    if C[r, c].max() >= BIG: return None
    ch = {A[i]: (T[k // n] if k < len(T)*n else None) for i, k in zip(r, c)}
    return env._evaluate_assignment(ch)["score"], ch

sizes = [int(x) for x in sys.argv[3].split(",")]; N = int(sys.argv[4])
print("tasks issues boards  conflict(price>0)  costless(price=0)  same-issue-impossible")
for m in sizes:
    conflict = costless = imposs = 0
    for s in range(1, N + 1):
        env, col = board(s, m)
        free = {a: set(env.tasks) | {None} for a in env.agent_names}
        F, _ = best(env, free)
        issues = sorted({t["issue_id"] for t in env.tasks.values()})
        vals = []
        for k in issues:
            al = dict(free); ts = {t for t, v in env.tasks.items() if v["issue_id"] == k}
            for c in col: al[c] = ts
            b = best(env, al, nodup=set(col))
            if b: vals.append(b[0])
        if not vals: imposs += 1; continue
        price = F - max(vals)
        if price > 1e-9: conflict += 1
        else: costless += 1
    print(f"{m:5d} {len(issues):6d} {N:6d}  {conflict/N:8.1%}           {costless/N:8.1%}           {imposs/N:6.1%}")
