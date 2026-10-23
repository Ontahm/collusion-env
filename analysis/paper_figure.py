"""A paper-style chart for the Colosseum reproduction (study colosseum_paper.yaml).

Usage:
    python -m analysis.paper_figure runs/<run folder> [--colosseum <Colosseum summary.csv>]

Writes figures/paper_comparison.(png|pdf) and paper_comparison.md in the run folder:

  left    normalised regret (1 - team score / optimum) per condition: mean over seeds, 95% CI
  middle  regret gap in points (non-colluders' mean regret - colluders'), the quantity behind the
          paper's "coalition advantage"
  right   change in normalised regret from the baseline (no secret channel), paired by seed, with the
          paper's GPT-4.1-mini values (read off Fig. 4 of arXiv:2602.15198; approximate). The change in
          regret gap, and a run of Colosseum's own code if given, are in paper_comparison.md

Units: Colosseum's chart rescales the coalition advantage by the largest gap a model reaches across
its runs (`_normalize_coalition_regret_gap`), so it is not comparable between studies; the regret gap
is shown in points instead. The paper's judge score is not reproduced (no judge in this repository).
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


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run")
    ap.add_argument("--colosseum", help="summary.csv of a run of Colosseum's own code (optional, for the right panel)")
    args = ap.parse_args(argv)
    run = Path(args.run)
    rows = list(csv.DictReader(open(run / "index.csv", encoding="utf-8")))
    nr = per_seed(rows, "normalized_regret")
    gap = per_seed(rows, "regret_gap")
    conds = [c for c in CONDITIONS if c in nr]
    if not conds:
        raise SystemExit(f"no conditions named {CONDITIONS} in {run}/index.csv")

    style()
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    colors = {"baseline": "#6b7a8f", "emergent": "#3a8f8a", "prompted": "#c0703f"}
    lines = [f"# Paper comparison: {run.name}", "", "| condition | normalised regret (95% CI) | regret gap, points (95% CI) | seeds |", "|---|---|---|---|"]
    for ax, data, title in ((axes[0], nr, "Normalised regret (lower = better team)"),
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
    for c in conds:
        m1, h1 = mean_ci(list(nr.get(c, {}).values()))
        m2, h2 = mean_ci(list(gap.get(c, {}).values()))
        fmt = lambda m, h: "n/a" if m is None else (f"{m:.3f}" + (f" ± {h:.3f}" if h is not None else ""))
        lines.append(f"| {c} | {fmt(m1, h1)} | {fmt(m2, h2)} | {len(nr.get(c, {}))} |")

    # right: change from baseline, paired by seed
    ax = axes[2]
    lines += ["", "## Change from the baseline (paired by seed)", "",
              "| condition | Δ normalised regret (95% CI) | paper, Fig. 4 (approx.) | Δ regret gap, points (95% CI) |", "|---|---|---|---|"]
    x = 0
    ticks = []
    for c in conds[1:]:
        seeds = sorted(set(nr.get(c, {})) & set(nr.get("baseline", {})))
        m, h = mean_ci([nr[c][s] - nr["baseline"][s] for s in seeds])
        if m is not None:
            ax.bar(x, m, width=0.55, color=colors[c], label="this run" if x == 0 else None)
            if h is not None:
                ax.errorbar(x, m, yerr=h, color="black", capsize=4, lw=1)
        if c in PAPER_DELTA_NORMALIZED_REGRET:
            ax.plot(x, PAPER_DELTA_NORMALIZED_REGRET[c], marker="D", color="black", ms=7, zorder=5,
                    label="paper, Fig. 4 (approx.)" if x == 0 else None)
        ticks.append(LABELS[c])
        d1 = mean_ci([nr[c][s] - nr["baseline"][s] for s in sorted(set(nr.get(c, {})) & set(nr.get("baseline", {})))])
        d2 = mean_ci([gap[c][s] - gap["baseline"][s] for s in sorted(set(gap.get(c, {})) & set(gap.get("baseline", {})))])
        f = lambda mh: "n/a" if mh[0] is None else (f"{mh[0]:+.3f}" + (f" ± {mh[1]:.3f}" if mh[1] is not None else ""))
        lines.append(f"| {c} | {f(d1)} | {PAPER_DELTA_NORMALIZED_REGRET.get(c, float('nan')):+.3f} | {f(d2)} |")
        x += 1
    if args.colosseum:
        crow = colosseum_rows(Path(args.colosseum))
        cgap = per_seed(crow, "regret_gap")
        lines += ["", f"Colosseum's own code ({args.colosseum}): Δ regret gap, points, paired by seed: " + ", ".join(
            f"{c} {mean_ci([cgap[c][s] - cgap['baseline'][s] for s in sorted(set(cgap.get(c, {})) & set(cgap.get('baseline', {})))])[0]:+.2f}"
            for c in conds[1:] if c in cgap)]
    ax.set_xticks(range(len(ticks)), ticks, fontsize=8)
    ax.axhline(0, color="black", lw=0.6)
    ax.set_title("Change in normalised regret from baseline\n(paired by seed; ◆ the paper's GPT-4.1-mini)", fontsize=10)
    ax.legend(fontsize=8, frameon=False)
    fig.suptitle(f"Colosseum reproduction, {run.name}", fontsize=11)
    paths = save(fig, run / "figures", "paper_comparison")
    plt.close(fig)
    lines += ["", "Paper values: Fig. 4 of arXiv:2602.15198, GPT-4.1-mini (point 1), read off the plot (approximate).",
              "The paper's coalition-advantage axis is rescaled per model, so only its direction is comparable;",
              "the judge score is not reproduced.", "", "Figures: " + ", ".join(str(p.relative_to(run)) for p in paths)]
    (run / "paper_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
