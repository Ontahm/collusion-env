# 13 — Modules and build order

One module per responsibility, each matching a part of this spec. Every module comes with tests
and is reviewed before the next one starts.

## 13.1 Modules (as built)

| Module | Spec | Role | Checked against |
|---|---|---|---|
| `env/board.py` | [02](02-board.md), [03](03-agents.md) | tasks, agent profiles, costs | Colosseum, 1,600 boards bit for bit; 1,165 real episodes |
| `env/roles.py` | [03](03-agents.md) 3.6 | colluders, turn order | Colosseum's runner functions, 800 draws |
| `env/scoring.py` | [04](04-rewards.md), [08](08-metrics.md) | rewards, team score, exact optimum, regrets | Colosseum on 80 boards x 4 assignments |
| `env/objectives.py` | [04](04-rewards.md) 4.6 | coalition objectives, high-value ticket, matching cost | hand cases |
| `env/board_analysis.py` | [09](09-board-analysis.md) | price of collusion, conflict flags | the verification table of 9.3 |
| `env/blackboards.py` | [05](05-protocol.md) | boards, events, prompt formatting | Colosseum's claim events |
| `env/views.py` | [07](07-scenarios.md) | what an agent sees of others' picks | one test per view |
| `env/tools.py` | [05](05-protocol.md) | tool schemas and checks | Colosseum's messages and result dicts |
| `env/prompts.py` | [06](06-prompts.md) | system and user prompts | 144 prompts rendered by Colosseum, identical |
| `env/game_config.py`, `env/configio.py` | [15](15-configuration.md) | configuration, validation | defaults = the paper config file |
| `env/game.py` | [05](05-protocol.md) | the engine: rounds, phases, turns, fill | Colosseum's fill; turn mechanics |
| `agents/llm.py` | [10](10-models.md) | OpenAI-compatible client, Colosseum's turn loop | a fake client |
| `agents/scripted.py` | — | fixed policies for tests and dry runs | — |
| `metrics.py` | [08](08-metrics.md) | per-round metrics | via scoring tests |
| `outcomes.py` | [08](08-metrics.md) | ticket outcomes, chat repetition, herding; also on recorded rounds | hand cases, an old-format run |
| `run.py` | [11](11-study-design.md), [12](12-reproducibility.md) | studies, logs, resume | end-to-end scripted run |
| `analysis/` | [11](11-study-design.md), [09](09-board-analysis.md) | summaries, board study, charts (PNG + PDF) | end-to-end |

## 13.2 How to change something

- A new variant of the game: a config file ([15](15-configuration.md)), no code.
- New wording: a file in `prompts/`.
- A new phase kind, objective or view: one function in `env/game.py`, `env/objectives.py` or
  `env/views.py`, plus its validation in `env/game_config.py` and a test.

## 13.3 Dependencies

[Q-25], decided 2026-10-23. The allowed set: `numpy` and `scipy` (exact optimum), `names==0.3.0`
(agent names, [Q-04]), an HTTP client for the OpenAI-compatible API (`openai` or `httpx`), `pyyaml`
(configs), `pytest` (tests). Each is added only when the module that needs it is built. Anything
else needs agreement first. Used: `httpx` (chosen over `openai`: fewer dependencies, and requests
and responses are logged exactly as sent), `names`, `numpy`, `scipy`, `pyyaml`, `pytest`, and their
own dependencies (`uv.lock`). Added 2026-10-23 with your agreement: `matplotlib` (report charts).

## Remarks & suggestions

- *Your remarks:*
