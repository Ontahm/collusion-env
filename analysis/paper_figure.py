"""A paper-style chart for the Colosseum reproduction (study colosseum_paper.yaml).

Usage:
    python -m analysis.paper_figure runs/<run folder> [--colosseum <Colosseum summary.csv>]

Writes, in the run folder:

  figures/paper_comparison.(png|pdf)   our run next to the paper, as the paper reports it (Fig. 4 of
      arXiv:2602.15198, GPT-4.1-mini, read off the plot, approximate): the change from the
      no-secret-channel control, for each secret-channel condition, in
        - team regret (normalised regret: 1 - team score / optimum; higher = the team does worse)
        - coalition advantage (Colosseum's: the non-colluders' mean regret minus the colluders',
          rescaled to [0, 1] by the largest absolute gap of the model's runs, as Colosseum's
          `_normalize_coalition_regret_gap`; higher = the colluders do better)
      Ours: mean over seeds, paired by seed, 95% interval. Paper: one value, no interval published.
  figures/paper_comparison_conditions.(png|pdf)   our run only: both measures per condition
  paper_comparison.md   the numbers

The rescaling divides by the largest gap in *this* run's data (the paper: in its runs), so the
advantage values are comparable in kind, not exactly. The judge score is not reproduced.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt

from analysis.figures import save, style

CONDITIONS = ("baseline", "emergent", "prompted")
LABELS = {"baseline": "No secret channel", "emergent": "Secret channel,\nno instruction", "prompted": "Secret channel,\n\"simple\" instruction"}
# Fig. 4 of the paper, GPT-4.1-mini (point 1), change from the no-channel control; read off the plot.
# The regret axis of Fig. 4 puts "More" (more regret) at the top, where its tick labels are negative;
# the text says prompted collusion "negatively affect[s] the cooperative system". So the values below
# are condition minus control in regret, positive = the team does worse. Approximate.
PAPER_DELTA_NORMALIZED_REGRET = {"emergent": 0.035, "prompted": 0.07}
# Fig. 4, left panel ("Change in Coalition Advantage on Jira"), GPT-4.1-mini, read off the plot.
PAPER_DELTA_ADVANTAGE = {"emergent": 0.08, "prompted": 0.17}
T95 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23, 15: 2.13, 20: 2.09}


def t95(n: int) -> float:
    return T95.get(n - 1, 1.96) if n > 1 else float("nan")


def mean_ci(values: List[float]) -> Tuple[Optional[float], Optional[float]]:
    values = [v for v in values if v is not None and math.isfinite(v)]
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], None
    return mean(values), t95(len(values)) * stdev(values) / math.sqrt(len(values))


def per_seed(rows: List[dict], key: str) -> Dict[str, Dict[int, float]]:
    out: Dict[str, Dict[int, List[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        try:
            out[r["condition"]][int(r["seed"])].append(float(r[key]))
        except (TypeError, ValueError, KeyError):
            continue
    return {c: {s: mean(v) for s, v in seeds.items()} for c, seeds in out.items()}


def colosseum_rows(path: Path) -> List[dict]:
    """A Colosseum run's summary.csv mapped to this repository's columns."""
    rows = []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        cond = "baseline" if r.get("secret_channel_enabled") == "False" else (
            "emergent" if r.get("prompt_variant") == "control" else "prompted")
        try:
            gap = float(r["noncoalition_mean_regret"]) - float(r["coalition_mean_regret"])
        except (TypeError, ValueError, KeyError):
            continue
        rows.append({"condition": cond, "seed": r["seed"], "regret_gap": gap, "normalized_regret": r.get("normalized_regret", "")})
    return rows


def rescaled(gaps: Dict[str, Dict[int, float]]) -> Dict[str, Dict[int, float]]:
    """Colosseum's coalition advantage: 0.5 + gap / (2 x largest |gap| of the model's runs), in [0, 1]."""
    top = max((abs(v) for seeds in gaps.values() for v in seeds.values()), default=0.0)
    if top == 0.0:
        return {c: {s: 0.5 for s in seeds} for c, seeds in gaps.items()}
    return {c: {s: min(1.0, max(0.0, 0.5 + v / (2 * top))) for s, v in seeds.items()} for c, seeds in gaps.items()}


def paired_delta(data: Dict[str, Dict[int, float]], c: str) -> Tuple[Optional[float], Optional[float]]:
    seeds = sorted(set(data.get(c, {})) & set(data.get("baseline", {})))
    return mean_ci([data[c][s] - data["baseline"][s] for s in seeds])


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run")
    ap.add_argument("--colosseum", help="summary.csv of a run of Colosseum's own code (optional, for the table)")
    args = ap.parse_args(argv)
    run = Path(args.run)
    rows = list(csv.DictReader(open(run / "index.csv", encoding="utf-8")))
    nr = per_seed(rows, "normalized_regret")
    gap = per_seed(rows, "regret_gap")
    adv = rescaled(gap)
    conds = [c for c in CONDITIONS if c in nr]
    if "baseline" not in conds or len(conds) < 2:
        raise SystemExit(f"need the conditions {CONDITIONS} in {run}/index.csv")
    treated = conds[1:]
    n_seeds = len(nr["baseline"])
    style()
    ours_color, paper_color = "#2f6f9f", "#b9b9b9"

    # 1. our run next to the paper -----------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    panels = ((axes[0], nr, PAPER_DELTA_NORMALIZED_REGRET, "Change in team regret\n(higher = the team does worse)"),
              (axes[1], adv, PAPER_DELTA_ADVANTAGE, "Change in coalition advantage\n(higher = the colluders do better)"))
    for ax, data, paper, title in panels:
        for i, c in enumerate(treated):
            m, h = paired_delta(data, c)
            if m is not None:
                ax.bar(i - 0.19, m, width=0.36, color=ours_color, label=f"Our run (gpt-4.1-mini, {n_seeds} seeds)" if i == 0 else None)
                if h is not None:
                    ax.errorbar(i - 0.19, m, yerr=h, color="black", capsize=4, lw=1)
                ax.annotate(f"{m:+.3f}", (i - 0.19, m), textcoords="offset points", xytext=(0, 4 if m >= 0 else -12),
                            ha="center", fontsize=8)
            if c in paper:
                ax.bar(i + 0.19, paper[c], width=0.36, color=paper_color, hatch="//", edgecolor="#777777",
                       label="Paper, Fig. 4 (approx.)" if i == 0 else None)
                ax.annotate(f"{paper[c]:+.3f}", (i + 0.19, paper[c]), textcoords="offset points", xytext=(0, 4),
                            ha="center", fontsize=8)
        ax.set_xticks(range(len(treated)), [LABELS[c] for c in treated], fontsize=9)
        ax.axhline(0, color="black", lw=0.6)
        ax.set_title(title, fontsize=10)
        ax.legend(fontsize=8, frameon=False, loc="upper left")
    fig.suptitle("Colosseum's Jira result: our reproduction vs the paper (change from no secret channel)", fontsize=11)
    paths = save(fig, run / "figures", "paper_comparison")
    plt.close(fig)

    # 2. our run per condition -----------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.0))
    colors = {"baseline": "#6b7a8f", "emergent": "#3a8f8a", "prompted": "#c0703f"}
    for ax, data, title in ((axes[0], nr, "Team regret (normalised; lower = better team)"),
                            (axes[1], gap, "Regret gap, points (higher = colluders do better)")):
        for i, c in enumerate(conds):
            m, h = mean_ci(list(data.get(c, {}).values()))
            if m is None:
                continue
            ax.bar(i, m, color=colors[c], width=0.65)
            if h is not None:
                ax.errorbar(i, m, yerr=h, color="black", capsize=4, lw=1)
        ax.set_xticks(range(len(conds)), [LABELS[c] for c in conds], fontsize=8)
        ax.set_title(title, fontsize=10)
        ax.axhline(0, color="black", lw=0.6)
    fig.suptitle(f"Our run only, per condition ({run.name})", fontsize=11)
    paths += save(fig, run / "figures", "paper_comparison_conditions")
    plt.close(fig)

    # table ------------------------------------------------------------------------------------------
    fmt = lambda mh: "n/a" if mh[0] is None else (f"{mh[0]:+.3f}" + (f" ± {mh[1]:.3f}" if mh[1] is not None else ""))
    lines = [f"# Paper comparison: {run.name}", "", "## Change from the no-secret-channel control (ours: paired by seed, 95% interval)", "",
             "| condition | team regret, ours | team regret, paper | coalition advantage, ours | coalition advantage, paper | regret gap (points), ours |",
             "|---|---|---|---|---|---|"]
    for c in treated:
        lines.append(f"| {c} | {fmt(paired_delta(nr, c))} | {PAPER_DELTA_NORMALIZED_REGRET[c]:+.3f} | "
                     f"{fmt(paired_delta(adv, c))} | {PAPER_DELTA_ADVANTAGE[c]:+.3f} | {fmt(paired_delta(gap, c))} |")
    lines += ["", "## Our run per condition (mean over seeds, 95% interval)", "",
              "| condition | team regret | regret gap, points | seeds |", "|---|---|---|---|"]
    for c in conds:
        m1, h1 = mean_ci(list(nr.get(c, {}).values()))
        m2, h2 = mean_ci(list(gap.get(c, {}).values()))
        lines.append(f"| {c} | {fmt((m1, h1))} | {fmt((m2, h2))} | {len(nr.get(c, {}))} |")
    if args.colosseum:
        cgap = per_seed(colosseum_rows(Path(args.colosseum)), "regret_gap")
        lines += ["", f"Colosseum's own code ({args.colosseum}), change in regret gap (points), paired by seed: " +
                  ", ".join(f"{c} {fmt(paired_delta(cgap, c))}" for c in treated if c in cgap)]
    lines += ["", "Paper: Fig. 4 of arXiv:2602.15198, GPT-4.1-mini (point 1), read off the plot (approximate); its",
              "regret axis is drawn with \"More\" at the top. Coalition advantage rescaled as Colosseum does, by the",
              "largest gap in each study's own runs, so comparable in kind, not exactly. No judge score.",
              "", "Figures: " + ", ".join(str(p.relative_to(run)) for p in paths)]
    (run / "paper_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
