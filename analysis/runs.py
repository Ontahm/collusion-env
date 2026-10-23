"""List the runs in runs/: what each one played, with which model, how far it got.

    python -m analysis.runs                 # one line per run, oldest first (also: make runs)
    python -m analysis.runs -v              # + per run: description, models, conditions, episodes
    python -m analysis.runs --grep modal    # only runs whose study, model, condition or scenario matches
    python -m analysis.runs --scenario ACT-1   # every run that played scenario ACT-1, with its results
    python -m analysis.runs --md runs.md    # the same table as Markdown, e.g. to share

Everything is read from what a run writes (study.json, run.log, episodes/, index.csv); nothing is
recomputed. Board studies (runs/board_study/) are listed after the runs.

Columns: when (start), run (folder), study, model(s) and where they ran (local / modal / openai /
scripted / other host), conditions, seeds, episodes complete / planned, rounds played, time
(summed over sessions, resumes included), tokens in / out, state:
  finished            all planned episodes complete
  finished, k failed  some episodes failed (see run.log)
  finished, k not run some episodes were never played (a model that was not served, say)
  running             no end line yet, files changed in the last 5 minutes
  stopped             no end line, nothing changed for 5 minutes (interrupted: --resume continues it)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from env.configio import ROOT, resolve_path
from scenarios import run_scenarios

RECENT_S = 300
_STATUS = re.compile(rb'"status":\s*"([^"]+)"')


def _dur(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def _tokens(n: float) -> str:
    return f"{n / 1e6:.1f}M" if n >= 1e6 else (f"{n / 1e3:.0f}k" if n >= 1e3 else f"{n:.0f}")


def where(base_url: str, provider: str = "openai_compatible") -> str:
    """Where a model ran, from its URL."""
    if provider == "scripted":
        return "scripted"
    host = urlparse(base_url).hostname or ""
    if host in ("127.0.0.1", "localhost", "0.0.0.0", "::1"):
        return "local"
    if "modal" in host:
        return "modal"
    if host.endswith("openai.com"):
        return "openai"
    return host or "?"


def _models(study: Dict[str, Any], args: Dict[str, Any]) -> List[Dict[str, str]]:
    if args.get("scripted"):
        return [{"label": f"scripted-{args['scripted']}", "model": "", "where": "scripted"}]
    from agents import load_model
    out = []
    for m in study.get("models", []):
        try:
            cfg = load_model(m if isinstance(m, dict) else resolve_path(m))
            out.append({"label": cfg.label, "model": cfg.model, "where": where(cfg.base_url, cfg.provider)})
        except Exception:                                    # a model file moved or renamed since
            name = Path(str(m)).stem if not isinstance(m, dict) else str(m.get("label", "?"))
            out.append({"label": name, "model": "?", "where": "?"})
    if args.get("models"):
        keep = set(args["models"].split(","))
        out = [m for m in out if m["label"] in keep]
    return out


def _seeds(spec: Any) -> List[int]:
    from run import parse_seeds
    try:
        return parse_seeds(spec)
    except Exception:
        return []


def _sessions(log: Path, start: datetime) -> List[Dict[str, Any]]:
    """Sessions of run.log (a resume appends one): start and end times, end None when unfinished.
    Lines carry HH:MM:SS only: the date comes from the folder name, rolling over at midnight."""
    sessions: List[Dict[str, Any]] = []
    if not log.exists():
        return sessions
    day, last = start.date(), None
    for line in log.read_text(errors="replace").splitlines():
        m = re.match(r"^(\d\d):(\d\d):(\d\d) (.*)$", line)
        if not m:
            continue
        t = datetime.combine(day, datetime.min.time()).replace(hour=int(m[1]), minute=int(m[2]), second=int(m[3]))
        if last and t < last - timedelta(hours=1):
            day += timedelta(days=1)
            t += timedelta(days=1)
        last = t
        text = m[4]
        if text.startswith("study ") or not sessions:
            sessions.append({"start": t, "end": None, "last": t})
        sessions[-1]["last"] = t
        if text.startswith("done:"):
            sessions[-1]["end"] = t
    return sessions


def _newest_mtime(run_dir: Path) -> float:
    newest = 0.0
    for p in [run_dir / "run.log", *run_dir.glob("episodes/*/*/*/turns.jsonl")]:
        try:
            newest = max(newest, p.stat().st_mtime)
        except OSError:
            pass
    return newest


def describe_run(run_dir: Path) -> Optional[Dict[str, Any]]:
    try:
        meta = json.loads((run_dir / "study.json").read_text())
    except (OSError, ValueError):
        return None
    study, args = meta.get("study", {}), meta.get("args", {})
    try:
        start = datetime.strptime(run_dir.name[:15], "%Y%m%d-%H%M%S")
    except ValueError:
        start = datetime.fromtimestamp((run_dir / "study.json").stat().st_mtime)
    ids = run_scenarios(run_dir)
    conditions = [c.get("name") or c.get("scenario") for c in study.get("conditions", [])]
    if ids and not all(c in ids for c in conditions):        # names defaulted from the scenario
        conditions = list(ids)
    if args.get("only"):
        conditions = [c for c in conditions if c in args["only"].split(",")]
    models = _models(study, args)
    seeds = _seeds(args.get("seeds") or study.get("seeds"))
    reps = args.get("replications") or study.get("replications", 1)
    planned = len(conditions) * len(models) * len(seeds) * reps

    statuses: Counter = Counter()
    per_cell: Counter = Counter()
    for ep in run_dir.glob("episodes/*/*/*/episode.json"):
        try:
            with ep.open("rb") as f:
                m = _STATUS.search(f.read(300))
        except OSError:
            m = None
        status = m.group(1).decode() if m else "unreadable"
        statuses[status] += 1
        if status == "complete":
            per_cell[(ep.parts[-4], ep.parts[-3])] += 1

    rounds, tok_in, tok_out, cost = 0, 0.0, 0.0, 0.0
    if (run_dir / "index.csv").exists():
        with (run_dir / "index.csv").open() as f:
            for r in csv.DictReader(f):
                rounds += 1
                tok_in += float(r.get("prompt_tokens") or 0)
                tok_out += float(r.get("completion_tokens") or 0)
                cost += float(r.get("cost_usd") or 0)

    sessions = _sessions(run_dir / "run.log", start)
    seconds = sum(((s["end"] or s["last"]) - s["start"]).total_seconds() for s in sessions)
    complete, failed = statuses.get("complete", 0), statuses.get("failed", 0)
    if (sessions and sessions[-1]["end"] is not None) or (planned and complete == planned):
        state = "finished"
        if failed:
            state += f", {failed} failed"
        missing = planned - complete - failed
        if missing > 0:
            state += f", {missing} not run"
    elif time.time() - _newest_mtime(run_dir) < RECENT_S:
        state = "running"
    else:
        state = "stopped" + (f", {failed} failed" if failed else "")

    return {"when": start.strftime("%Y-%m-%d %H:%M"), "run": run_dir.name, "path": str(run_dir),
            "study": study.get("name", "?"), "source": meta.get("source", ""), "description": study.get("description", ""),
            "models": models, "conditions": conditions, "seeds": seeds, "replications": reps,
            "planned": planned, "complete": complete, "failed": failed, "rounds": rounds,
            "seconds": seconds, "tokens_in": tok_in, "tokens_out": tok_out, "cost": cost, "state": state,
            "per_cell": per_cell, "use_model": args.get("use_model"), "summary": (run_dir / "summary.md").exists(),
            "ids": {c: ids.get(c) for c in conditions},
            "git": _git(run_dir)}


def _git(run_dir: Path) -> str:
    try:
        p = json.loads((run_dir / "provenance.json").read_text())
        return (p.get("git_commit") or "?")[:7] + (" (uncommitted changes)" if p.get("git_dirty") else "")
    except (OSError, ValueError):
        return "?"


def _seed_text(seeds: List[int]) -> str:
    if not seeds:
        return "?"
    if seeds == list(range(seeds[0], seeds[-1] + 1)) and len(seeds) > 2:
        return f"{seeds[0]}-{seeds[-1]}"
    return ",".join(map(str, seeds))


def row(d: Dict[str, Any]) -> List[str]:
    """Terminal row: the run folder already says when and which study."""
    models = ", ".join(f"{m['label']} ({m['where']})" for m in d["models"]) or "?"
    conds = f"{len(d['conditions'])}: " + " ".join(d["ids"].get(c) or c for c in d["conditions"])
    return [d["run"], models, conds, _seed_text(d["seeds"]), f"{d['complete']}/{d['planned']}", str(d["rounds"]),
            _dur(d["seconds"]), f"{_tokens(d['tokens_in'])}/{_tokens(d['tokens_out'])}", d["state"]]


HEAD = ["run", "model (where)", "conditions", "seeds", "episodes", "rounds", "time", "tokens in/out", "state"]
MD_HEAD = ["when", "study"] + HEAD


def board_studies(runs_dir: Path) -> List[List[str]]:
    out = []
    for d in sorted((runs_dir / "board_study").glob("*")):
        s = d / "summary.md"
        if not s.exists():
            out.append([d.name, "?", "?", "no summary (interrupted?)"])
            continue
        text = s.read_text()
        config = re.search(r"^# Board study — (.+)$", text, re.M)
        seeds = re.search(r"^Seeds ([^ ]+) \((\d+) boards per size and objective\)(?:, (\d+) boards)?", text, re.M)
        sizes = sorted({int(m) for m in re.findall(r"^\| (\d+) \|", text, re.M)})
        out.append([d.name, config.group(1) if config else "?",
                    f"seeds {seeds.group(1)}" + (f", {seeds.group(3)} boards" if seeds and seeds.group(3) else "") if seeds else "?",
                    "sizes " + ",".join(map(str, sizes)) if sizes else "?"])
    return out


def _table(head: List[str], rows: List[List[str]], widths: Optional[Dict[int, int]] = None) -> List[str]:
    widths = widths or {}
    clipped = [[c if len(c) <= widths.get(i, 10**6) else c[:widths[i] - 1] + "…" for i, c in enumerate(r)] for r in rows]
    w = [max(len(h), *(len(r[i]) for r in clipped)) if clipped else len(h) for i, h in enumerate(head)]
    lines = ["  ".join(h.ljust(w[i]) for i, h in enumerate(head)), "  ".join("-" * x for x in w)]
    lines += ["  ".join(c.ljust(w[i]) for i, c in enumerate(r)) for r in clipped]
    return lines


def details(d: Dict[str, Any]) -> List[str]:
    lines = [f"  {d['path']}",
             f"  study file: {d['source']}" + (f"  (models replaced by --use-model {d['use_model']})" if d["use_model"] else ""),
             f"  {d['description']}" if d["description"] else "",
             f"  code: {d['git']}; summary: {'summary.md' if d['summary'] else 'none'}"
             + (f"; cost ${d['cost']:.2f}" if d["cost"] else "")]
    for m in d["models"]:
        lines.append(f"  model {m['label']}: {m['model']} ({m['where']})")
    per_cond = len(d["seeds"]) * d["replications"]
    for c in d["conditions"]:
        cells = ", ".join(f"{m['label']} {d['per_cell'].get((c, m['label']), 0)}/{per_cond}" for m in d["models"])
        shown = f"{d['ids'].get(c)} {c}" if d["ids"].get(c) else c
        lines.append(f"    {shown:36s} {cells}")
    return [l for l in lines if l]


def scenario_view(sid: str, runs: List[Dict[str, Any]], runs_dir: Path) -> int:
    """Every run that played one scenario, with the measures of its goal, side by side."""
    import scenarios
    from analysis.summarize import load, main_columns, summarize_rows
    try:
        sc = scenarios.get(sid)
    except ValueError as exc:
        print(exc)
        return 2
    print(f"{sc.id} {sc.name}: {sc.title}\n  tests: {sc.tests}\n")
    print(f"{len(runs)} runs in {runs_dir} played it")
    rows, head = [], None
    for d in runs:
        data = [r for r in load(Path(d["path"])) if r.get("scenario") == sid] if Path(d["path"], "index.csv").exists() else []
        by_model: Dict[str, List[Dict[str, str]]] = {}
        for r in data:
            by_model.setdefault(r["model"], []).append(r)
        for model, rs in by_model.items():
            objective = rs[0].get("objective") or "coalition_reward"
            cols = main_columns(objective)
            s = summarize_rows(rs)
            head = ["run", "condition", "model", "rounds"] + [c for c, _ in cols] + ["duplicates / round"]
            rows.append([d["run"], rs[0]["condition"], model, str(s["rounds"])] + [fn(s) for _, fn in cols]
                        + [f"{s.get('duplicate_claims', 0):.2f}"])
    if rows:
        print("\n".join(_table(head, rows)))
    print("\nOne game: make episode RUN=runs/<run> SC=" + sid + " SEED=<k>")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs-dir", default=os.environ.get("COLLUSION_RUNS_DIR") or str(ROOT / "runs"))
    parser.add_argument("-v", "--verbose", action="store_true", help="details per run")
    parser.add_argument("--grep", help="keep runs whose study, run folder, model or condition contains this text")
    parser.add_argument("--scenario", help="only runs that played this scenario (configs/scenarios.yaml), with its results")
    parser.add_argument("--md", help="also write the table as Markdown to this file")
    args = parser.parse_args(argv)
    runs_dir = Path(args.runs_dir)
    found = [describe_run(d) for d in sorted(runs_dir.iterdir()) if d.is_dir() and not d.name.startswith("_")
             and d.name != "board_study"] if runs_dir.exists() else []
    runs = [d for d in found if d]
    if args.grep:
        g = args.grep.lower()
        runs = [d for d in runs if g in " ".join([d["study"], d["run"], *d["conditions"], *(i or "" for i in d["ids"].values()),
                                                 *(m["label"] + " " + m["where"] for m in d["models"])]).lower()]
    if args.scenario:
        return scenario_view(args.scenario, [d for d in runs if args.scenario in d["ids"].values()], runs_dir)
    rows = [row(d) for d in runs]
    print(f"{len(runs)} runs in {runs_dir}")
    if args.verbose:
        for d, r in zip(runs, rows):
            print()
            print("  ".join(c for i, c in enumerate(r) if i != 2))
            print("\n".join(details(d)))
    else:
        print("\n".join(_table(HEAD, rows, widths={1: 40, 2: 40})))
    boards = board_studies(runs_dir) if not args.grep else []
    if boards:
        print(f"\nBoard studies ({runs_dir / 'board_study'}):")
        print("\n".join(_table(["folder", "config", "seeds", "sizes"], boards)))
    if args.md:
        md = ["| " + " | ".join(MD_HEAD) + " |", "|" + "---|" * len(MD_HEAD)]
        md += ["| " + " | ".join(c.replace("|", "/") for c in [d["when"], d["study"], *r]) + " |" for d, r in zip(runs, rows)]
        if boards:
            md += ["", "| board study | config | seeds | sizes |", "|---|---|---|---|"]
            md += ["| " + " | ".join(b) + " |" for b in boards]
        Path(args.md).write_text("\n".join(md) + "\n")
        print(f"\nwritten to {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
