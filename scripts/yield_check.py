"""Free check of the yield-to-partner positive control with scripted agents (no model).

Plays configs/games/yield_control.yaml (or --game) on the same boards once per scripted policy and
reads the round measures the runner records. Expected:
    oracle_pair    B alone got T on ~100% of boards (ceiling)
    greedy         ~0% (A takes T)
    team_optimal   ~0% (H takes T)

    python scripts/yield_check.py --seeds 100
"""

from __future__ import annotations

import argparse
import asyncio
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.scripted import ScriptedAgent      # noqa: E402
from env.game import Episode                   # noqa: E402
from env.game_config import load_game          # noqa: E402
from metrics import round_metrics              # noqa: E402


def run(game, policy, seeds):
    rows = []
    for seed in seeds:
        for record in asyncio.run(Episode(game, seed, lambda name, roles: ScriptedAgent(name, policy)).play()):
            m = round_metrics(record)
            plan = record["setup"].analysis["construction"]
            holders = [a for a, t in record["assignment"].items() if t == plan["tempting_task"]]
            rows.append({"b_alone": float(m["actions"]["better_alone_got_t"]),
                         "a_holds": float(plan["worse_colluder"] in holders),
                         "h_holds": float(plan["team_best_fit"] in holders),
                         "pair": m["actions"]["pair_reward"], "team_loss": m["team_loss"],
                         "targets_met": float(plan["targets_met"])})
    return rows


def wilson(p, n, z=1.96):
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="configs/games/yield_control.yaml")
    ap.add_argument("--seeds", type=int, default=100)
    args = ap.parse_args()
    game = load_game(args.game)
    seeds = range(1, args.seeds + 1)
    print(f"{args.game}: {args.seeds} boards\n")
    print(f"{'policy':13s} {'B alone got T':>24s} {'A holds T':>10s} {'H holds T':>10s} {'pair reward':>12s} "
          f"{'team loss':>10s} {'targets met':>12s}")
    for policy in ("oracle_pair", "greedy", "team_optimal"):
        rows = run(game, policy, seeds)
        n = len(rows)
        avg = lambda k: statistics.mean(r[k] for r in rows)      # noqa: E731
        lo, hi = wilson(avg("b_alone"), n)
        print(f"{policy:13s} {avg('b_alone'):6.0%} [{lo:4.0%}, {hi:4.0%}] n={n:<4d} {avg('a_holds'):10.0%} "
              f"{avg('h_holds'):10.0%} {avg('pair'):12.1f} {avg('team_loss'):10.1f} {avg('targets_met'):12.0%}")


if __name__ == "__main__":
    main()
