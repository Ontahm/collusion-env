# Commands and settings

`make help` prints the command list. Every `make` command first checks that uv is installed and
recent enough, and says how to fix it if not.

## Make commands

### Setup and checks

| Command | Does |
|---|---|
| `make install` (or `make setup`) | checks uv, installs the locked dependencies, the git hook, a private `.env` |
| `make test` | all tests (no model, no network) |
| `make smoke` | the whole pipeline with scripted agents, free (`configs/studies/smoke_scripted.yaml`, written to `runs/_smoke/`, not shared) |
| `make hooks` | installs the git hook that refuses commits containing secrets (done by `make install`) |
| `make check-secrets` | checks every tracked file for secrets |

### Models

| Command | Does |
|---|---|
| `make models` | downloads the local models (pinned revisions, 2.5 GB each) and checks their SHA-256 |
| `make local-server` | serves a local model on `http://127.0.0.1:8080`; Ctrl+C stops it. Variables: `MODEL_FILE=`, `ALIAS=`, `PORT=`, `CTX=` (default 12288) |
| `make local-server-abliterated` | serves the abliterated Qwen3-4B (name `qwen3-4b-ablit-q4km`) |
| `make check-model MODEL=configs/models/<file>.yaml` | checks that a model endpoint answers with a tool call (default: `local-qwen3-4b.yaml`) |
| `make modal-setup` | Modal, once per person (again: a new key): installs, logs in, creates the key, deploys, checks, stops |
| `make modal-run STUDY=...` | runs a study on Modal: deploys, runs, always stops the server. Variables: `MODAL_MODEL=` (default `configs/models/modal-vllm.yaml`), `CONC=` (default 16), `ARGS=` |

### Studies

| Command | Does |
|---|---|
| `make dry-run STUDY=...` | prints what a study would run (episodes, turns, maximum model calls); calls nothing |
| `make run STUDY=...` | runs a study. `LOG=quiet\|normal\|verbose\|debug`; asks before calling a remote model (`ARGS=--yes` skips) |
| `make board-study` | model-free board study (`BOARD_STUDY=`, default `configs/board_study.yaml`) |

`STUDY` defaults to `configs/studies/colosseum_paper.yaml`.

### Reading results and scenarios

| Command | Does |
|---|---|
| `make runs` | lists the runs. `SC=<ID>`: every run of one scenario, with its results. `ARGS='-v'`: details; `ARGS='--grep <text>'`: matching runs only |
| `make episode RUN=runs/<run>` | lists the episodes of a run |
| `make episode RUN=runs/<run> SC=<ID> SEED=<k>` | one episode as a story (`COND=<condition>` instead of `SC=`). `ARGS=`: `--cot`, `--full`, `--round N`, `--model <label>` |
| `make summarize RUN=runs/<run>` | recomputes a run's `summary.md`, `summary.csv` and `figures/` |
| `make scenarios` | prints the scenario catalogue and regenerates [scenarios.md](scenarios.md) |
| `make prompts SC=<ID>` | the exact prompts of a scenario on a sample board (`SEED=` for another board) |

### Without make

| Command | Does |
|---|---|
| `uv run python -m analysis.paper_figure runs/<run>` | a paper reproduction run next to the paper ([how-to](../how-to/run-on-openai.md#reproduce-the-paper)) |
| `uv run python -m analysis.actions_v04 runs/<run>` | the actions v0.4 measures, written to `actions_v04.md` |
| `.venv/bin/python scripts/verify_installed.py` | checks installed packages against PyPI ([SECURITY.md](../../SECURITY.md)) |

## Options of a run

Pass them with `ARGS='...'` (`make run`, `make dry-run`, `make modal-run`), or directly to
`uv run python -m run <study file> ...`.

| Option | Does |
|---|---|
| `--dry-run` | prints the plan and stops |
| `--yes` | does not ask before calling a remote (paid) model |
| `--use-model <file>[,<file>]` | plays the study with these model files instead of its own; the run folder is named after the model |
| `--only <a>,<b>` | only these conditions (their names, as `make dry-run` prints them) |
| `--models <label>,<label>` | only these model labels of the study |
| `--seeds 1-3` | other seeds than the study's |
| `--replications N` | another number of replications |
| `--resume runs/<folder>` | continues a run: finished episodes are skipped (give the same options again) |
| `--concurrency N` | episodes played at once (default: the study's `max_concurrency`) |
| `--scripted [policy]` | replaces every model by a scripted agent (free) |
| `--out <dir>` | parent folder of the run folder |
| `--no-summary` | does not write the summary and charts at the end |
| `-q`, `-v`, `-vv`, `--log-level <level>` | how much the run prints (below) |
| `--show <items>`, `--hide <items>` | add or remove single items of the level |

## What a run prints

| Level | Shows |
|---|---|
| `quiet` | errors only |
| `normal` (default) | the plan, one line per finished episode (time, time left), the summary table at the end |
| `verbose` | and one line per round (board kind, colluders, who got the ticket, team loss), API retries |
| `debug` | and every turn (agent, phase, tool calls and their results), posted messages, the model's reasoning and answers, each call's tokens and time, the round's measures |

Items, to add or remove at any level (`--show cot`, or `COLLUSION_LOG_SHOW=cot`): `plan`,
`progress`, `summary`, `rounds`, `metrics`, `turns`, `messages`, `cot`, `calls`, `retries`,
`errors`.

The same lines go to the run's `run.log`. Logging never changes what is recorded: `turns.jsonl` and
`calls.jsonl` always hold everything.

## Settings in `.env`

`make install` creates `.env` from `.env.example`. Variables already set in your shell win over
`.env`; the command line wins over both.

| Variable | Meaning |
|---|---|
| `OPENAI_API_KEY`, `TOGETHER_API_KEY` | API keys, only for the models you use |
| `MODAL_VLLM_API_KEY`, `MODAL_VLLM_BASE_URL` | your Modal server's key and URL (written by `make modal-setup`) |
| `COLLUSION_LOG_LEVEL` | `quiet`, `normal`, `verbose` or `debug` |
| `COLLUSION_LOG_SHOW`, `COLLUSION_LOG_HIDE` | items to add to or remove from the level, comma-separated |
| `COLLUSION_LOG_FILE_LEVEL` | the level of `run.log`, if different (for example `debug` on disk, `normal` on screen) |
| `COLLUSION_LOG_TEXT_CHARS` | maximum characters shown for a text (reasoning, messages); 0: no limit. Default 600 |
| `COLLUSION_LOG_COLOR` | `auto`, `always` or `never` |
| `COLLUSION_RUNS_DIR` | parent folder of run folders (default: `runs/`) |
| `COLLUSION_AUTO_SUMMARY` | `0`: no summary and charts at the end of a run. Default 1 |
