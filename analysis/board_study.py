"""Model-free board study: how often can the coalition's goal be seen as a loss for the team?

    python -m analysis.board_study configs/board_study.yaml [--seeds 1-200] [--workers N] [--out DIR]

For every board size, seed and objective in the config: the board, its colluders (drawn as in the
game config), and the exact analysis of spec/09 (optimum, price of collusion, conflict flag,
matching cost, high-value holder in the optimum). Boards are analysed in parallel (`--workers`,
default: all CPU cores) and streamed to runs/board_study/<timestamp>/boards.csv; summary.md and
figures/ (analysis/figures.py) are computed from running aggregates, so memory stays small even
for hundreds of thousands of boards. No model is called. Results do not depend on --workers.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from analysis.stats import quantile, wilson
from env.board import make_board, with_size
from env.board_analysis import analyze
from env.configio import load_yaml, resolve_path
from env.game_config import load_game
from env.objectives import resolve
from env.roles import draw_roles
from run import parse_seeds

COLUMNS = ["tasks", "objective", "seed", "optimum", "optimum_has_duplicate", "price_same_issue",
           "same_issue_conflict", "matching_cost", "hv_task", "price_hv", "hv_conflict",
           "hv_holder_in_optimum_is_colluder"]
FLAGS = ("same_issue_conflict", "hv_conflict", "hv_holder_in_optimum_is_colluder", "optimum_has_duplicate")
VALUES = ("price_same_issue", "price_hv", "matching_cost")


def analyze_chunk(job: Tuple[Optional[str], Dict[str, Any], int, str, List[int]]) -> List[list]:
    """One worker's share: boards of one size and objective, for a list of seeds."""
    game_path, overrides, size, label, seeds = job
    game = load_game(game_path, overrides)
    board_cfg = with_size(game.board, int(size))
    rows = []
    for seed in seeds:
        board = make_board(seed, board_cfg)
        roles = draw_roles(board.agent_names, seed, game.roles.colluders, game.roles.selection, game.roles.order)
        objective = resolve(game.objective, board, roles, seed, game.scoring)
        a = analyze(board, roles, objective.scoring_context(game.scoring, roles), objective)
        rows.append([size, label, seed, a["optimum"], a["optimum_has_duplicate"], a["price_same_issue"],
                     a["same_issue_conflict"], a["matching_cost"], a.get("hv_task"), a.get("price_hv"),
                     a.get("hv_conflict"), a.get("hv_holder_in_optimum_is_colluder")])
    return rows


class Aggregate:
    """Counts of each flag and lists of each value, per (size, objective)."""

    def __init__(self) -> None:
        self.flags: Dict[tuple, List[int]] = defaultdict(lambda: [0, 0])
        self.values: Dict[tuple, List[float]] = defaultdict(list)

    def add(self, row: list) -> None:
        r = dict(zip(COLUMNS, row))
        group = (int(r["tasks"]), r["objective"])
        for flag in FLAGS:
            if r[flag] is not None:
                cell = self.flags[group + (flag,)]
                cell[0] += bool(r[flag])
                cell[1] += 1
        for key in VALUES:
            if r[key] is not None:
                self.values[group + (key,)].append(float(r[key]))

    def rate(self, group: tuple, flag: str) -> Optional[Tuple[int, int]]:
        cell = self.flags.get(group + (flag,))
        return (cell[0], cell[1]) if cell and cell[1] else None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("config")
    parser.add_argument("--seeds")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--out", help="parent folder (default: the config's out_dir, runs/board_study)")
    args = parser.parse_args(argv)
    cfg = load_yaml(args.config)
    base_set = cfg.get("set") or {}
    base_game = load_game(cfg.get("game"), base_set)
    seeds = parse_seeds(args.seeds or cfg.get("seeds", "1-200"))
    sizes = cfg.get("sizes", [base_game.board.n_tasks])
    objectives = cfg.get("objectives") or {"same_issue": {"objective.type": "same_issue"}}
    out_dir = resolve_path(args.out or cfg.get("out_dir", "runs/board_study")) / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)

    chunk = max(1, min(200, len(seeds) // max(1, args.workers) or 1))
    jobs = [(cfg.get("game"), {**base_set, **overrides}, size, label, seeds[i:i + chunk])
            for size in sizes for label, overrides in objectives.items() for i in range(0, len(seeds), chunk)]
    total = len(sizes) * len(objectives) * len(seeds)
    print(f"{total} boards ({len(sizes)} sizes x {len(objectives)} objectives x {len(seeds)} seeds), "
          f"{args.workers} workers -> {out_dir}", flush=True)
    agg = Aggregate()
    started, done, next_report = time.time(), 0, 0
    with (out_dir / "boards.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        pool = ProcessPoolExecutor(max_workers=args.workers) if args.workers > 1 else None
        try:
            results = pool.map(analyze_chunk, jobs) if pool else map(analyze_chunk, jobs)   # in job order
            for rows in results:
                writer.writerows(rows)
                for row in rows:
                    agg.add(row)
                done += len(rows)
                if done >= next_report:
                    print(f"  {done}/{total} boards, {time.time() - started:.0f} s", flush=True)
                    next_report += max(1, total // 20)
        finally:
            if pool:
                pool.shutdown()

    def frac(group, flag):
        r = agg.rate(group, flag)
        if not r:
            return "—"
        lo, hi = wilson(*r)
        return f"{r[0] / r[1]:.1%} [{lo:.1%}, {hi:.1%}]"

    def med(group, key):
        v = quantile(agg.values.get(group + (key,), []), 0.5)
        return "—" if v is None else f"{v:.2f}"

    lines = [f"# Board study — {args.config}", "",
             f"Seeds {seeds[0]}–{seeds[-1]} ({len(seeds)} boards per size and objective), {total} boards in "
             f"{time.time() - started:.0f} s. Conflict = reaching the coalition's goal costs the team (price > 0).", "",
             "| tasks | objective | same-issue conflict | high-value conflict | high-value held by a colluder in the optimum | median price (same issue) | median price (high value) | median matching cost | optimum with a duplicate |",
             "|---|---|---|---|---|---|---|---|---|"]
    for size in sorted(int(s) for s in sizes):
        for label in objectives:
            g = (size, label)
            lines.append(f"| {size} | {label} | {frac(g, 'same_issue_conflict')} | {frac(g, 'hv_conflict')} | "
                         f"{frac(g, 'hv_holder_in_optimum_is_colluder')} | {med(g, 'price_same_issue')} | "
                         f"{med(g, 'price_hv')} | {med(g, 'matching_cost')} | {frac(g, 'optimum_has_duplicate')} |")
    from analysis.figures import board_figures
    made = board_figures(out_dir, agg)
    lines += ["", "Figures: " + ", ".join(f"`figures/{p.name}`" for p in made if p.suffix == ".png")]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nwritten to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
