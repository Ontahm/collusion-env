"""Charts for reports, from a run's index.csv or a board study's boards.csv (PNG and PDF).

    python -m analysis.figures <run dir>            # also done by `python -m analysis.summarize`
    python -m analysis.figures --boards <board study dir>

Run charts (each only when the run has the data for it):
  hv_capture        coalition holds the high-value ticket, per condition (rate, 95% CI)
  same_issue        colluders on one issue, and collusive matches (same-issue objective)
  by_board_kind     the main rate on conflict vs costless boards (spec/09)
  by_round          the main rate per round (games of several rounds)
  team_loss         optimum minus team score (mean, 95% CI)
  colosseum         regret gap (the paper's coalition advantage) and reward gap
  reservations      reservation-round signals (games with reservations)
  health            failed tool results, turns without a claim, missing claims
Board-study charts: conflict share by board size, and the distribution of the price of collusion.
Colours: Okabe-Ito (readable with colour-vision deficiencies).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

from analysis.stats import wilson  # noqa: E402

PALETTE = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442", "#000000"]


def style() -> None:
    plt.rcParams.update({
        "figure.dpi": 150, "savefig.dpi": 150, "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.3,
        "grid.linewidth": 0.5, "legend.frameon": False, "savefig.bbox": "tight",
    })


def outside_legend(ax, **kwargs) -> None:
    """Legend to the right of the plot, so it never covers data."""
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=7, **kwargs)


def save(fig, out_dir: Path, name: str) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [out_dir / f"{name}.png", out_dir / f"{name}.pdf"]
    for p in paths:
        fig.savefig(p)
    plt.close(fig)
    return paths


# --- reading ----------------------------------------------------------------------------------------


def _bool(v) -> Optional[bool]:
    return {"True": True, "False": False, True: True, False: False}.get(v)


def _num(v) -> Optional[float]:
    try:
        x = float(v)
        return None if math.isnan(x) else x
    except (TypeError, ValueError):
        return None


def lo_err(c) -> float:
    """Whisker lengths, clamped at 0: a Wilson bound can miss the rate by a rounding error at 0% or 100%."""
    return max(0.0, c[0] - c[1])


def hi_err(c) -> float:
    return max(0.0, c[2] - c[0])


def rate(rows: Sequence[dict], key: str) -> Optional[Tuple[float, float, float, int]]:
    vals = [b for b in (_bool(r.get(key)) for r in rows) if b is not None]
    if not vals:
        return None
    k, n = sum(vals), len(vals)
    lo, hi = wilson(k, n)
    return k / n, lo, hi, n


def mean_ci(rows: Sequence[dict], key: str) -> Optional[Tuple[float, float, int]]:
    vals = [x for x in (_num(r.get(key)) for r in rows) if x is not None]
    if not vals:
        return None
    m = sum(vals) / len(vals)
    if len(vals) < 2:
        return m, 0.0, len(vals)
    sd = math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1))
    return m, 1.96 * sd / math.sqrt(len(vals)), len(vals)


# --- generic plots -----------------------------------------------------------------------------------


def grouped_rates(groups: Dict[Tuple[str, str], List[dict]], keys: Sequence[Tuple[str, str]], title: str,
                  ylabel: str = "share of rounds") -> Optional[plt.Figure]:
    """Bars: x = condition (and model when several), one bar per key; Wilson 95% CI."""
    labels = [f"{c}\n{m}" if len({m for _, m in groups}) > 1 else c for c, m in groups]
    cells = [[rate(rows, k) for k, _ in keys] for rows in groups.values()]
    if not any(c for row in cells for c in row):
        return None
    fig, ax = plt.subplots(figsize=(max(4.0, 1.1 * len(labels) * max(1, len(keys)) * 0.7 + 1.5), 3.2))
    width = 0.8 / len(keys)
    for j, (_, name) in enumerate(keys):
        xs, ys, err, ns = [], [], [[], []], []
        for i, row in enumerate(cells):
            c = row[j]
            if c is None:
                continue
            xs.append(i + (j - (len(keys) - 1) / 2) * width)
            ys.append(c[0]); err[0].append(lo_err(c)); err[1].append(hi_err(c)); ns.append(c[3])
        ax.bar(xs, ys, width * 0.92, yerr=err, capsize=3, color=PALETTE[j % len(PALETTE)], label=name,
               error_kw={"linewidth": 0.8})
        for x, y, n in zip(xs, ys, ns):
            ax.text(x, 0.01, f"n={n}", ha="center", va="bottom", fontsize=6, color="white" if y > 0.08 else "black")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylim(0, 1)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if len(keys) > 1:
        outside_legend(ax)
    ax.text(1.0, -0.22 if len(labels) < 6 else -0.3, "bars: share of rounds; whiskers: Wilson 95% CI",
            transform=ax.transAxes, ha="right", fontsize=6, color="grey")
    return fig


def grouped_means(groups: Dict[Tuple[str, str], List[dict]], keys: Sequence[Tuple[str, str]], title: str,
                  ylabel: str) -> Optional[plt.Figure]:
    labels = [f"{c}\n{m}" if len({m for _, m in groups}) > 1 else c for c, m in groups]
    cells = [[mean_ci(rows, k) for k, _ in keys] for rows in groups.values()]
    if not any(c for row in cells for c in row):
        return None
    fig, ax = plt.subplots(figsize=(max(4.0, 0.9 * len(labels) * max(1, len(keys)) * 0.7 + 1.5), 3.2))
    width = 0.8 / len(keys)
    for j, (_, name) in enumerate(keys):
        for i, row in enumerate(cells):
            c = row[j]
            if c is None:
                continue
            x = i + (j - (len(keys) - 1) / 2) * width
            ax.errorbar([x], [c[0]], yerr=[[c[1]], [c[1]]], fmt="o", color=PALETTE[j % len(PALETTE)], capsize=3,
                        markersize=4, label=name if i == 0 else None)
    ax.axhline(0, color="grey", linewidth=0.6)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if len(keys) > 1:
        outside_legend(ax)
    ax.text(1.0, -0.22, "points: mean over rounds; whiskers: 95% CI (normal approximation)",
            transform=ax.transAxes, ha="right", fontsize=6, color="grey")
    return fig


# --- run charts -------------------------------------------------------------------------------------


def main_rate_key(rows: Sequence[dict]) -> Optional[Tuple[str, str, str]]:
    """(rate column, conflict column, label) of the run's objective."""
    objectives = {r.get("objective") for r in rows}
    if "high_value_ticket" in objectives:
        return "hv_captured_by_coalition", "hv_conflict", "coalition holds the high-value ticket"
    if "same_issue" in objectives:
        return "same_issue_match", "same_issue_conflict", "colluders on the same issue"
    return None


def run_figures(run_dir: Path) -> List[Path]:
    style()
    with (run_dir / "index.csv").open() as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return []
    out = run_dir / "figures"
    groups: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["condition"], r["model"])].append(r)
    groups = dict(sorted(groups.items()))
    paths: List[Path] = []

    def keep(fig, name):
        if fig is not None:
            paths.extend(save(fig, out, name))

    hv = {g: rs for g, rs in groups.items() if any(r.get("hv_captured_by_coalition") in ("True", "False") for r in rs)}
    if hv:
        keep(grouped_rates(hv, [("hv_captured_by_coalition", "coalition"), ("hv_captured_by_honest", "an honest agent")],
                           "Who ends up holding the high-value ticket"), "hv_capture")
    si = {g: rs for g, rs in groups.items() if any(r.get("objective") == "same_issue" for r in rs)}
    if si:
        keep(grouped_rates(si, [("same_issue_match", "same issue"), ("collusive_match", "same issue at a cost")],
                           "Colluders on the same issue"), "same_issue")

    main = main_rate_key(rows)
    if main:
        key, flag, label = main
        split = {}
        for g, rs in groups.items():
            for value, name in (("True", "conflict"), ("False", "costless")):
                sub = [r for r in rs if r.get(flag) == value]
                if sub:
                    split.setdefault(g, {})[name] = sub
        if split:
            fig, ax = plt.subplots(figsize=(max(4.0, 1.2 * len(split) + 1.5), 3.2))
            for j, name in enumerate(("conflict", "costless")):
                for i, (g, parts) in enumerate(split.items()):
                    c = rate(parts.get(name, []), key)
                    if c is None:
                        continue
                    x = i + (j - 0.5) * 0.38
                    ax.bar([x], [c[0]], 0.35, yerr=[[lo_err(c)], [hi_err(c)]], capsize=3, color=PALETTE[j],
                           label=name if i == 0 else None, error_kw={"linewidth": 0.8})
                    ax.text(x, 0.01, f"n={c[3]}", ha="center", va="bottom", fontsize=6,
                            color="white" if c[0] > 0.08 else "black")
            labels = [f"{c}\n{m}" if len({m for _, m in split}) > 1 else c for c, m in split]
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, fontsize=8)
            ax.set_ylim(0, 1)
            ax.set_ylabel("share of rounds")
            ax.set_title(f"{label.capitalize()}, by board kind")
            outside_legend(ax, title="board (spec/09)", title_fontsize=7)
            ax.text(1.0, -0.22, "conflict: reaching the coalition's goal costs the team; costless: it does not",
                    transform=ax.transAxes, ha="right", fontsize=6, color="grey")
            keep(fig, "by_board_kind")

        if any(r["round"] != "0" for r in rows):
            fig, ax = plt.subplots(figsize=(5.5, 3.2))
            for i, (g, rs) in enumerate(groups.items()):
                by_round = defaultdict(list)
                for r in rs:
                    by_round[int(r["round"])].append(r)
                pts = [(k + 1, rate(v, key)) for k, v in sorted(by_round.items())]
                pts = [(x, c) for x, c in pts if c is not None]
                if not pts:
                    continue
                xs = [x for x, _ in pts]
                ax.plot(xs, [c[0] for _, c in pts], marker="o", markersize=3, color=PALETTE[i % len(PALETTE)],
                        label=g[0] if len({m for _, m in groups}) == 1 else f"{g[0]} / {g[1]}")
                ax.fill_between(xs, [c[1] for _, c in pts], [c[2] for _, c in pts], color=PALETTE[i % len(PALETTE)], alpha=0.12)
            ax.set_ylim(0, 1)
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            ax.set_xlabel("round")
            ax.set_ylabel("share of games")
            ax.set_title(f"{label.capitalize()}, by round")
            outside_legend(ax)
            keep(fig, "by_round")

    keep(grouped_means(groups, [("team_loss", "team loss")], "Team loss (optimum minus team score)", "score units"), "team_loss")
    keep(grouped_means(groups, [("regret_gap", "regret gap (paper's coalition advantage)"), ("reward_gap", "reward gap")],
                       "Coalition advantage (Colosseum's two measures)", "score units"), "colosseum")

    signals = _reservation_signals(run_dir)
    if signals:
        fig, axes = plt.subplots(1, 2, figsize=(8, 3.2), sharey=True)
        for ax, (name, title) in zip(axes, (("same_issue", "colluders reserve on one issue"),
                                             ("hv", "a colluder reserves the high-value ticket"))):
            for i, (g, per_pass) in enumerate(signals.items()):
                pts = [(p + 1, rate([{"v": str(v)} for v in vals], "v")) for p, vals in sorted(per_pass[name].items()) if vals]
                if not pts:
                    continue
                shift = (i - (len(signals) - 1) / 2) * 0.06          # side by side, so no series hides another
                ax.errorbar([x + shift for x, _ in pts], [c[0] for _, c in pts],
                            yerr=[[lo_err(c) for _, c in pts], [hi_err(c) for _, c in pts]],
                            marker="o", markersize=3, capsize=3, color=PALETTE[i % len(PALETTE)], label=g)
            ax.set_title(title)
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            ax.set_xlabel("reservation round")
            ax.set_ylim(0, 1)
        axes[0].set_ylabel("share of rounds")
        outside_legend(axes[1])
        keep(fig, "reservations")

    keep(grouped_means(groups, [("failed_tool_results", "failed tool results"), ("turns_without_commit", "turns without a claim"),
                                ("missing_claims", "missing claims")], "Health (per round)", "count per round"), "health")
    return paths


def _reservation_signals(run_dir: Path) -> Dict[str, Dict[str, Dict[int, list]]]:
    """Per condition: per reservation pass, the colluders' same-issue and high-value reservation flags."""
    out: Dict[str, Dict[str, Dict[int, list]]] = {}
    for ep in run_dir.glob("episodes/**/episode.json"):
        data = json.loads(ep.read_text())
        if data.get("status") != "complete":
            continue
        for rnd in data.get("rounds", []):
            m = rnd.get("metrics", {})
            if "reservation_colluders_same_issue" not in m:
                continue
            g = out.setdefault(data["condition"], {"same_issue": defaultdict(list), "hv": defaultdict(list)})
            for i, v in enumerate(m["reservation_colluders_same_issue"]):
                g["same_issue"][i].append(v)
            for i, v in enumerate(m.get("reservation_hv_by_colluder") or []):
                if v is not None:
                    g["hv"][i].append(v)
    return dict(sorted(out.items()))


# --- board study charts --------------------------------------------------------------------------------


def board_figures(study_dir: Path, agg=None) -> List[Path]:
    """Charts of a board study, from its running aggregate (analysis/board_study.py) or, when
    called on a finished study folder, from a single streaming pass over boards.csv."""
    style()
    if agg is None:
        from analysis.board_study import Aggregate, COLUMNS
        agg = Aggregate()
        with (study_dir / "boards.csv").open() as f:
            for row in csv.DictReader(f):
                agg.add([_cast(row[c]) for c in COLUMNS])
    groups = sorted({k[:2] for k in agg.flags} | {k[:2] for k in agg.values})
    sizes = sorted({g[0] for g in groups})
    objectives = sorted({g[1] for g in groups})
    paths: List[Path] = []

    fig, ax = plt.subplots(figsize=(5.5, 3.4))
    # The same-issue flag does not depend on the objective: read it from the first objective.
    series = [("same_issue_conflict", "same issue", objectives[0])] + \
             [("hv_conflict", f"high-value ({o})", o) for o in objectives if o.startswith("hv")]
    for i, (flag, label, obj) in enumerate(series):
        pts = []
        for s in sizes:
            r = agg.rate((s, obj), flag)
            if r:
                lo, hi = wilson(*r)
                p = r[0] / r[1]
                pts.append((s, (p, lo, hi, r[1])))
        if pts:
            ax.errorbar([s for s, _ in pts], [c[0] for _, c in pts],
                        yerr=[[lo_err(c) for _, c in pts], [hi_err(c) for _, c in pts]],
                        marker="o", markersize=4, capsize=3, color=PALETTE[i % len(PALETTE)], label=label)
    if len(sizes) > 1 and max(sizes) / max(1, min(sizes)) > 20:
        ax.set_xscale("log")
        ax.minorticks_off()
        labelled, last = [], None                      # label sizes far enough apart on the log axis
        for s in sizes:
            if last is None or math.log10(s) - math.log10(last) >= 0.12:
                labelled.append(s)
                last = s
    else:
        labelled = sizes
    ax.set_xticks(labelled)
    ax.set_xticklabels([str(s) for s in labelled], fontsize=7)
    ax.set_ylim(0, 1)
    ax.set_xlabel("tasks on the board")
    ax.set_ylabel("share of boards")
    ax.set_title("Boards where reaching the coalition's goal costs the team")
    outside_legend(ax)
    ax.text(1.0, -0.25, "conflict: price of collusion > 0 (exact, no model); whiskers: Wilson 95% CI",
            transform=ax.transAxes, ha="right", fontsize=6, color="grey")
    paths.extend(save(fig, study_dir / "figures", "conflict_by_size"))

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.2))
    hv_obj = next((o for o in objectives if o == "hv_random"), next((o for o in objectives if o.startswith("hv")), objectives[-1]))
    shown = sizes if len(sizes) <= 6 else sorted({sizes[0], sizes[len(sizes) // 3], sizes[2 * len(sizes) // 3], sizes[-1]})
    for ax, (key, obj, title) in zip(axes, (("price_same_issue", objectives[0], "same issue"),
                                            ("price_hv", hv_obj, "high-value ticket"))):
        for i, s in enumerate(shown):
            vals = sorted(agg.values.get((s, obj, key), []))
            if not vals:
                continue
            ax.step(vals, [(k + 1) / len(vals) for k in range(len(vals))], where="post", color=PALETTE[i % len(PALETTE)],
                    label=f"{s} tasks")
        ax.set_xscale("symlog", linthresh=0.1)
        ax.set_xlabel("price of collusion (score units)")
        ax.set_title(f"Price of collusion: {title}")
        ax.set_ylim(0, 1)
    axes[0].set_ylabel("share of boards with price <= x")
    outside_legend(axes[1])
    paths.extend(save(fig, study_dir / "figures", "price_distribution"))
    return paths


def _cast(v: str):
    if v in ("", "None"):
        return None
    if v in ("True", "False"):
        return v == "True"
    try:
        return float(v) if any(ch in v for ch in ".e") or not v.lstrip("-").isdigit() else int(v)
    except ValueError:
        return v


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path")
    parser.add_argument("--boards", action="store_true", help="path is a board-study folder")
    args = parser.parse_args(argv)
    path = Path(args.path)
    paths = board_figures(path) if args.boards else run_figures(path)
    for p in paths:
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
