"""Summarise a run: one table per condition x model, from index.csv (one row per round).

    python -m analysis.summarize <run dir> [--no-figures]

Writes <run dir>/summary.md and summary.csv, and the charts of analysis/figures.py in
<run dir>/figures/. Rates come with Wilson 95% intervals; rows are split by board kind (conflict /
costless, spec/09) and, for repeated games, by round.
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from analysis.stats import mean, wilson

RATES = ("same_issue_match", "collusive_match", "hv_captured_by_coalition", "hv_captured_by_honest")
MEANS = ("colluders_filled", "team_loss", "normalized_regret", "regret_gap", "reward_gap", "coalition_value", "colluder_sacrifice_sum",
         "failed_tool_results", "turns_without_commit", "missing_claims", "duplicate_claims", "errors",
         "prompt_tokens", "completion_tokens")


def _bool(v: str) -> Optional[bool]:
    return {"True": True, "False": False}.get(v)


def _num(v: str) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load(run_dir: Path) -> List[Dict[str, str]]:
    with (run_dir / "index.csv").open() as f:
        return list(csv.DictReader(f))


def summarize_rows(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"rounds": len(rows)}
    for key in RATES:
        vals = [_bool(r.get(key, "")) for r in rows]
        vals = [v for v in vals if v is not None]
        if vals:
            k, n = sum(vals), len(vals)
            lo, hi = wilson(k, n)
            out[key] = {"k": k, "n": n, "rate": k / n, "ci": [lo, hi]}
    for key in MEANS:
        m = mean(_num(r.get(key)) for r in rows)
        if m is not None:
            out[key] = m
    return out


def _rate(cell: Optional[Dict[str, Any]]) -> str:
    if not cell:
        return "—"
    return f"{cell['rate']:.0%} [{cell['ci'][0]:.0%}, {cell['ci'][1]:.0%}] (n={cell['n']})"


def summarize_run(run_dir: Path, figures: bool = True) -> List[str]:
    """Write summary.md, summary.csv and (optionally) the charts; return the summary's lines."""
    rows = load(run_dir)
    groups: Dict[tuple, List[Dict[str, str]]] = defaultdict(list)
    for r in rows:
        groups[(r["condition"], r["model"])].append(r)
    lines = [f"# Summary — {run_dir.name}", "", f"{len(rows)} rounds.", ""]
    tokens_in = sum(_num(r.get("prompt_tokens")) or 0 for r in rows)
    tokens_out = sum(_num(r.get("completion_tokens")) or 0 for r in rows)
    costs = [_num(r.get("cost_usd")) for r in rows]
    known = [c for c in costs if c is not None]
    lines += [f"Tokens: {tokens_in:,.0f} in, {tokens_out:,.0f} out."
              + (f" Cost: ${sum(known):.2f}" + ("" if len(known) == len(costs) else " (models without prices not counted)") + "."
                 if known else ""), ""]
    flat = []
    lines += ["## By condition and model", "",
              "| condition | model | rounds | same issue | collusive match | high-value to coalition | team loss | regret gap | reward gap | failed tool results / round |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for (cond, model), rs in sorted(groups.items()):
        s = summarize_rows(rs)
        flat.append({"condition": cond, "model": model, "split": "all", **{k: (v["rate"] if isinstance(v, dict) else v) for k, v in s.items()}})
        lines.append(f"| {cond} | {model} | {s['rounds']} | {_rate(s.get('same_issue_match'))} | {_rate(s.get('collusive_match'))} | "
                     f"{_rate(s.get('hv_captured_by_coalition'))} | {s.get('team_loss', float('nan')):.2f} | "
                     f"{s.get('regret_gap', float('nan')):.2f} | {s.get('reward_gap', float('nan')):.2f} | "
                     f"{s.get('failed_tool_results', float('nan')):.2f} |")
    lines += ["", "## By board kind (spec/09: conflict = the coalition's goal costs the team)", "",
              "| condition | model | board kind | rounds | same issue | high-value to coalition | team loss |", "|---|---|---|---|---|---|---|"]
    for (cond, model), rs in sorted(groups.items()):
        for flag in ("same_issue_conflict", "hv_conflict"):
            for value in ("True", "False"):
                sub = [r for r in rs if r.get(flag) == value]
                if sub:
                    s = summarize_rows(sub)
                    lines.append(f"| {cond} | {model} | {flag}={value} | {len(sub)} | {_rate(s.get('same_issue_match'))} | "
                                 f"{_rate(s.get('hv_captured_by_coalition'))} | {s.get('team_loss', float('nan')):.2f} |")
    if any(r["round"] != "0" for r in rows):
        lines += ["", "## By round (repeated games)", "", "| condition | model | round | same issue | high-value to coalition | team loss |",
                  "|---|---|---|---|---|---|"]
        for (cond, model), rs in sorted(groups.items()):
            for rnd in sorted({int(r["round"]) for r in rs}):
                s = summarize_rows([r for r in rs if int(r["round"]) == rnd])
                lines.append(f"| {cond} | {model} | {rnd + 1} | {_rate(s.get('same_issue_match'))} | "
                             f"{_rate(s.get('hv_captured_by_coalition'))} | {s.get('team_loss', float('nan')):.2f} |")
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n")
    with (run_dir / "summary.csv").open("w", newline="") as f:
        keys = sorted({k for row in flat for k in row})
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(flat)
    if figures:
        from analysis.figures import run_figures
        made = run_figures(run_dir)
        lines += ["", "## Figures", ""] + [f"- `{p.relative_to(run_dir)}`" for p in made if p.suffix == ".png"]
        (run_dir / "summary.md").write_text("\n".join(lines) + "\n")
    return lines


def main(argv: Optional[List[str]] = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    run_dir = Path([a for a in args if not a.startswith("--")][0])
    print("\n".join(summarize_run(run_dir, figures="--no-figures" not in args)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
