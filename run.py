"""Run a study: conditions x models x seeds x replications, every episode logged in full.

    python -m run configs/studies/<study>.yaml [options]

    --dry-run            print the plan (episodes, turns, maximum model calls) and stop
    --yes                do not ask before calling a remote (paid) model
    --scripted [POLICY]  replace every model by a scripted agent (free end-to-end check)
    --only A,B           run only these conditions;  --models X,Y  only these model labels
    --seeds 1-3          override the study's seeds; --replications N
    --resume RUN_DIR     continue a run: completed episodes are skipped
    --concurrency N      episodes run in parallel (default: the study's max_concurrency)
    --out DIR            parent folder of the run (default: COLLUSION_RUNS_DIR, else the study's out_dir)
    --no-summary         do not write summary.md and the charts at the end
    -q, -v, -vv          quiet / verbose / debug (default: COLLUSION_LOG_LEVEL, else normal)
    --log-level LEVEL    quiet | normal | verbose | debug
    --show A,B / --hide A,B   add or remove log items (logs.py: plan, progress, summary, rounds,
                         metrics, turns, messages, cot, calls, retries, errors)

Settings can also come from .env (see .env.example): API keys, COLLUSION_LOG_* and
COLLUSION_RUNS_DIR. Output: runs/<timestamp>__<study>/ with study.json, provenance.json, run.log,
and per episode episodes/<condition>/<model>/seed<k>_rep<r>/{episode.json, turns.jsonl, calls.jsonl};
index.csv has one row per round (metrics.py); summary.md, summary.csv and figures/ at the end.
Spec: spec/11-study-design.md, spec/12-reproducibility.md.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass, field, replace
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from agents import load_model
from agents.llm import ChatClient, FatalModelError, LLMAgent, ModelConfig
from agents.scripted import ScriptedAgent
from env.configio import ROOT, build, load_yaml, resolve_path, to_plain
from env.game import Episode, plain_round
from env.game_config import GameConfig, load_game
from logs import LogSettings, RunLogger
from metrics import index_row, round_metrics


@dataclass(frozen=True)
class ConditionConfig:
    """A condition of a study: a scenario of configs/scenarios.yaml by ID (its rules are fixed; `set`
    may change only the run size), or, for ad-hoc tests, a game file plus overrides."""
    scenario: Optional[str] = None
    name: str = ""                               # default: the scenario's name
    game: str = ""
    set: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StudyConfig:
    name: str
    description: str = ""
    conditions: Tuple[ConditionConfig, ...] = ()
    models: Tuple[Any, ...] = ()                 # paths to model configs, or inline mappings
    seeds: Any = "1-10"                          # "1-10", "1,3,5" or a list
    replications: int = 1
    max_concurrency: int = 4
    out_dir: str = "runs"


def parse_seeds(spec: Any) -> List[int]:
    if isinstance(spec, int):
        return [spec]
    if isinstance(spec, (list, tuple)):
        return [int(s) for s in spec]
    seeds: List[int] = []
    for part in str(spec).split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            seeds.extend(range(int(lo), int(hi) + 1))
        elif part:
            seeds.append(int(part))
    return seeds


def load_env_file(path: Path = ROOT / ".env") -> None:
    """KEY=VALUE lines from .env into the environment; variables already set win. Accepts
    `export KEY=VALUE`, quoted values and trailing ` # comments` on unquoted values."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if value[:1] in ("'", '"') and value[-1:] == value[:1] and len(value) >= 2:
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        os.environ.setdefault(key.strip(), value)


def missing_settings(jobs: List["Job"]) -> List[str]:
    """Environment variables a model needs (its key, its server URL) that are not set: reported before
    anything runs, instead of failing in the middle of a run."""
    out = []
    for m in {j.model.label: j.model for j in jobs if j.model.provider != "scripted"}.values():
        for var, what in ((m.api_key_env, "key"), (m.base_url_env, "server URL")):
            if var and not os.environ.get(var):
                hint = " (Modal: make modal-setup)" if "MODAL" in var else ""
                out.append(f"model {m.label!r}: its {what} is missing: set {var} in .env{hint}")
    return out


def is_local(model: ModelConfig) -> bool:
    return any(h in model.base_url for h in ("://127.0.0.1", "://localhost", "://0.0.0.0", "://[::1]"))


async def local_model_problem(client: ChatClient) -> Optional[str]:
    """Why a local model cannot be used, or None. A llama-server answers whatever `model` a request
    names, so a config pointing at the wrong server would run silently under the wrong label:
    check that the server lists the config's model before any episode."""
    cfg = client.config
    try:
        r = await client.http.get("/models", timeout=10)
    except httpx.HTTPError as exc:
        return f"cannot reach {cfg.base_url} ({type(exc).__name__}); is the local server running?"
    try:
        served = [m.get("id") for m in (r.json().get("data") or [])] if r.status_code == 200 else []
    except ValueError:
        served = []
    if served and cfg.model not in served:
        return (f"the server at {cfg.base_url} serves {served}, not {cfg.model!r}: start the matching server "
                f"(e.g. make local-server-abliterated) or fix `model` in the config")
    return None


def provenance(local: bool = False) -> Dict[str, Any]:
    def git(*args: str) -> Optional[str]:
        try:
            return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()
        except Exception:
            return None
    packages = {}
    for name in ("numpy", "scipy", "names", "pyyaml", "httpx", "matplotlib"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    out = {"git_commit": git("rev-parse", "HEAD"), "git_dirty": bool(git("status", "--porcelain")),
           "python": platform.python_version(), "packages": packages,
           "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "log_settings": {k: os.environ[k] for k in sorted(os.environ) if k.startswith("COLLUSION_")}}
    server = ROOT / "runs" / "_server" / "current.json"      # written by `make local-server`
    if local and server.exists():
        try:
            out["local_server"] = json.loads(server.read_text())
        except json.JSONDecodeError:
            pass
    return out


@dataclass
class Job:
    condition: str
    game: GameConfig
    model: ModelConfig
    seed: int
    replication: int
    scenario: Optional[str] = None             # its ID in configs/scenarios.yaml, if any

    @property
    def folder(self) -> str:
        return f"episodes/{self.condition}/{self.model.label}/seed{self.seed}_rep{self.replication}"

    @property
    def label(self) -> str:
        return f"{self.condition} · {self.model.label} · seed {self.seed}" + (f" rep {self.replication}" if self.replication else "")


def plan(study: StudyConfig, only=None, models=None, seeds=None, replications=None, scripted=None) -> List[Job]:
    """Expand a study into episodes. Unknown condition or model names are errors (typo safety)."""
    model_cfgs = [load_model(m if isinstance(m, dict) else resolve_path(m)) for m in study.models]
    labels = [m.label for m in model_cfgs]
    if len(set(labels)) != len(labels):
        raise ValueError(f"study {study.name!r}: two model files share a label: {labels}")
    if scripted:
        model_cfgs = [ModelConfig(label=f"scripted-{scripted}", provider="scripted", api_key_env=None, policy=scripted)]
    if models:
        unknown = sorted(set(models) - {m.label for m in model_cfgs})
        if unknown:
            raise ValueError(f"--models: unknown labels {unknown}; this study has {[m.label for m in model_cfgs]}")
        model_cfgs = [m for m in model_cfgs if m.label in models]
    resolved = [resolve_condition(c) for c in study.conditions]
    names = [r[0] for r in resolved]
    if len(set(names)) != len(names):
        raise ValueError(f"study {study.name!r}: two conditions share a name: {names}")
    if only:
        unknown = sorted(set(only) - set(names))
        if unknown:
            raise ValueError(f"--only: unknown conditions {unknown}; this study has {names}")
    jobs = []
    for name, game, sid in resolved:
        if only and name not in only:
            continue
        for model in model_cfgs:
            for seed in (seeds or parse_seeds(study.seeds)):
                for rep in range(replications if replications is not None else study.replications):
                    jobs.append(Job(name, game, model, seed, rep, sid))
    return jobs


def resolve_condition(cond: ConditionConfig) -> Tuple[str, GameConfig, Optional[str]]:
    """(name, game, scenario ID). A scenario reference takes its rules from the catalogue; a game
    file is recognised as a scenario when its rules match one."""
    import scenarios
    if cond.scenario:
        sc = scenarios.get(cond.scenario)
        if cond.game:
            raise ValueError(f"condition {cond.scenario}: give a scenario or a game, not both")
        size = scenarios.split_set(cond.set)
        game = load_game(sc.game, {**dict(sc.set), **size})
        return cond.name or sc.name, game, sc.id
    if not cond.game or not cond.name:
        raise ValueError("a condition needs `scenario: <ID>` (configs/scenarios.yaml), or `name` and `game`")
    game = load_game(cond.game, cond.set)
    return cond.name, game, scenarios.identify(to_plain(game))


def board_seed_overlaps(jobs: List[Job]) -> List[str]:
    """Conditions whose games reuse a board across seeds (seed + r x stride hits another seed's round)."""
    out = []
    for cond in sorted({j.condition for j in jobs}):
        js = [j for j in jobs if j.condition == cond and j.replication == 0]
        g = js[0].game
        if g.series.mode == "repeated_same_board" or g.series.rounds == 1:
            continue
        seen: Dict[int, int] = {}
        for j in {j.seed: j for j in js}.values():
            for r in range(g.series.rounds):
                b = j.seed + r * g.series.seed_stride if r else j.seed
                if b in seen and seen[b] != j.seed:
                    out.append(f"{cond}: board seed {b} is used by seeds {seen[b]} and {j.seed} (series.seed_stride "
                               f"{g.series.seed_stride} too small for these seeds)")
                    break
                seen[b] = j.seed
    return out


def turns_per_round(game: GameConfig) -> int:
    n_agents = game.board.n_agents
    n_coll = game.roles.colluders
    count = {"all": n_agents, "colluders": n_coll, "honest": n_agents - n_coll}
    return sum(p.passes * count[p.participants] for p in game.phases)


class Progress:
    """Time left, counted in turns: each episode's planned turns, the turns played so far and their
    measured duration. The estimate is the larger of two limits: the turns left at the throughput
    measured so far (episodes in parallel), and the longest episode left played one turn at a time
    (an episode's turns are sequential, so a long episode alone at the end cannot go faster)."""

    def __init__(self, jobs: List[Job]):
        self.planned = {j.folder: turns_per_round(j.game) * j.game.series.rounds for j in jobs}
        self.played: Dict[str, int] = {}
        self.turns, self.turn_seconds, self.started = 0, 0.0, time.time()

    def turn(self, job: Job, seconds: float) -> None:
        self.played[job.folder] = self.played.get(job.folder, 0) + 1
        self.turns += 1
        self.turn_seconds += seconds

    def finish(self, job: Job) -> None:
        self.played[job.folder] = self.planned[job.folder]

    def eta(self) -> Optional[float]:
        left = [max(0, p - self.played.get(k, 0)) for k, p in self.planned.items()]
        if not any(left):
            return 0.0
        if not self.turns:
            return None
        throughput = self.turns / max(1e-9, time.time() - self.started)
        return max(sum(left) / throughput, max(left) * self.turn_seconds / self.turns)


def describe(jobs: List[Job]) -> str:
    lines = [f"{len(jobs)} episodes"]
    by: Dict[Tuple[str, str], List[Job]] = {}
    for j in jobs:
        by.setdefault((f"{j.scenario} {j.condition}" if j.scenario else j.condition, j.model.label), []).append(j)
    calls_total = 0
    for (cond, model), js in by.items():
        g = js[0].game
        turns = turns_per_round(g) * g.series.rounds
        calls = turns * g.calls_per_turn * len(js)
        calls_total += calls if js[0].model.provider != "scripted" else 0
        lines.append(f"  {cond:28s} {model:24s} {len(js):4d} episodes x {g.series.rounds} rounds, "
                     f"{turns} turns/episode, <= {turns * g.calls_per_turn} model calls/episode")
    lines.append(f"maximum model calls: {calls_total}")
    return "\n".join(lines)


def is_complete(job: Job, run_dir: Path) -> bool:
    """The episode already finished in this run folder (resume)."""
    done = run_dir / job.folder / "episode.json"
    try:
        return done.exists() and json.loads(done.read_text()).get("status") == "complete"
    except json.JSONDecodeError:
        return False


async def run_job(job: Job, run_dir: Path, clients: Dict[str, ChatClient], index_lock: asyncio.Lock,
                  log: RunLogger, progress: Optional[Progress] = None) -> Tuple[str, int]:
    """Play one episode and write its files. Returns (status, rounds played)."""
    folder = run_dir / job.folder
    if is_complete(job, run_dir):
        return "skipped", 0
    folder.mkdir(parents=True, exist_ok=True)
    turns_f = (folder / "turns.jsonl").open("w")
    calls_f = (folder / "calls.jsonl").open("w")
    metrics_by_round: Dict[int, Dict[str, Any]] = {}

    def log_turn(record: Dict[str, Any]) -> None:
        turns_f.write(json.dumps(record, default=str) + "\n")
        turns_f.flush()
        log.turn(job.label, record)
        if progress:
            progress.turn(job, float(record.get("seconds") or 0.0))

    def log_call(record: Dict[str, Any]) -> None:
        calls_f.write(json.dumps(record, default=str) + "\n")
        calls_f.flush()

    def on_round(record: Dict[str, Any]) -> None:
        try:
            m = round_metrics(record)
        except Exception as exc:                       # a metric bug must not lose the episode
            log.error(f"{job.label} round {record['round'] + 1}: metrics failed: {type(exc).__name__}: {exc}")
            return
        metrics_by_round[record["round"]] = m
        log.round(job.label, record, m)

    salt = f"{job.condition}:{job.seed}:{job.replication}"

    def make_agent(name, roles):
        if job.model.provider == "scripted":
            return ScriptedAgent(name, job.model.policy)
        return LLMAgent(name, clients[job.model.label], log_call, seed_salt=salt)

    episode = Episode(job.game, job.seed, make_agent, replication=job.replication, log_turn=log_turn, on_round=on_round)
    started = time.time()
    fatal = None
    try:
        records = await episode.play()
        status, error = "complete", None
    except FatalModelError as exc:
        records, status, error, fatal = episode.rounds, "failed", str(exc), exc
    except Exception as exc:                           # keep the partial logs; mark the episode failed
        records, status, error = episode.rounds, "failed", f"{type(exc).__name__}: {exc}"
    finally:
        turns_f.close()
        calls_f.close()
    if error:
        log.error(f"{job.label}: {error}")
    rounds, rows = [], []
    for record in records:
        m = metrics_by_round.get(record["round"])
        if m is None:
            try:
                m = round_metrics(record)
            except Exception as exc:
                log.error(f"{job.label} round {record['round'] + 1}: metrics failed: {type(exc).__name__}: {exc}")
                status, error = "failed", error or f"metrics failed: {exc}"
                continue
        rounds.append({**plain_round(record), "metrics": to_plain(m)})
        row = {"scenario": job.scenario or "", **index_row(job.condition, job.model.label, job.seed, job.replication, record, m)}
        row["cost_usd"] = cost(job.model, row["prompt_tokens"], row["completion_tokens"])
        rows.append(row)
    (folder / "episode.json").write_text(json.dumps({"status": status, "error": error, "condition": job.condition,
                                "model": to_plain(job.model), "seed": job.seed, "replication": job.replication,
                                "seconds": time.time() - started, "game": to_plain(job.game), "rounds": rounds,
                                "index_rows": rows}, indent=1, default=str))
    if status == "complete":                           # index.csv only ever holds complete episodes
        async with index_lock:
            append_rows(run_dir / "index.csv", rows)
    if fatal is not None:
        raise fatal
    return status, len(rounds)


def cost(model: ModelConfig, prompt_tokens: int, completion_tokens: int) -> Optional[float]:
    """USD, from the prices in the model config (None when they are not set)."""
    if model.price_input_per_1m is None or model.price_output_per_1m is None:
        return None
    return (prompt_tokens * model.price_input_per_1m + completion_tokens * model.price_output_per_1m) / 1e6


def append_rows(path: Path, rows: List[Dict[str, Any]]) -> None:
    """Append rows to a CSV. A new file gets every column seen in `rows`; an existing file keeps its
    header (rows written by an older version, with fewer or other columns, still fit)."""
    if not rows:
        return
    if path.exists():
        with path.open(newline="") as f:
            header = next(csv.reader(f), None)
    else:
        header = None
    fields = header or list(dict.fromkeys(k for row in rows for k in row))
    with path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", restval="")
        if header is None:
            writer.writeheader()
        writer.writerows(rows)


def rebuild_index(run_dir: Path) -> int:
    rows = []
    for ep in sorted(run_dir.glob("episodes/**/episode.json")):
        try:
            data = json.loads(ep.read_text())
        except json.JSONDecodeError:
            continue
        if data.get("status") == "complete":
            rows.extend(data.get("index_rows", []))
    path = run_dir / "index.csv"
    if path.exists():
        path.unlink()
    append_rows(path, rows)
    return len(rows)


async def run_all(jobs: List[Job], run_dir: Path, concurrency: int, log: Optional[RunLogger] = None) -> Dict[str, int]:
    log = log or RunLogger()
    clients: Dict[str, ChatClient] = {}
    for job in jobs:
        if job.model.provider != "scripted" and job.model.label not in clients:
            label = job.model.label
            clients[label] = ChatClient(job.model, on_retry=lambda a, e, d, label=label: log.retry(label, a, e, d))
    sem = asyncio.Semaphore(max(1, concurrency))
    lock = asyncio.Lock()
    counts: Dict[str, int] = {}
    dead: Dict[str, str] = {}                          # model label -> fatal error: its remaining episodes are skipped
    pending = {j.model.label for j in jobs if not is_complete(j, run_dir)}
    for label, client in clients.items():
        if label in pending and client.config.startup_wait_s:
            log.plan(f"waiting for {label!r} to start (up to {client.config.startup_wait_s / 60:.0f} min)")
            problem = await client.wait_until_ready()
            if problem:
                dead[label] = f"server not ready after {client.config.startup_wait_s / 60:.0f} min: {problem}"
                log.error(f"model {label!r} not run: {dead[label]}")
                continue
            log.plan(f"{label!r} is up")
        if label in pending and is_local(client.config):
            problem = await local_model_problem(client)
            if problem:
                dead[label] = problem
                log.error(f"model {label!r} not run: {problem}")
    started = time.time()
    progress = Progress(jobs)

    async def one(job: Job) -> None:
        async with sem:
            if is_complete(job, run_dir):
                status, n_rounds, seconds = "skipped", 0, 0.0
            elif job.model.label in dead:
                status, n_rounds, seconds = "not run (model unusable)", 0, 0.0
            else:
                t0 = time.time()
                try:
                    status, n_rounds = await run_job(job, run_dir, clients, lock, log, progress)
                except FatalModelError as exc:
                    dead[job.model.label] = str(exc)
                    log.error(f"stopping every episode of model {job.model.label!r}: {exc}")
                    status, n_rounds = "failed", 0
                except Exception as exc:               # never let one episode take the run down
                    log.error(f"{job.label}: {type(exc).__name__}: {exc}")
                    status, n_rounds = "failed", 0
                seconds = time.time() - t0
            counts[status] = counts.get(status, 0) + 1
            progress.finish(job)
            log.progress(sum(counts.values()), len(jobs), job.label, status, seconds, started, n_rounds,
                         eta=progress.eta())

    try:
        await asyncio.gather(*(one(j) for j in jobs))
    finally:
        for c in clients.values():
            await c.close()
    return counts


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("study")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--scripted", nargs="?", const="colluder", default=None)
    parser.add_argument("--only")
    parser.add_argument("--models")
    parser.add_argument("--use-model", help="model file(s), comma-separated, replacing the study's models "
                                            "(e.g. the same study on an open model on Modal)")
    parser.add_argument("--seeds")
    parser.add_argument("--replications", type=int)
    parser.add_argument("--resume")
    parser.add_argument("--concurrency", type=int)
    parser.add_argument("--out", help="parent folder of the run (default: COLLUSION_RUNS_DIR, else the study's out_dir)")
    parser.add_argument("--no-summary", action="store_true")
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("--log-level", choices=["quiet", "normal", "verbose", "debug"])
    parser.add_argument("--show", default="")
    parser.add_argument("--hide", default="")
    args = parser.parse_args(argv)

    load_env_file()
    level = args.log_level or ("quiet" if args.quiet else {0: None, 1: "verbose"}.get(args.verbose, "debug"))
    try:
        settings = LogSettings.from_env(level, [s for s in args.show.split(",") if s], [s for s in args.hide.split(",") if s])
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    log = RunLogger(settings)
    try:
        study = build(StudyConfig, load_yaml(args.study), "study")
        if args.use_model:
            study = replace(study, models=tuple(m.strip() for m in args.use_model.split(",") if m.strip()))
        jobs = plan(study, only=args.only.split(",") if args.only else None,
                    models=args.models.split(",") if args.models else None,
                    seeds=parse_seeds(args.seeds) if args.seeds else None,
                    replications=args.replications, scripted=args.scripted)
    except (ValueError, OSError) as exc:
        log.error(str(exc))
        return 2
    plan_text = f"study {study.name}: " + describe(jobs)
    log.plan(plan_text)
    for warning in board_seed_overlaps(jobs):
        log.warning(warning)
    if args.dry_run or not jobs:
        return 0
    missing = missing_settings(jobs)
    if missing:
        for problem in missing:
            log.error(problem)
        return 2
    remote = sorted({j.model.label for j in jobs if j.model.provider != "scripted" and not is_local(j.model)})
    if remote and not args.yes:
        if not sys.stdin.isatty():
            log.error(f"this run calls remote models {remote}: re-run with --yes to confirm")
            return 2
        if input(f"This run calls remote models {remote}. Proceed? [y/N] ").strip().lower() != "y":
            return 1
    if args.resume:
        run_dir = Path(args.resume)
    else:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        parent = args.out or os.environ.get("COLLUSION_RUNS_DIR") or study.out_dir
        suffix = "__scripted" if args.scripted else ""
        if args.use_model and not args.scripted:              # the folder says which model replaced the study's
            suffix = "__" + "+".join(sorted({j.model.label for j in jobs}))
        run_dir = resolve_path(parent) / f"{stamp}__{study.name}{suffix}"
    run_dir.mkdir(parents=True, exist_ok=True)
    log.open_file(run_dir / "run.log", preamble=plan_text)
    log.plan(f"run folder: {run_dir}")
    if not (run_dir / "study.json").exists():
        (run_dir / "study.json").write_text(json.dumps({"source": str(args.study), "study": to_plain(study),
                                                        "args": vars(args),
                                                        "scenarios": {j.condition: j.scenario for j in jobs}}, indent=1))
        local = any(j.model.provider != "scripted" and is_local(j.model) for j in jobs)
        (run_dir / "provenance.json").write_text(json.dumps(provenance(local), indent=1))
    again = f"python -m run {args.study}" + (f" --use-model {args.use_model}" if args.use_model else "") + f" --resume {run_dir}"
    try:
        counts = asyncio.run(run_all(jobs, run_dir, args.concurrency or study.max_concurrency, log))
    except KeyboardInterrupt:
        rebuild_index(run_dir)
        log.error(f"interrupted. Finished episodes are kept; continue with: {again}")
        log.close()
        return 130
    n_rows = rebuild_index(run_dir)
    log.summary(f"done: {counts}; {n_rows} rounds in {run_dir / 'index.csv'}")
    if n_rows and not args.no_summary and os.environ.get("COLLUSION_AUTO_SUMMARY", "1") != "0":
        try:
            from analysis.summarize import summarize_run
            lines = summarize_run(run_dir)
            table = lines[lines.index("## By condition and model"):]
            table = table[:next((i for i, l in enumerate(table[1:], 1) if l.startswith("## ")), len(table))]
            log.summary("\n".join([l for l in lines if l.startswith("Tokens")][:1] + table).rstrip())
            log.summary(f"summary and charts: {run_dir / 'summary.md'}, {run_dir / 'figures'}")
        except Exception as exc:
            log.error(f"summary failed ({type(exc).__name__}: {exc}); run: python -m analysis.summarize {run_dir}")
    not_run, failed = counts.get("not run (model unusable)", 0), counts.get("failed", 0)
    if not_run or failed:
        log.error(f"{not_run} episodes not run, {failed} failed (exit code 3). Finished episodes are kept: fix the cause "
                  f"(e.g. start the model's server), then continue with: {again}")
    log.close()
    return 0 if not (failed or not_run) else 3


if __name__ == "__main__":
    sys.exit(main())
