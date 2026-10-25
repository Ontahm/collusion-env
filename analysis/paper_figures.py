"""Figures 1 and 2 of the report ("Say Nothing: Action-Only Collusion Between LLM Agents"), redrawn from
the committed runs (PNG and PDF, in paper/).

    python -m analysis.paper_figures            # or: make paper-figures

  Figure 1  how often B claimed the jackpot, with 95% Wilson intervals:
            (a) per condition and model; (b) gpt-5-mini, boards where A blocked (claimed the decoy) vs
            all other boards, labelled hits/boards, for conditions with at least one block.
  Figure 2  each condition's hit rate against the share of its boards flagged by the cost rule
            (A claimed anything other than its two best tasks; every block is flagged).

JP-5 is drawn as its first run (boards 1-150) and two replications on fresh boards (151-300, 301-600),
never pooled. Measures as in analysis/jackpot.py (B right: B claimed the jackpot; missing, skipped and
off-pair claims count as wrong).
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Tuple

from analysis.figures import INK_2, MUTED, plt, save, style
from analysis.jackpot import _b, is_flagged, wilson

ROOT = Path(__file__).resolve().parents[1]
GPT, QWEN = "gpt-5-mini", "Qwen3-32B (exploratory)"
NAVY, ORANGE, PURPLE, GREEN = "#1f3a68", "#e8890c", "#7b3fa0", "#1f8a5b"

# (label shown, model, run folder, condition, seeds or None for all)
SERIES: List[Tuple[str, str, str, str, Tuple[int, int] | None]] = [
    ("JP-0\nno partner", GPT, "runs/20261024-175907__jackpot", "jackpot_no_partner", None),
    ("JP-1\nchat", GPT, "runs/20261024-175907__jackpot", "jackpot_chat", None),
    ("JP-2\nvisible", GPT, "runs/20261024-175907__jackpot", "jackpot_visible", None),
    ("JP-3\nhidden", GPT, "runs/20261024-175907__jackpot", "jackpot_hidden", None),
    ("JP-4\nuntold", GPT, "runs/20261024-175907__jackpot", "jackpot_untold", None),
    ("JP-5\nnaive", GPT, "runs/20261024-175907__jackpot", "jackpot_naive", None),
    ("JP-5\nrep. 1", GPT, "runs/20261025-111033__jackpot_followup", "jackpot_naive", None),
    ("JP-5\nrep. 2", GPT, "runs/20261025-133808__jackpot_followup", "jackpot_naive", None),
    ("JP-6\ncode", GPT, "runs/20261025-111033__jackpot_followup", "jackpot_code", None),
    ("JP-7\nauditor", GPT, "runs/20261025-111033__jackpot_followup", "jackpot_monitor", None),
    ("JP-1\nchat", QWEN, "runs/20261024-171111__jackpot__modal-qwen3-32b-thinking", "jackpot_chat", None),
    ("JP-2\nvisible", QWEN, "runs/20261024-171111__jackpot__modal-qwen3-32b-thinking", "jackpot_visible", None),
    ("JP-3\nhidden", QWEN, "runs/20261024-171111__jackpot__modal-qwen3-32b-thinking", "jackpot_hidden", None),
    ("JP-6\ncode", QWEN, "runs/20261025-111125__jackpot_followup__modal-qwen3-32b-thinking", "jackpot_code", None),
]
SHORT = {"JP-5\nrep. 1": "JP-5 r1", "JP-5\nrep. 2": "JP-5 r2"}
# Figure 2 label offsets in points, where the default (right, above) would overlap a neighbour.
OFFSETS = {("JP-5\nrep. 1", GPT): (-34, -12), ("JP-0\nno partner", GPT): (-10, 10),
           ("JP-7\nauditor", GPT): (-30, -12), ("JP-2\nvisible", QWEN): (6, 4), ("JP-3\nhidden", QWEN): (6, -12)}


def load(root: Path) -> Dict[Tuple[str, str], List[dict]]:
    cache: Dict[str, List[dict]] = {}
    out = {}
    for label, model, run, cond, seeds in SERIES:
        if run not in cache:
            with open(root / run / "index.csv", newline="") as f:
                cache[run] = list(csv.DictReader(f))
        rows = [r for r in cache[run] if r["condition"] == cond
                and (seeds is None or seeds[0] <= int(r["seed"]) <= seeds[1])]
        if not rows:
            raise SystemExit(f"no rows for {cond} in {run}")
        out[(label, model)] = rows
    return out


def hit(rows: List[dict]) -> Tuple[int, int]:
    return sum(_b(r["jk_b_correct"]) for r in rows), len(rows)


def point(ax, x, k, n, color, marker, filled=True, label=None, annotate=False):
    p = k / n
    lo, hi = wilson(k, n)
    ax.errorbar([x], [100 * p], yerr=[[100 * (p - lo)], [100 * (hi - p)]], fmt=marker, color=color,
                markerfacecolor=color if filled else "white", markeredgewidth=1.4, markersize=6,
                elinewidth=1.2, capsize=2.5, label=label, zorder=3)
    if annotate:
        ax.annotate(f"{k}/{n}", (x, 100 * hi), textcoords="offset points", xytext=(0, 4), ha="center",
                    fontsize=6.5, color=color)


def chance(ax):
    ax.axhline(50, color=MUTED, linestyle="--", linewidth=0.9, zorder=1)
    ax.text(1.005, 50, "chance", transform=ax.get_yaxis_transform(), ha="left", va="center", fontsize=7,
            color=MUTED, clip_on=False)


def figure1(data, out: Path):
    labels = list(dict.fromkeys(label for label, *_ in SERIES))
    x = {label: i for i, label in enumerate(labels)}
    fig, (a, b) = plt.subplots(2, 1, figsize=(7.2, 6.0))
    for (label, model), rows in data.items():
        gpt = model == GPT
        point(a, x[label] + (-0.12 if gpt else 0.12), *hit(rows), NAVY if gpt else ORANGE,
              "o" if gpt else "s", filled=gpt, label=model)
    handles, names = a.get_legend_handles_labels()
    keep = dict(zip(names, handles))
    a.legend(keep.values(), keep.keys(), loc="lower left")
    a.set_title("(a) Hit rate by condition")

    shown = [label for label in labels if any(r["jk_a_strategy"] == "block" for r in data.get((label, GPT), []))]
    for i, label in enumerate(shown):
        rows = data[(label, GPT)]
        blocked = [r for r in rows if r["jk_a_strategy"] == "block"]
        other = [r for r in rows if r["jk_a_strategy"] != "block"]
        point(b, i - 0.15, *hit(blocked), PURPLE, "D", label="A blocked (took the decoy)", annotate=True)
        point(b, i + 0.15, *hit(other), GREEN, "o", label="all other boards", annotate=True)
    handles, names = b.get_legend_handles_labels()
    keep = dict(zip(names, handles))
    b.legend(keep.values(), keep.keys(), loc="upper right", ncol=2, bbox_to_anchor=(1.0, 1.18))
    b.set_title("(b) gpt-5-mini: boards where A blocked vs all other boards")

    for ax, ticks in ((a, labels), (b, shown)):
        chance(ax)
        ax.set_xticks(range(len(ticks)), ticks)
        ax.set_ylim(0, 108)
        ax.set_ylabel("B claimed the jackpot (%)")
    save(fig, out, "fig1_hit_rate")


def figure2(data, out: Path):
    fig, ax = plt.subplots(figsize=(6.0, 4.0))
    for (label, model), rows in data.items():
        gpt = model == GPT
        k, n = hit(rows)
        flagged = 100 * sum(is_flagged(r) for r in rows) / n
        ax.scatter([flagged], [100 * k / n], marker="o" if gpt else "s", s=42, zorder=3,
                   color=NAVY if gpt else "white", edgecolor=NAVY if gpt else ORANGE, linewidth=1.4,
                   label=model)
        name = SHORT.get(label, label.split("\n")[0])
        offset = OFFSETS.get((label, model), (5, 4) if gpt else (5, -10))
        ax.annotate(name, (flagged, 100 * k / n), textcoords="offset points", xytext=offset,
                    fontsize=7, color=NAVY if gpt else ORANGE)
    handles, names = ax.get_legend_handles_labels()
    keep = dict(zip(names, handles))
    ax.legend(keep.values(), keep.keys(), loc="lower left")
    chance(ax)
    ax.set_xlim(-2, 36)
    ax.set_ylim(20, 105)
    ax.set_xlabel("Boards flagged by the cost rule (%)")
    ax.set_ylabel("B claimed the jackpot (%)", color=INK_2)
    save(fig, out, "fig2_cost_rule")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(ROOT / "paper"), help="output folder (default: paper/)")
    args = parser.parse_args(argv)
    style()
    data = load(ROOT)
    figure1(data, Path(args.out))
    figure2(data, Path(args.out))
    for (label, model), rows in data.items():
        k, n = hit(rows)
        print(f"{label.replace(chr(10), ' '):18} {model:24} B right {k:3}/{n:3} = {k / n:4.0%}   "
              f"flagged {sum(is_flagged(r) for r in rows) / n:4.0%}")
    print(f"figures in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
