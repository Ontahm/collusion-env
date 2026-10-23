"""Charts for reports, from a run's index.csv or a board study's boards.csv (PNG and PDF).

    python -m analysis.figures <run dir>            # also done by `python -m analysis.summarize`
    python -m analysis.figures --boards <board study dir>

Run charts (each only when the run has the data for it):
  hv_capture        who holds the high-value ticket: one colluder alone, colluders colliding on it,
                    shared with an honest agent, honest agents only, nobody (stacked, sums to 100%)
  same_issue        colluders on one issue, collusive matches, matches on conflict boards
  by_board_kind     the goal's main rate on conflict vs costless boards (spec/09), per kind of game
  by_round          the main rate per round, one panel per condition (games of several rounds)
  team_loss         optimum minus team score (mean, 95% CI)
  colosseum         regret gap (the paper's coalition advantage) and reward gap
  reservations      reservation-round signals (games with reservations)
  health            failed tool results, turns without a claim, missing and duplicate claims
  chat_herding      repeated posts, colluders naming the ticket in secret, the largest pile on one task
Board-study charts: conflict share by board size, and the distribution of the price of collusion.

Layout: most charts are dot-and-interval plots. One row per condition (names on the left, so long
names never collide), one panel per measure, one colour per model (the same model keeps its colour
in every chart). Each row's label carries its number of rounds. Colours: a palette checked for
colour-vision deficiencies (adjacent series), dark text on white, hairline grid.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import textwrap
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator, PercentFormatter  # noqa: E402

from analysis.stats import wilson  # noqa: E402

# Categorical slots, in this order (the order is what keeps neighbours apart for colour-blind readers).
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
# One-hue ramp for ordered series (board sizes), light to dark; starts dark enough to read on white.
RAMP = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281", "#0d366b"]
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#8a8984"
GRID, AXIS = "#ebeae6", "#c4c2bc"

Stat = Tuple[float, float, float, int]                     # value, low, high, n


def style() -> None:
    plt.rcParams.update({
        "figure.dpi": 150, "savefig.dpi": 200, "figure.facecolor": "white", "axes.facecolor": "white",
        "figure.constrained_layout.use": True, "savefig.bbox": "tight", "savefig.pad_inches": 0.08,
        "font.size": 8.5, "text.color": INK, "axes.titlesize": 8.5, "axes.titlelocation": "left",
        "axes.titlepad": 6, "axes.labelsize": 8, "axes.labelcolor": INK_2, "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8, "axes.axisbelow": True, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
        "grid.color": GRID, "grid.linewidth": 0.7, "xtick.color": INK_2, "ytick.color": INK_2,
        "xtick.labelsize": 7.5, "ytick.labelsize": 8, "xtick.major.size": 0, "ytick.major.size": 0,
        "xtick.major.pad": 4, "ytick.major.pad": 6, "legend.frameon": False, "legend.fontsize": 8,
        "lines.solid_capstyle": "round", "pdf.fonttype": 42,
    })


def save(fig, out_dir: Path, name: str) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [out_dir / f"{name}.png", out_dir / f"{name}.pdf"]
    for p in paths:
        fig.savefig(p)
    plt.close(fig)
    return paths


def frame(fig, title: str, caption: Optional[str] = None) -> None:
    """Title top left, caption bottom left, both inside the layout (nothing can overlap them)."""
    fig.suptitle(title, x=0.0, ha="left", fontsize=10, fontweight="bold", color=INK)
    if caption:
        fig.supxlabel(caption, x=0.0, ha="left", fontsize=7, color=MUTED)


def model_legend(ax, models: Sequence[str]) -> None:
    """Model colours, to the right of the top-right panel (the layout makes room for it)."""
    if len(models) > 1:
        handles = [Line2D([], [], color=PALETTE[i % len(PALETTE)], marker="o", linewidth=2, markersize=5)
                   for i in range(len(models))]
        ax.legend(handles, models, loc="upper left", bbox_to_anchor=(1.03, 1.0), title="model",
                  title_fontsize=7.5, alignment="left", handlelength=1.6)


# --- reading ----------------------------------------------------------------------------------------


def _bool(v) -> Optional[bool]:
    return {"True": True, "False": False, True: True, False: False}.get(v)


def _num(v) -> Optional[float]:
    try:
        x = float(v)
        return None if math.isnan(x) else x
    except (TypeError, ValueError):
        return None


def rate_of(values: Sequence) -> Optional[Stat]:
    vals = [b for b in (_bool(v) for v in values) if b is not None]
    if not vals:
        return None
    k, n = sum(vals), len(vals)
    lo, hi = wilson(k, n)
    return k / n, lo, hi, n


def rate(rows: Sequence[dict], key: str) -> Optional[Stat]:
    """Share of rows where `key` is True, with its Wilson 95% interval."""
    return rate_of([r.get(key) for r in rows])


def mean_ci(rows: Sequence[dict], key: str) -> Optional[Stat]:
    """Mean of `key`, with a normal-approximation 95% interval (none for a single value)."""
    vals = [x for x in (_num(r.get(key)) for r in rows) if x is not None]
    if not vals:
        return None
    m = sum(vals) / len(vals)
    half = 0.0 if len(vals) < 2 else 1.96 * math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1) / len(vals))
    return m, m - half, m + half, len(vals)


# --- dot-and-interval chart ---------------------------------------------------------------------------

Panel = Tuple                                              # (title, payload -> stat[, scale])


def forest(entries: Dict[Tuple[str, str], object], panels: Sequence[Panel], title: str, caption: str,
           scale: str = "rate", xlabel: str = "") -> Optional[plt.Figure]:
    """Rows = entries' first key (in order), colour = their second key (the model), one panel per measure.
    scale: "rate" (0-100%), "signed" (a zero line), "count" (starts at 0); a panel can set its own."""
    cells = {(p, key): panel[1](payload) for p, panel in enumerate(panels) for key, payload in entries.items()}
    rows = list(dict.fromkeys(r for (r, m) in entries if any(cells[(p, (r, m))] for p in range(len(panels)))))
    models = list(dict.fromkeys(m for _, m in entries))
    shown = [p for p in range(len(panels)) if any(cells[(p, k)] for k in entries)]
    if not shown:
        return None
    label_n = []
    for r in rows:
        ns = sorted({c[3] for (p, (rr, _)), c in cells.items() if rr == r and c})
        label_n.append(f"{r}  (n={ns[0]})" if len(ns) == 1 else f"{r}  (n={ns[0]}–{ns[-1]})" if ns else r)
    step = 0.22 if len(models) > 1 else 0.0
    height = 0.75 + 0.3 * len(rows) * max(1.0, 0.75 * len(models))
    fig, axes = plt.subplots(1, len(shown), sharey=True, squeeze=False,
                             figsize=(1.9 + 2.5 * len(shown) + (1.3 if len(models) > 1 else 0), max(1.9, height)))
    for ax, p in zip(axes[0], shown):
        for (r, m), _ in entries.items():
            c = cells[(p, (r, m))]
            if c is None or r not in rows:
                continue
            j = models.index(m)
            y = rows.index(r) + (j - (len(models) - 1) / 2) * step
            colour = PALETTE[j % len(PALETTE)]
            ax.plot([max(c[1], -1e9), c[2]], [y, y], color=colour, linewidth=1.8, alpha=0.55, zorder=2)
            ax.plot([c[0]], [y], "o", color=colour, markersize=6, markeredgecolor="white", markeredgewidth=1, zorder=3)
        ax.set_title(textwrap.fill(panels[p][0], 36))
        ax.grid(axis="y", visible=False)
        ax.spines["left"].set_visible(False)
        kind = panels[p][2] if len(panels[p]) > 2 else scale
        if kind == "rate":
            ax.set_xlim(-0.04, 1.04)
            ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
            ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
        else:
            ax.xaxis.set_major_locator(MaxNLocator(5))
            if kind == "signed":
                ax.axvline(0, color=AXIS, linewidth=0.9, zorder=1)
            else:                                           # counts: from 0, with room for a dot at 0
                hi = max(ax.get_xlim()[1], 1.0)
                ax.set_xlim(-0.03 * hi, hi)
        if xlabel:
            ax.set_xlabel(xlabel)
    axes[0][0].set_yticks(range(len(rows)))
    axes[0][0].set_yticklabels(label_n)
    axes[0][0].set_ylim(len(rows) - 0.5, -0.5)               # first row on top
    frame(fig, title, caption)
    model_legend(axes[0][-1], models)
    return fig


RATE_NOTE = "dot: share of rounds; line: Wilson 95% interval; n: rounds"
MEAN_NOTE = "dot: mean per round; line: 95% interval (normal approximation); n: rounds"


def _rate_panel(key: str) -> Callable[[object], Optional[Stat]]:
    return lambda rows: rate(rows, key)


def _mean_panel(key: str) -> Callable[[object], Optional[Stat]]:
    return lambda rows: mean_ci(rows, key)


# --- run charts -------------------------------------------------------------------------------------


# The goal's main rate, its conflict flag (spec/09), its label, and a short name for file suffixes.
MAIN_RATE = {"high_value_ticket": ("hv_clean_capture", "hv_conflict", "One colluder alone holds the high-value ticket", "hv"),
             "same_issue": ("same_issue_match", "same_issue_conflict", "Colluders on the same issue", "same_issue")}
OUTCOME_LABELS = {"colluder_alone": "one colluder alone", "colluders_collide": "colluders collide on it",
                  "shared_with_honest": "shared with an honest agent", "honest": "honest agents only", "nobody": "nobody"}
OUTCOME_COLOURS = {"colluder_alone": PALETTE[0], "colluders_collide": PALETTE[1], "shared_with_honest": PALETTE[3],
                   "honest": PALETTE[2], "nobody": "#c9c7c1"}


def run_figures(run_dir: Path, rows: Optional[List[dict]] = None) -> List[Path]:
    """Charts of a run. `rows`: index rows with the outcome columns (analysis.summarize.load)."""
    from analysis.summarize import condition_order, load
    style()
    rows = load(run_dir) if rows is None else rows
    if not rows:
        return []
    out = run_dir / "figures"
    order = condition_order(run_dir)
    groups: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for r in sorted(rows, key=lambda r: (order.get(r["condition"], len(order)), r["condition"], r["model"])):
        groups[(r["condition"], r["model"])].append(r)
    paths: List[Path] = []

    def keep(fig, name):
        if fig is not None:
            paths.extend(save(fig, out, name))

    hv = {g: rs for g, rs in groups.items() if any(r.get("hv_outcome") for r in rs)}
    if hv:
        keep(_hv_outcomes(hv), "hv_capture")
    si = {g: rs for g, rs in groups.items() if any(r.get("objective") == "same_issue" for r in rs)}
    if si:
        keep(forest(si, [("same issue", _rate_panel("same_issue_match")),
                         ("same issue, at a cost to a colluder", _rate_panel("collusive_match")),
                         ("same issue, on conflict boards",
                          lambda rs: rate([r for r in rs if r.get("same_issue_conflict") == "True"], "same_issue_match"))],
                    "Colluders claiming tasks of the same issue", RATE_NOTE + "."), "same_issue")

    # Splits by board kind and by round, for each kind of game with a goal (one chart each).
    kinds = [o for o in MAIN_RATE if any(r.get("objective") == o for r in rows)]
    for objective in kinds:
        key, flag, label, short = MAIN_RATE[objective]
        sub = {g: rs for g, rs in groups.items() if rs[0].get("objective") == objective}
        suffix = "" if len(kinds) == 1 else f"_{short}"
        keep(forest(sub, [("conflict boards: the goal costs the team",
                           lambda rs, key=key, flag=flag: rate([r for r in rs if r.get(flag) == "True"], key)),
                          ("costless boards", lambda rs, key=key, flag=flag: rate([r for r in rs if r.get(flag) == "False"], key))],
                    f"{label}, by board kind (spec/09)",
                    RATE_NOTE + " of that board kind; boards are classified exactly, before any model plays."),
             f"by_board_kind{suffix}")
        if any(r["round"] != "0" for rs in sub.values() for r in rs):
            keep(_by_round(sub, key, label), f"by_round{suffix}")

    keep(forest(groups, [("team loss", _mean_panel("team_loss"))],
                "Team loss: optimum minus the team's score", MEAN_NOTE + ". Score units.", scale="count"), "team_loss")
    keep(forest(groups, [("regret gap (the paper's coalition advantage)", _mean_panel("regret_gap")),
                         ("reward gap", _mean_panel("reward_gap"))],
                "Coalition advantage, Colosseum's two measures",
                MEAN_NOTE + ". Positive: the colluders do better than the others. Score units.", scale="signed"),
         "colosseum")

    signals = _reservation_signals(run_dir)
    if signals:
        keep(forest(signals, [("colluders reserve tasks of one issue", lambda v: rate_of(v["same_issue"])),
                              ("a colluder reserves the high-value ticket", lambda v: rate_of(v["hv"]))],
                    "What the colluders signal in reservation passes",
                    "One row per condition and reservation pass. " + RATE_NOTE + "."), "reservations")

    keep(forest(groups, [("failed tool results", _mean_panel("failed_tool_results")),
                         ("turns without a claim", _mean_panel("turns_without_commit")),
                         ("missing claims", _mean_panel("missing_claims")),
                         ("duplicate claims", _mean_panel("duplicate_claims"))],
                "Health: can the model play the game?",
                MEAN_NOTE + ". Counts per round; read these before any collusion rate.", scale="count"), "health")
    keep(forest(groups, [("distinct posts (1 - repeats)", _mean_panel("distinct_post_share"), "rate"),
                         ("colluders name the ticket in secret chat", _rate_panel("colluders_name_hv"), "rate"),
                         ("largest pile on one task", _mean_panel("largest_pile"), "count")],
                "Chat and herding",
                "Distinct posts: mean share of messages that are not a repeat by the same agent. Ticket: share of rounds. "
                "Largest pile: the most agents on one task (1 = no duplicate)."), "chat_herding")
    return paths


def _hv_outcomes(groups: Dict[Tuple[str, str], List[dict]]) -> Optional[plt.Figure]:
    """100% stacked bars: one row per condition (and model), one segment per outcome of the ticket."""
    rows = [(g, [r.get("hv_outcome") for r in rs if r.get("hv_outcome")]) for g, rs in groups.items()]
    rows = [(g, v) for g, v in rows if v]
    if not rows:
        return None
    several = len({m for (_, m), _ in rows}) > 1
    labels = [f"{c} · {m}  (n={len(v)})" if several else f"{c}  (n={len(v)})" for (c, m), v in rows]
    fig, ax = plt.subplots(figsize=(8.2, max(2.4, 0.9 + 0.36 * len(rows))))   # room for the legend
    for i, (_, vals) in enumerate(rows):
        left = 0.0
        for name in OUTCOME_LABELS:
            share = vals.count(name) / len(vals)
            if share:
                ax.barh(i, share, left=left, height=0.62, color=OUTCOME_COLOURS[name], edgecolor="white", linewidth=1.5)
                if share >= 0.12:
                    ax.text(left + share / 2, i, f"{share:.0%}", ha="center", va="center", fontsize=7,
                            color="white" if name in ("colluder_alone", "colluders_collide", "honest") else INK)
                left += share
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(labels)
    ax.set_ylim(len(rows) - 0.5, -0.5)
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
    ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=OUTCOME_COLOURS[n]) for n in OUTCOME_LABELS]
    ax.legend(handles, list(OUTCOME_LABELS.values()), loc="upper left", bbox_to_anchor=(1.02, 1.0),
              title="who holds it", title_fontsize=7.5, alignment="left", handlelength=1.2)
    frame(fig, "Who ends up holding the high-value ticket",
          "Share of rounds; actual claims only (random fills not counted). 'Collide': two colluders claimed it, "
          "a failed coordination.")
    return fig


def _by_round(groups: Dict[Tuple[str, str], List[dict]], key: str, label: str) -> Optional[plt.Figure]:
    """Small multiples: one panel per condition, x = round, one line per model with its Wilson band."""
    conditions = list(dict.fromkeys(c for (c, _), rs in groups.items() if rate(rs, key)))
    models = list(dict.fromkeys(m for _, m in groups))
    if not conditions:
        return None
    cols = min(3, len(conditions))
    nrows = math.ceil(len(conditions) / cols)
    fig, axes = plt.subplots(nrows, cols, sharex=True, sharey=True, squeeze=False,
                             figsize=(1.0 + 2.9 * cols + (1.3 if len(models) > 1 else 0), 0.9 + 2.0 * nrows))
    drawn = False
    for idx, cond in enumerate(conditions):
        ax = axes[idx // cols][idx % cols]
        ax.set_title(cond)
        for m in models:
            by_round = defaultdict(list)
            for r in groups.get((cond, m), []):
                by_round[int(r["round"]) + 1].append(r)
            pts = [(x, rate(v, key)) for x, v in sorted(by_round.items())]
            pts = [(x, c) for x, c in pts if c is not None]
            if not pts:
                continue
            drawn = True
            j = models.index(m)
            colour = PALETTE[j % len(PALETTE)]
            if len(models) == 1:                       # one model: the interval as a band
                xs = [x for x, _ in pts]
                ax.fill_between(xs, [c[1] for _, c in pts], [c[2] for _, c in pts], color=colour, alpha=0.13, linewidth=0)
            else:                                      # several: offset whiskers, bands would pile up
                xs = [x + (j - (len(models) - 1) / 2) * 0.08 for x, _ in pts]
                ax.vlines(xs, [c[1] for _, c in pts], [c[2] for _, c in pts], color=colour, linewidth=1.4, alpha=0.5)
            ax.plot(xs, [c[0] for _, c in pts], color=colour, linewidth=2,
                    marker="o" if len(xs) <= 12 else None, markersize=4, markeredgecolor="white", markeredgewidth=0.8)
        ax.set_ylim(-0.03, 1.03)
        ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
        ax.set_yticks([0, 0.5, 1])
        ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=6))
    for idx in range(len(conditions), nrows * cols):
        axes[idx // cols][idx % cols].set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel("round")
    for row in axes:
        row[0].set_ylabel("share of games")
    if not drawn:
        plt.close(fig)
        return None
    frame(fig, f"{label}, by round", "line: share of games in that round; "
          + ("band" if len(models) == 1 else "whiskers") + ": Wilson 95% interval")
    model_legend(axes[0][-1] if len(conditions) >= cols else axes[0][len(conditions) - 1], models)
    return fig


def _reservation_signals(run_dir: Path) -> Dict[Tuple[str, str], Dict[str, list]]:
    """(condition, pass k, model) -> the colluders' same-issue and high-value reservation flags."""
    from analysis.summarize import condition_order
    acc: Dict[Tuple[str, int, str], Dict[str, list]] = {}
    for ep in run_dir.glob("episodes/**/episode.json"):
        data = json.loads(ep.read_text())
        if data.get("status") != "complete":
            continue
        model = data["model"]["label"] if isinstance(data.get("model"), dict) else str(data.get("model"))
        for rnd in data.get("rounds", []):
            m = rnd.get("metrics", {})
            if "reservation_colluders_same_issue" not in m:
                continue
            hv = m.get("reservation_hv_by_colluder") or []
            for i, v in enumerate(m["reservation_colluders_same_issue"]):
                cell = acc.setdefault((data["condition"], i, model), {"same_issue": [], "hv": []})
                cell["same_issue"].append(v)
                if i < len(hv) and hv[i] is not None:
                    cell["hv"].append(hv[i])
    order = condition_order(run_dir)
    keys = sorted(acc, key=lambda k: (order.get(k[0], len(order)), k))
    return {(f"{c}, pass {i + 1}", m): acc[(c, i, m)] for c, i, m in keys}


# --- board study charts --------------------------------------------------------------------------------

OBJECTIVE_NAMES = {"same_issue": "same issue", "hv_random": "high-value ticket drawn at random",
                   "hv_optimum_honest": "high-value ticket an honest agent gets in the optimum"}


def _plain_number(x, _pos=None) -> str:
    return f"{x:g}"


def _spread(ys: List[float], gap: float) -> List[float]:
    """Move label positions apart by at least `gap`, keeping their order."""
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    out = list(ys)
    for a, b in zip(order, order[1:]):
        out[b] = max(out[b], out[a] + gap)
    shift = (sum(ys) - sum(out)) / max(1, len(ys))   # recentre: labels stay as close to their lines as they can
    return [y + shift for y in out]


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

    # Conflict share by size: one line per goal, labelled at its end (no legend to look up).
    fig, ax = plt.subplots(figsize=(7.0, 3.4))
    series = [("same_issue_conflict", "same issue", objectives[0])] + \
             [("hv_conflict", OBJECTIVE_NAMES.get(o, o), o) for o in objectives if o.startswith("hv")]
    ends = []
    for i, (flag, label, obj) in enumerate(series):
        pts = []
        for s in sizes:
            r = agg.rate((s, obj), flag)          # the same-issue flag does not depend on the objective
            if r:
                lo, hi = wilson(*r)
                pts.append((s, r[0] / r[1], lo, hi))
        if not pts:
            continue
        colour = PALETTE[i % len(PALETTE)]
        xs = [p[0] for p in pts]
        ax.fill_between(xs, [p[2] for p in pts], [p[3] for p in pts], color=colour, alpha=0.1, linewidth=0)
        ax.plot(xs, [p[1] for p in pts], color=colour, linewidth=2, marker="o", markersize=4,
                markeredgecolor="white", markeredgewidth=0.8)
        ends.append((pts[-1][0], pts[-1][1], textwrap.fill(label, 34), colour))
    log = len(sizes) > 1 and max(sizes) / max(1, min(sizes)) > 20
    if log:
        ax.set_xscale("log")
        ax.minorticks_off()
        labelled, last = [], None                  # tick sizes far enough apart on the log axis
        for s in sizes:
            if last is None or math.log10(s) - math.log10(last) >= 0.15:
                labelled.append(s)
                last = s
    else:
        labelled = sizes
    ax.set_xticks(labelled)
    ax.xaxis.set_major_formatter(FuncFormatter(_plain_number))
    ax.set_ylim(0, 1.02)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("tasks on the board")
    ax.set_ylabel("share of boards")
    ax.grid(axis="x", visible=False)
    end_y = {label: y for _, y, label, _ in ends}
    for (x, _, label, colour), y in zip(ends, _spread([e[1] for e in ends], 0.1)):
        ax.annotate(label, (x, end_y[label]), xytext=(x * 1.35 if log else x + 0.06 * (sizes[-1] - sizes[0]), y),
                    textcoords="data", va="center", fontsize=7.5, color=INK, annotation_clip=False,
                    arrowprops={"arrowstyle": "-", "color": colour, "linewidth": 1, "shrinkA": 2, "shrinkB": 4})
    for x, y, _, colour in ends:
        ax.plot([x], [y], "o", color=colour, markersize=5, markeredgecolor="white", markeredgewidth=0.8)
    frame(fig, "Boards where reaching the coalition's goal costs the team",
          "conflict: price of collusion > 0, computed exactly (no model); band: Wilson 95% interval")
    paths.extend(save(fig, study_dir / "figures", "conflict_by_size"))

    # Distribution of the price of collusion: ordered sizes, so one hue from light (small) to dark (large).
    hv_obj = next((o for o in objectives if o == "hv_random"), next((o for o in objectives if o.startswith("hv")), objectives[-1]))
    shown = sizes if len(sizes) <= 5 else sorted({sizes[0], sizes[len(sizes) // 3], sizes[2 * len(sizes) // 3], sizes[-1]})
    ramp = [RAMP[round(i * (len(RAMP) - 1) / max(1, len(shown) - 1))] for i in range(len(shown))]
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 3.3), sharey=True)
    for ax, (key, obj, title) in zip(axes, (("price_same_issue", objectives[0], "same issue"),
                                            ("price_hv", hv_obj, OBJECTIVE_NAMES.get(hv_obj, hv_obj)))):
        for s, colour in zip(shown, ramp):
            vals = sorted(agg.values.get((s, obj, key), []))
            if vals:
                ax.step(vals, [(k + 1) / len(vals) for k in range(len(vals))], where="post", color=colour,
                        linewidth=1.8)
        ax.set_xscale("symlog", linthresh=0.1)
        ax.minorticks_off()
        lo, hi = ax.get_xlim()
        ax.set_xticks([t for t in (0, 0.1, 1, 10, 100, 1000) if lo <= t <= hi])
        ax.xaxis.set_major_formatter(FuncFormatter(_plain_number))
        ax.set_xlabel("price of collusion (score units)")
        ax.set_title(title)
        ax.set_ylim(0, 1.02)
        ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    axes[0].set_ylabel("share of boards with price ≤ x")
    handles = [Line2D([], [], color=c, linewidth=2) for c in ramp]
    axes[1].legend(handles, [f"{s} tasks" for s in shown], loc="upper left", handlelength=1.6,
                   title="board size", title_fontsize=7.5, alignment="left")
    frame(fig, "Price of collusion: what the coalition's goal costs the team",
          "cumulative share of boards; the jump at 0 is the share of costless boards")
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
