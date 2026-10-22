"""Compare env/board.py with the boards agents actually saw in real Colosseum episodes.

    python -I check_episodes.py <collusion-env repo> <directory of Colosseum outputs>

For every episode (a folder with run_config.json and agent_prompts.json), rebuild the board from
its seed, number of tasks and number of agents, then compare with each agent's first prompt:
names, availability, top skills (2 decimals, as printed), every task line, every cost (2 decimals).
Also counts how the colluders were chosen (Colosseum's random draw or the first two agents)."""
import glob, json, os, random, re, sys
from collections import Counter
sys.path.insert(0, sys.argv[1])                       # collusion-env repo
from env.board import load_board_config, make_board

TASK = re.compile(r"^- (\S+): (.*) \| type=(\S+) \| effort=(\S+) \| priority=(\S+) \| tags=\[(.*)\]$")
COST = re.compile(r"^- (\S+): cost=(\S+)$")

def section(text, name):
    m = re.search(rf"=== {name} ===\n(.*?)(?:\n\n|\Z)", text, re.S)
    return m.group(1).splitlines() if m else []

stats, problems, order_stats = Counter(), [], Counter()
for rc_path in glob.glob(os.path.join(sys.argv[2], "**", "run_config.json"), recursive=True):
    ep = os.path.dirname(rc_path)
    if not os.path.exists(f"{ep}/agent_prompts.json"):
        stats["no prompts"] += 1; continue
    rc = json.load(open(rc_path))
    n_tasks = int((rc.get("environment_cfg") or {}).get("max_tasks", 20))
    board = make_board(int(rc["seed"]), load_board_config(n_tasks=n_tasks, n_agents=int(rc["num_agents"])))
    prompts = {}
    for p in json.load(open(f"{ep}/agent_prompts.json")):
        prompts.setdefault(p["agent_name"], p["user_prompt"])     # first prompt of each agent
    errs = []
    if set(prompts) != set(board.agent_names):
        errs.append(f"names {sorted(prompts)} vs {sorted(board.agent_names)}")
    for name, text in prompts.items():
        if name not in board.agent_names: continue
        a = board.agent(name)
        av = re.search(r"Availability \(hours\): (\S+)", text).group(1)
        if av != str(a.availability): errs.append(f"{name} availability {av} vs {a.availability}")
        sk = re.search(r"Top skills: (.*)", text).group(1)
        ours = ", ".join(f"{t}:{v:.2f}" for t, v in sorted(a.skills, key=lambda x: x[1], reverse=True)[:5])
        if sk != ours: errs.append(f"{name} skills {sk} vs {ours}")
        tasks = [TASK.match(l).groups() for l in section(text, r"TASKS \(PUBLIC\)")]
        ours_t = [(t.id, t.title, t.work_type, str(t.effort), t.priority, ", ".join(t.tags)) for t in board.tasks]
        if tasks != ours_t: errs.append(f"{name} tasks differ")
        costs = dict(COST.match(l).groups() for l in section(text, r"YOUR COSTS \(PRIVATE\)"))
        ours_c = {t.id: f"{board.cost(name, t.id):.2f}" for t in board.tasks}
        if costs != ours_c: errs.append(f"{name} costs differ")
    stats["episodes"] += 1
    if errs:
        stats["mismatch"] += 1; problems.append((ep, errs[:3]))
    else:
        stats["identical"] += 1
    stats[f"tasks={n_tasks},agents={rc['num_agents']}"] += 1
    # what Colosseum's own runner would draw for this seed (for module 2), vs what the run used
    draw = random.Random(int(rc["seed"])).sample(list(board.agent_names), k=int(rc["colluder_count"]))
    order_stats["colluders = Colosseum random draw" if set(draw) == set(rc["colluders"]) else
                 ("colluders = first two names" if set(rc["colluders"]) == set(board.agent_names[:2]) else "colluders = other")] += 1
    order_stats[f"agent_order={rc.get('agent_order')}"] += 1
print(dict(stats)); print(dict(order_stats))
for ep, errs in problems[:5]: print("MISMATCH", ep.split("/runs/")[-1][:90], errs)
