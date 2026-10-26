"""Figures 1, 2 and B1 of the paper "Say Nothing" (jackpot game, challenge 3.1).

Usage (from the repo folder):
    uv run --locked python -m analysis.jackpot_figures

Reads index.csv from the five run folders the paper uses (SOURCES below) and writes, in paper/figures/:
  jackpot_figure1.png/.pdf   how often B claimed the jackpot, by condition and model, 95% Wilson intervals
  jackpot_figure2.png/.pdf   each condition's hit rate against the share of its boards flagged by the
                             cost rule
  jackpot_figureB1.png/.pdf  (appendix) gpt-5-mini only, boards where A blocked vs all other boards
PNGs are 300 dpi. Figures 1 and B1 are 7 x 2.6 inches, Figure 2 is 4.6 x 3 inches. Captions carry the
titles, so the figures have none.

Definitions come from analysis/jackpot.py, so the figures match the reports: B right = jk_b_correct;
block = A took the decoy; flagged = analysis.jackpot.is_flagged (A claimed anything other than A1 or A2).
JP-5's three runs (boards 1-150, 151-300, 301-600) are drawn separately and never pooled.

To change the figures: SOURCES lists the run folders; ORDER sets the conditions, their order and labels;
colours are set below ORDER. Label positions in Figure 2 are set by hand (offsets in draw_c); if the data
change, check that the labels still do not overlap.
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "figures"
sys.path.insert(0, str(ROOT))

from analysis.jackpot import _b, is_flagged, wilson  # noqa: E402

SOURCES = [  # run folder, tag for JP-5 rows from that folder
    ("20261024-175907__jackpot", ""),
    ("20261024-171111__jackpot__modal-qwen3-32b-thinking", ""),
    ("20261025-111033__jackpot_followup", " rep1"),
    ("20261025-111125__jackpot_followup__modal-qwen3-32b-thinking", ""),
    ("20261025-133808__jackpot_followup", " rep2"),
]
ORDER = [  # condition key, axis label, short label for panel (c)
    ("jackpot_no_partner", "JP-0\nno partner", "JP-0"),
    ("jackpot_chat", "JP-1\nchat", "JP-1"),
    ("jackpot_visible", "JP-2\nvisible", "JP-2"),
    ("jackpot_hidden", "JP-3\nhidden", "JP-3"),
    ("jackpot_untold", "JP-4\nuntold", "JP-4"),
    ("jackpot_naive", "JP-5\nnaive", "JP-5"),
    ("jackpot_naive rep1", "JP-5\nrep. 1", "JP-5 r1"),
    ("jackpot_naive rep2", "JP-5\nrep. 2", "JP-5 r2"),
    ("jackpot_code", "JP-6\ncode", "JP-6"),
    ("jackpot_monitor", "JP-7\nauditor", "JP-7"),
]
GPT, QWEN = "gpt-5-mini", "modal-qwen3-32b-thinking"
NAVY, ORANGE, PURPLE, GREEN, GREY = "#1f3a68", "#e07b00", "#7b3fa0", "#2e8b57", "#888888"


def load():
    by = defaultdict(list)
    for folder, tag in SOURCES:
        with open(ROOT / "runs" / folder / "index.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            if r.get("jk_coin") in (None, "", "None"):
                continue
            c = r["condition"].split()[-1]
            if c == "jackpot_naive":
                c += tag
            by[(c, r["model"])].append(r)
    return by


def rate(rs):
    k, n = sum(_b(r["jk_b_correct"]) for r in rs), len(rs)
    lo, hi = wilson(k, n)
    return k, n, 100 * k / n, 100 * lo, 100 * hi


def draw_a(ax_a, by):
    for i, (c, label, _) in enumerate(ORDER):
        for model, dx, kw in ((GPT, -0.13 if (c, QWEN) in by else 0, dict(marker="o", color=NAVY, mfc=NAVY)),
                              (QWEN, 0.13, dict(marker="s", color=ORANGE, mfc="white"))):
            if (c, model) not in by:
                continue
            k, n, p, lo, hi = rate(by[(c, model)])
            ax_a.errorbar(i + dx, p, yerr=[[p - lo], [hi - p]], ms=4.2, mew=1, lw=0.9, capsize=1.8, ls="none", **kw)
    ax_a.axhline(50, color=GREY, lw=0.7, ls="--", zorder=0)
    ax_a.text(len(ORDER) - 0.45, 51.5, "chance", color=GREY, fontsize=6, ha="right", va="bottom")
    ax_a.set_xticks(range(len(ORDER)), [o[1] for o in ORDER])
    ax_a.set_xlim(-0.5, len(ORDER) - 0.5)
    ax_a.set_ylim(0, 105)
    ax_a.set_ylabel("B claimed the jackpot (%)")
    ax_a.legend(handles=[Line2D([], [], marker="o", color=NAVY, ls="none", ms=4.2, label="GPT-5 Mini"),
                         Line2D([], [], marker="s", color=ORANGE, mfc="white", ls="none", ms=4.2, label="Qwen3-32B (exploratory)")],
                loc="lower left", frameon=False, ncol=2, bbox_to_anchor=(0.0, -0.02))


def draw_b(ax_b, by):
    split = [o for o in ORDER if any(r["jk_a_strategy"] == "block" for r in by.get((o[0], GPT), []))]
    for i, (c, label, _) in enumerate(split):
        rs = by[(c, GPT)]
        for sub, dx, kw, va, dy in (([r for r in rs if r["jk_a_strategy"] == "block"], -0.13,
                                     dict(marker="D", color=PURPLE, mfc=PURPLE, ms=3.6), "bottom", 1),
                                    ([r for r in rs if r["jk_a_strategy"] != "block"], 0.13,
                                     dict(marker="o", color=GREEN, mfc=GREEN, ms=3.8), "top", -1)):
            k, n, p, lo, hi = rate(sub)
            ax_b.errorbar(i + dx, p, yerr=[[p - lo], [hi - p]], lw=0.9, capsize=1.6, ls="none", mew=0.8, **kw)
            y = hi + 2 if dy > 0 else lo - 2
            ax_b.text(i + dx, y, f"{k}/{n}", fontsize=5.2, ha="center", va=va, color=kw["color"])
    ax_b.axhline(50, color=GREY, lw=0.7, ls="--", zorder=0)
    ax_b.set_xticks(range(len(split)), [o[1] for o in split])
    ax_b.set_xlim(-0.55, len(split) - 0.45)
    ax_b.set_ylim(-8, 124)
    ax_b.set_yticks(range(0, 101, 25))
    ax_b.set_ylabel("B claimed the jackpot (%)")
    ax_b.legend(handles=[Line2D([], [], marker="D", color=PURPLE, ls="none", ms=3.6, label="A blocked (took the decoy)"),
                         Line2D([], [], marker="o", color=GREEN, ls="none", ms=3.8, label="all other boards")],
                loc="upper center", frameon=False, bbox_to_anchor=(0.5, 1.04), ncol=2, columnspacing=1.2, handletextpad=0.3)


def draw_c(ax_c, by):
    offsets = {  # label placement (points), chosen by eye to avoid overlaps; True = draw a leader line
        ("jackpot_no_partner", GPT): (-8, 14, True), ("jackpot_chat", GPT): (-4, 7, False),
        ("jackpot_visible", GPT): (-3, 6, False), ("jackpot_hidden", GPT): (5, 0, False),
        ("jackpot_untold", GPT): (5, -5, False), ("jackpot_naive", GPT): (5, 2, False),
        ("jackpot_naive rep1", GPT): (5, -6, False), ("jackpot_naive rep2", GPT): (6, 1, False),
        ("jackpot_code", GPT): (-2, 7, False), ("jackpot_monitor", GPT): (-10, -14, True),
        ("jackpot_chat", QWEN): (5, -2, False), ("jackpot_visible", QWEN): (10, 9, True),
        ("jackpot_hidden", QWEN): (12, -12, True), ("jackpot_code", QWEN): (3, -9, False),
    }
    for c, _, short in ORDER:
        for model, kw in ((GPT, dict(marker="o", color=NAVY, mfc=NAVY)), (QWEN, dict(marker="s", color=ORANGE, mfc="white"))):
            if (c, model) not in by:
                continue
            rs = by[(c, model)]
            x = 100 * sum(is_flagged(r) for r in rs) / len(rs)
            y = 100 * sum(_b(r["jk_b_correct"]) for r in rs) / len(rs)
            ax_c.plot(x, y, ls="none", ms=4.6, mew=1, **kw)
            ox, oy, lead = offsets.get((c, model), (4, 0, False))
            ax_c.annotate(short, (x, y), xytext=(ox, oy), textcoords="offset points", fontsize=6,
                          color=kw["color"], va="center", ha="right" if ox < -5 else "left",
                          arrowprops=dict(arrowstyle="-", color=kw["color"], lw=0.4, shrinkA=0, shrinkB=2.5) if lead else None)
    ax_c.axhline(50, color=GREY, lw=0.7, ls="--", zorder=0)
    ax_c.text(35.5, 51, "chance", color=GREY, fontsize=6, ha="right", va="bottom")
    ax_c.set_xlim(-2, 36)
    ax_c.set_ylim(20, 105)
    ax_c.set_xlabel("Boards flagged by the cost rule (%)")
    ax_c.set_ylabel("B claimed the jackpot (%)")
    ax_c.legend(handles=[Line2D([], [], marker="o", color=NAVY, ls="none", ms=4.2, label="GPT-5 Mini"),
                         Line2D([], [], marker="s", color=ORANGE, mfc="white", ls="none", ms=4.2, label="Qwen3-32B (exploratory)")],
                loc="lower left", frameon=False, bbox_to_anchor=(0.0, 0.0))


def main():
    by = load()
    plt.rcParams.update({"font.size": 7, "axes.titlesize": 7.5, "axes.labelsize": 7,
                         "xtick.labelsize": 6, "ytick.labelsize": 6.5, "legend.fontsize": 6,
                         "axes.spines.top": False, "axes.spines.right": False})
    OUT.mkdir(parents=True, exist_ok=True)
    # Figure 1: hit rate by condition, both models
    fig, ax = plt.subplots(figsize=(7, 2.6))
    draw_a(ax, by)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.97, bottom=0.17)
    fig.savefig(OUT / "jackpot_figure1.png", dpi=300)
    fig.savefig(OUT / "jackpot_figure1.pdf")
    # Figure 2: hit rate against boards flagged by the cost rule
    fig2, ax = plt.subplots(figsize=(4.6, 3.0))
    draw_c(ax, by)
    fig2.subplots_adjust(left=0.12, right=0.97, top=0.97, bottom=0.14)
    fig2.savefig(OUT / "jackpot_figure2.png", dpi=300)
    fig2.savefig(OUT / "jackpot_figure2.pdf")
    # Figure B1 (appendix): gpt-5-mini, boards where A blocked vs all other boards
    fig3, ax = plt.subplots(figsize=(7, 2.6))
    draw_b(ax, by)
    fig3.subplots_adjust(left=0.075, right=0.985, top=0.97, bottom=0.17)
    fig3.savefig(OUT / "jackpot_figureB1.png", dpi=300)
    fig3.savefig(OUT / "jackpot_figureB1.pdf")
    print("wrote jackpot_figure1, jackpot_figure2 and jackpot_figureB1 (.png, .pdf) in", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
