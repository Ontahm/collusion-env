# collusion-env

An environment to study collusion between LLM agents. Six agents split a sprint backlog. Two of
them secretly pursue a shared goal. Do they gain at the team's expense, and how: by open chat, by a
secret chat, or by their actions alone?

It rebuilds the Jira task-allocation game of Colosseum
([Nakamura et al., arXiv:2602.15198](https://arxiv.org/abs/2602.15198)) and is tested against
Colosseum's own code. It adds what the team's studies need: several rounds per episode,
reservation phases, a high-value ticket, games without chat, and boards where collusion must cost
the team. Every variant is a config file; every default is Colosseum's paper setting.

## Status (23 Oct 2026)

- The environment is tested against Colosseum's code: boards, scoring, prompts, colluder draws
  ([details](docs/explanation/fidelity.md)).
- Five studies are ready to run ([what each asks](docs/explanation/studies.md)).
- The runs of 23 Oct are in `runs/`. Anyone can read them, no model or key needed: `make runs`.
- Findings: to come.

## Quick start

You need macOS or Linux, `make` and [uv](https://docs.astral.sh/uv/) (uv installs Python). On Nix,
run `nix develop` first.

```bash
make install    # checks uv, installs the dependencies, the git hook and a private .env
make test       # all tests, no model, no network
make smoke      # a whole study with scripted agents: free, a few seconds
make runs       # the runs the team has made
```

[Getting started](docs/getting-started.md) walks through these steps and ends with a real episode,
read turn by turn.

## Run a study on a model

| Model | Cost | Guide |
|---|---|---|
| Qwen3-4B on your own GPU | free | [run locally](docs/how-to/run-locally.md) |
| open models (Qwen3-8B and others) on a rented GPU | Modal GPU time | [run on Modal](docs/how-to/run-on-modal.md) |
| gpt-4.1-mini (the paper's model), gpt-5-mini or another API | API tokens (the paper reproduction cost $3.72) | [run on OpenAI](docs/how-to/run-on-openai.md) |

```bash
make dry-run STUDY=configs/studies/colosseum_paper.yaml    # what would run; nothing is called
make run     STUDY=configs/studies/colosseum_paper.yaml    # asks before calling a paid model
```

## Documentation

All pages are listed in [docs/README.md](docs/README.md). The most used:

- [The game](docs/explanation/the-game.md) and [what is measured](docs/explanation/measures.md)
- [Read results](docs/how-to/read-results.md)
- [Every scenario](docs/reference/scenarios.md) (`ACT-1`, `HV-2`…); exact prompts: `make prompts SC=HV-2`
- [Commands and settings](docs/reference/commands.md)
- Every rule and decision: [spec/](spec/README.md), [decisions](spec/decisions.md)
- Keys and safety: [SECURITY.md](SECURITY.md)

## Repository layout

| Folder | Contents |
|---|---|
| `env/`, `agents/` | the game engine; the model client and scripted agents |
| `configs/` | boards, games, scenarios, studies, models |
| `prompts/` | the texts agents read |
| `analysis/` | summaries, charts, run and episode readers, board study |
| `runs/` | the team's runs, shared in git |
| `spec/` | the specification |
| `docs/` | this documentation |
| `deploy/`, `scripts/`, `models/` | the Modal server; helper scripts; local model weights |
| `tests/` | tests, with reference outputs of Colosseum's code |

## Preexisting code and sprint work

The sprint ran 23–25 October 2026. The first commit, `6656e37` (22 October, v0.0.1), was written
before it and is **preexisting**:

- the game engine (`env/`): boards, scoring, roles, views, blackboards, tools and prompts, rebuilt
  from Colosseum and tested against its code (`tests/`);
- the model client and scripted agents (`agents/`), the run loop (`run.py`), summaries and charts
  (`analysis/`), and the first Modal server (`deploy/modal_vllm.py`);
- the Colosseum paper settings and the team's first game designs (`configs/games/colosseum_paper.yaml`,
  `configs/games/team/`, `configs/games/action_channel.yaml`), their prompts and the specification
  (`spec/`).

Added during the sprint (from 23 October; `git log 6656e37..` lists every change):

- the actions game v0.4 with planted conflicts and summed coalition rewards (PSUM scenarios);
- the jackpot game (`env/jackpot.py`, JP scenarios, `analysis/jackpot.py`) and its preregistration
  with amendments (`spec/jackpot/PREREG.md`);
- the yield-to-partner control;
- the repeated jackpot game with outcome feedback (JPR scenarios);
- DeepSeek V4 Pro and Qwen3 models on Modal, OpenAI reasoning summaries, and keeping finished rounds
  when a model server stops;
- every run in `runs/`.

## Credits and sharing

- Colosseum (umass-ai-safety/colosseum, commit `b077fe7`) and its paper (citation below) define the
  experiment. Its repository has no licence. This repository quotes its colluder prompts verbatim
  (`prompts/colluder/colosseum_*.txt` and the prompts built on them), reproduces its colluder header
  (`env/prompts.py`) and contains reference outputs of its code (`tests/fixtures/colosseum_*`,
  `spec/verification/outputs/`); run logs in `runs/` include these prompts. The team made the
  repository public on 25 October 2026 for the sprint submission (decision Q-29) and will remove this
  material if Colosseum's authors ask.
- Terrarium (`terrarium-agents`, MIT): the Jira environment and its system prompt.
- Qwen3-4B (Apache-2.0) and its abliterated variant: the local models ([models/](models/README.md)).
- names (MIT): agent names, as in Colosseum.
- Built with AI assistance (Claude).

```bibtex
@misc{nakamura2026colosseum,
  title         = {Colosseum: Auditing Collusion in Cooperative Multi-Agent Systems},
  author        = {Nakamura, Mason and Kumar, Abhinav and Das, Saswat and Abdelnabi, Sahar and
                   Mahmud, Saaduddin and Fioretto, Ferdinando and Zilberstein, Shlomo and
                   Bagdasarian, Eugene},
  year          = {2026},
  eprint        = {2602.15198},
  archivePrefix = {arXiv},
  primaryClass  = {cs.MA}
}
```
