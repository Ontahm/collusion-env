"""Reference colluders and turn orders from Colosseum's runner, for the tests of env/roles.py.

    python -I roles_fixtures.py <terrarium dir> <colosseum dir> <out.json>

The runner itself cannot be imported without its whole stack, so the two functions it uses,
`_select_colluders` and `_order_agent_turns`, are taken verbatim from the pristine
`experiments/collusion/run.py` (via `git show`) and executed here; the surrounding calls follow
`_run_single`: one `random.Random(seed)`, colluders drawn first, then `rng.shuffle(agents)` when the
order is random. Agent names come from Colosseum's board generator.
"""

import ast
import json
import random
import subprocess
import sys
from typing import List, Sequence  # noqa: F401  (used by the extracted functions)

sys.path.insert(0, sys.argv[1])
from envs.dcops.jira_ticket.jira_ticket_env import JiraTicketEnvironment as E  # noqa: E402

source = subprocess.run(["git", "-C", sys.argv[2], "show", "HEAD:experiments/collusion/run.py"],
                        capture_output=True, text=True, check=True).stdout
namespace = {"random": random, "List": List, "Sequence": Sequence}
for node in ast.parse(source).body:
    if isinstance(node, ast.FunctionDef) and node.name in ("_select_colluders", "_order_agent_turns"):
        exec(compile(ast.Module(body=[node], type_ignores=[]), "run.py", "exec"), namespace)


def names(seed):
    env = E.__new__(E)
    env.current_seed = seed
    return env._generate_agent_names(6)


out = {}
for selection in ("random", "first"):
    for order in ("random", "colluders_first"):
        rows = []
        for seed in range(1, 201):
            agent_names = names(seed)
            rng = random.Random(int(seed))
            colluders = namespace["_select_colluders"](agent_names=agent_names, count=2, strategy=selection, rng=rng)
            ordered = namespace["_order_agent_turns"](agent_names=agent_names, colluders=colluders, strategy=order)
            if order == "random":
                agents = list(agent_names)
                rng.shuffle(agents)
            else:
                agents = list(ordered)
            rows.append({"seed": seed, "names": agent_names, "colluders": colluders, "turn_order": agents})
        out[f"selection={selection},order={order}"] = rows
with open(sys.argv[3], "w") as f:
    json.dump(out, f)
    f.write("\n")
