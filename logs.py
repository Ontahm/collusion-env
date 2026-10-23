"""What a run prints, and how much: verbosity levels and items, set in .env or on the command line.

Levels (`COLLUSION_LOG_LEVEL`, or `-q`, `-v`, `-vv`, `--log-level`) choose a default set of items:

  quiet    errors
  normal   errors, plan, progress, summary                      (default)
  verbose  normal + rounds, retries
  debug    verbose + metrics, turns, messages, cot, calls

Items:
  plan      what will run: episodes, rounds, maximum model calls
  progress  one line per finished episode, with time and estimated time left
  summary   the summary table at the end of the run
  rounds    one line per finished round: board kind, colluders, claims of interest, team loss
  metrics   the round's main metrics, under its line
  turns     one line per turn: agent, phase, tool calls and their results, calls, time
  messages  the messages agents post on boards
  cot       the model's reasoning text and answer text, per call (truncated)
  calls     each model call: tokens and time
  retries   API retries and their reasons
  errors    model and episode errors (always on unless hidden)

`COLLUSION_LOG_SHOW=cot,metrics` adds items to the level's set, `COLLUSION_LOG_HIDE=progress`
removes some (command line: `--show`, `--hide`). The console and the run's `run.log` get the same
items, unless `COLLUSION_LOG_FILE_LEVEL` gives the file its own level (e.g. debug on disk, quiet
on screen). `COLLUSION_LOG_TEXT_CHARS` caps the length of texts (reasoning, messages; 0 = no cap),
`COLLUSION_LOG_COLOR` is auto | always | never.

Everything is also recorded in full in each episode's turns.jsonl and calls.jsonl, whatever the
verbosity: logging only changes what is shown.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, TextIO

ITEMS = ("plan", "progress", "summary", "rounds", "metrics", "turns", "messages", "cot", "calls", "retries", "errors")
LEVELS: Dict[str, Set[str]] = {
    "quiet": {"errors"},
    "normal": {"errors", "plan", "progress", "summary"},
}
LEVELS["verbose"] = LEVELS["normal"] | {"rounds", "retries"}
LEVELS["debug"] = LEVELS["verbose"] | {"metrics", "turns", "messages", "cot", "calls"}

_COLORS = {"error": "\033[31m", "warn": "\033[33m", "dim": "\033[2m", "bold": "\033[1m", "ok": "\033[32m", "end": "\033[0m"}


def _items(level: str, show: Iterable[str] = (), hide: Iterable[str] = ()) -> Set[str]:
    if level not in LEVELS:
        raise ValueError(f"log level {level!r}: expected one of {sorted(LEVELS)}")
    unknown = sorted((set(show) | set(hide)) - set(ITEMS))
    if unknown:
        raise ValueError(f"log items {unknown}: known items are {list(ITEMS)}")
    return (LEVELS[level] | set(show)) - set(hide)


def _split(value: Optional[str]) -> List[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


@dataclass
class LogSettings:
    level: str = "normal"
    show: Set[str] = field(default_factory=lambda: set(LEVELS["normal"]))
    file_show: Optional[Set[str]] = None          # None: same items as the console
    text_chars: int = 600
    color: str = "auto"

    @classmethod
    def from_env(cls, level: Optional[str] = None, show: Iterable[str] = (), hide: Iterable[str] = ()) -> "LogSettings":
        """Environment (.env) first, then the command line on top."""
        env = os.environ
        level = level or env.get("COLLUSION_LOG_LEVEL", "normal").strip().lower() or "normal"
        items = _items(level, _split(env.get("COLLUSION_LOG_SHOW")) + list(show),
                       _split(env.get("COLLUSION_LOG_HIDE")) + list(hide))
        file_level = env.get("COLLUSION_LOG_FILE_LEVEL", "").strip().lower()
        file_items = _items(file_level) if file_level else None
        return cls(level=level, show=items, file_show=file_items,
                   text_chars=int(env.get("COLLUSION_LOG_TEXT_CHARS", "600") or 0),
                   color=env.get("COLLUSION_LOG_COLOR", "auto").strip().lower() or "auto")


class RunLogger:
    """Thread- and task-safe printer of the items enabled in the settings, to the console and run.log."""

    def __init__(self, settings: Optional[LogSettings] = None, stream: Optional[TextIO] = None):
        self.s = settings or LogSettings()
        self.stream = stream or sys.stdout
        self.file: Optional[TextIO] = None
        self.lock = threading.Lock()
        tty = hasattr(self.stream, "isatty") and self.stream.isatty()
        self.color = self.s.color == "always" or (self.s.color == "auto" and tty and not os.environ.get("NO_COLOR"))

    # plumbing ----------------------------------------------------------------------------------
    def open_file(self, path: Path, preamble: str = "") -> None:
        """Start writing run.log; `preamble` (e.g. the plan, printed before the run folder existed)
        goes to the file only."""
        self.file = Path(path).open("a", encoding="utf-8")
        if preamble:
            with self.lock:
                self.file.write(time.strftime("%H:%M:%S ") + preamble + "\n")
                self.file.flush()

    def close(self) -> None:
        if self.file:
            self.file.close()
            self.file = None

    def on(self, item: str) -> bool:
        return item in self.s.show or (self.file is not None and item in (self.s.file_show or set()))

    def emit(self, item: str, text: str, style: Optional[str] = None) -> None:
        to_console = item in self.s.show
        to_file = self.file is not None and item in (self.s.file_show if self.s.file_show is not None else self.s.show)
        if not (to_console or to_file):
            return
        with self.lock:
            if to_console:
                shown = f"{_COLORS[style]}{text}{_COLORS['end']}" if (self.color and style) else text
                print(shown, file=self.stream, flush=True)
            if to_file:
                self.file.write(time.strftime("%H:%M:%S ") + text + "\n")
                self.file.flush()

    def clip(self, text: Any) -> str:
        text = " ".join(str(text or "").split())
        n = self.s.text_chars
        return text if not n or len(text) <= n else text[:n] + f"… [+{len(text) - n} chars]"

    # items --------------------------------------------------------------------------------------
    def error(self, text: str) -> None:
        self.emit("errors", f"ERROR {text}", "error")

    def warning(self, text: str) -> None:
        self.emit("errors", f"warning: {text}", "warn")

    def plan(self, text: str) -> None:
        self.emit("plan", text)

    def summary(self, text: str) -> None:
        self.emit("summary", text)

    def progress(self, done: int, total: int, label: str, status: str, seconds: float, started: float,
                 rounds: int = 0, eta: Optional[float] = None) -> None:
        """`eta`: time left from the runner (run.Progress, counted in turns); without it, the average
        episode time (wrong when episodes differ in length)."""
        elapsed = time.time() - started
        if eta is None:
            eta = elapsed / done * (total - done) if done else 0
        style = "ok" if status == "complete" else ("dim" if status == "skipped" else "error")
        self.emit("progress", f"[{done}/{total}] {label} · {status} · {rounds} rounds · {_dur(seconds)}"
                              f" · elapsed {_dur(elapsed)} · left ~{_dur(eta)}", style)

    def retry(self, label: str, attempt: int, error: str, delay: float) -> None:
        self.emit("retries", f"  retry {attempt} in {delay:.0f} s · {label} · {error[:200]}", "warn")

    def round(self, label: str, record: Dict[str, Any], m: Dict[str, Any]) -> None:
        if not (self.on("rounds") or self.on("metrics")):
            return
        b = m.get("board", {})
        kind = "conflict" if (b.get("hv_conflict") if m.get("hv_task") else b.get("same_issue_conflict")) else "costless"
        parts = [f"  {label} r{record['round'] + 1}", f"{kind} board", "colluders " + "+".join(record["colluders"])]
        if m.get("hv_task"):
            holders = m.get("hv_holders") or []
            who = ", ".join(f"{h} ({'colluder' if h in record['colluders'] else 'honest'})" for h in holders) or "nobody"
            parts.append(f"ticket {m['hv_task']} -> {who}")
        if m.get("objective") == "same_issue":
            parts.append(f"same issue {'yes' if m.get('same_issue_match') else 'no'}")
        parts.append(f"team loss {m['team_loss']:.2f}")
        h = m.get("health", {})
        if h.get("model_calls"):
            parts.append(f"{h['model_calls']} calls")
        if h.get("missing_claims"):
            parts.append(f"{h['missing_claims']} missing claims")
        self.emit("rounds", " · ".join(parts))
        self.emit("metrics", "    metrics: " + ", ".join(
            f"{k} {_fmt(m.get(k))}" for k in ("score", "optimum", "regret_gap", "reward_gap", "coalition_value",
                                               "same_issue_match", "collusive_match", "hv_captured_by_coalition")
            if m.get(k) is not None) + f", failed tool results {h.get('failed_tool_results', 0)}", "dim")

    def turn(self, label: str, record: Dict[str, Any]) -> None:
        if not any(self.on(i) for i in ("turns", "messages", "cot", "calls")):
            return
        calls = record.get("tool_calls") or []
        acts = []
        for c in calls:
            args = c.get("arguments") or {}
            what = args.get("task_id", "") if c["tool"] != "post_message" else f"board {args.get('blackboard_id', 0)}"
            result = c.get("result") or {}
            ok = "ok" if (isinstance(result, dict) and result.get("status") == "success") or "event_id" in result else \
                f"refused: {result.get('reason') or result.get('error') or result.get('status')}"
            acts.append(f"{c['tool']}({what}) {ok}")
        line = (f"    {label} r{record['round'] + 1} {record['phase']} · {record['agent']} ({record['role']}) · "
                + ("; ".join(acts) if acts else "no tool call")
                + f" · {record.get('model_calls', 0)} calls" + (f" · {record.get('seconds', 0):.1f} s" if record.get("seconds") else ""))
        self.emit("turns", line, None if record.get("committed") or record["kind"] == "chat" else "warn")
        if record.get("error"):
            self.error(f"{label} {record['agent']}: {record['error']}")
        for c in calls:
            if c["tool"] == "post_message" and "event_id" in (c.get("result") or {}):
                self.emit("messages", f"      {record['agent']} -> board {(c.get('arguments') or {}).get('blackboard_id', 0)}: "
                                      f"{self.clip((c.get('arguments') or {}).get('message'))}")
        for i, step in enumerate(record.get("steps") or [], start=1):
            if step.get("reasoning"):
                self.emit("cot", f"      [{record['agent']} call {i} thinking] {self.clip(step['reasoning'])}", "dim")
            if step.get("text"):
                self.emit("cot", f"      [{record['agent']} call {i} says] {self.clip(step['text'])}", "dim")
            self.emit("calls", f"      [{record['agent']} call {i}] {step.get('prompt_tokens', 0)} in / "
                               f"{step.get('completion_tokens', 0)} out tokens · {step.get('seconds', 0):.1f} s"
                               + (f" · {step['attempts']} attempts" if step.get("attempts", 1) > 1 else ""), "dim")


def _dur(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def _fmt(v: Any) -> str:
    return f"{v:.2f}" if isinstance(v, float) else str(v)
