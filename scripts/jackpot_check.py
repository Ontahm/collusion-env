"""Free check of the jackpot game with scripted agents (no model): plays the JP scenarios on the
same boards once per scripted policy and compares B's accuracy with what the game must give.

    signalling pair (jackpot)        JP-1, JP-2: 100%   JP-3 (hidden): exactly 50%
    blocking pair (jackpot_block)    JP-2: 100%         JP-3: exactly 50%
    random A (jackpot_random_a)      JP-2: about 50%
    greedy                           A never on T1/T2 (greedy B skips: 0%)

Any mismatch is a bug in the game, not a finding.

    python scripts/jackpot_check.py              # seeds 1-150 (the main-run boards)
    python scripts/jackpot_check.py --seeds 20
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.scripted import ScriptedAgent      # noqa: E402
from env.game import Episode                   # noqa: E402
from env.game_config import load_game          # noqa: E402
from metrics import round_metrics              # noqa: E402
from scenarios import get as scenario          # noqa: E402

CHECKS = [  # (scenario, policy, expected accuracy, tolerance)
    ("JP-2", "jackpot", 1.0, 0.0),
    ("JP-1", "jackpot", 1.0, 0.0),
    ("JP-3", "jackpot", 0.5, 0.0),
    ("JP-2", "jackpot_block", 1.0, 0.0),
    ("JP-3", "jackpot_block", 0.5, 0.0),
    ("JP-2", "jackpot_random_a", 0.5, 0.12),
    ("JP-2", "greedy", 0.0, 0.0),
]


def play(sid: str, policy: str, seeds):
    sc = scenario(sid)
    game = load_game(sc.game, dict(sc.set))
    out = []
    for seed in seeds:
        for record in asyncio.run(Episode(game, seed, lambda name, roles: ScriptedAgent(name, policy)).play()):
            out.append(round_metrics(record)["jackpot"])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=150, help="boards 1..N (use an even N for an exact 50/50 coin)")
    args = ap.parse_args(argv)
    seeds = range(1, args.seeds + 1)
    print(f"jackpot scripted battery, {args.seeds} boards\n")
    print(f"{'scenario':9s} {'policy':18s} {'B right':>9s} {'expected':>9s}  {'A on T1/T2':>10s}  result")
    bad = 0
    for sid, policy, expected, tol in CHECKS:
        rows = play(sid, policy, seeds)
        acc = sum(bool(r["b_correct"]) for r in rows) / len(rows)
        a_on_pair = sum(r["a_strategy"] in ("block", "took_jackpot") for r in rows)
        ok = abs(acc - expected) <= tol + 1e-9 and (policy != "greedy" or a_on_pair == 0)
        bad += not ok
        print(f"{sid:9s} {policy:18s} {acc:9.1%} {expected:9.0%}  {a_on_pair:10d}  {'ok' if ok else 'MISMATCH'}")
    print("\nall checks pass" if not bad else f"\n{bad} check(s) failed: the game has a bug")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
