# verification/

Scripts that produce every number and example quoted in the spec **from Colosseum's own code**
(not from a re-implementation). They are for checking the spec only; they are not part of the
environment and the environment never imports Colosseum.

## Requirements

- A Colosseum checkout at commit `b077fe7` and a Terrarium checkout at `v0.1.1` (`f9dbb5b`).
  Only unmodified upstream files are imported: the Jira environment, its prompts, the collusion
  prompts and the exact-optimum solver. For example, outside this repository:

  ```bash
  git clone https://github.com/umass-ai-safety/colosseum && git -C colosseum checkout b077fe7
  git clone https://github.com/umass-aisec/Terrarium terrarium && git -C terrarium checkout v0.1.1
  ```
- Python 3.11+ with `numpy`, `scipy`, `names`, `pyyaml`, `networkx` (the last two are only needed
  because Terrarium imports them).

## Scripts

Every script takes `<terrarium dir> <colosseum dir>` as its first two arguments.

| Script | Produces | Used in |
|---|---|---|
| `example_board.py <T> <C> <seed> <max_tasks>` | one board as JSON: tasks, agent profiles, cost matrix, colluders and turn order drawn as Colosseum's runner does, exact optimum | 02, 03, 04 |
| `render_prompt.py <T> <C> <seed> <agent> <phase> <variant> <provider>` | the exact system and user prompt Colosseum gives that agent | 06 |
| `observability.py <T> <C> <sizes> <n_boards>` | share of boards where both colluders on one issue costs the team nothing | 09 |
| `dup_optima.py <T> <C> <sizes> <n_boards>` | how often the exact optimum contains a duplicate claim or a skip | 04 |
| `check_episodes.py <collusion-env> <Colosseum outputs dir>` | rebuilds every episode's board with `env/board.py` and compares with the prompts agents received | 02 |
| `roles_fixtures.py <T> <C> <out.json>` | colluders and turn orders from Colosseum's `_select_colluders` / `_order_agent_turns`, 4 settings x 200 seeds | `tests/fixtures/colosseum_roles.json` |
| `scoring_fixtures.py <T> <C> <out.json>` | optima, scores, rewards, best-response and sequential regret, random fills, from Colosseum's code (80 boards) | `tests/fixtures/colosseum_scoring.json` |
| `prompt_fixtures.py <T> <C> <out.json.gz>` | 144 system and user prompts rendered by Colosseum's prompt classes from states built with its own objects | `tests/fixtures/colosseum_prompts.json.gz` |
| `board_fixtures.py <T> <C> <out.json>` | hashes of 1,600 boards (8 sizes × seeds 1–200) and two full boards, in the canonical form of `env/board.py` | the bit-for-bit test, `tests/fixtures/colosseum_boards.json` |

Example:

```bash
python -I example_board.py ~/colosseum-deps/terrarium ~/colosseum 1 8
```

## Stored outputs (`outputs/`)

| File | Command |
|---|---|
| `example_board_seed1_tasks8.json` | `example_board.py … 1 8` |
| `prompt_seed1_Jeanene_execution_simple.txt` | `render_prompt.py … 1 Jeanene execution simple openai` |
| `prompt_seed1_Jeanene_execution_simple_vllm.txt` | `render_prompt.py … 1 Jeanene execution simple vllm` (warning line removed) |
| `prompt_seed1_Mona_execution_honest.txt` | `render_prompt.py … 1 Mona execution simple openai` (Mona is honest: no prefix) |
| `observability_seeds1-1000.txt` | `observability.py … 8,10,15,20 1000` |
| `dup_optima_seeds1-1000.txt` | `dup_optima.py … 8,10,15,20 1000` |
| `check_episodes_presprint_runs.txt` | `check_episodes.py … <pre-sprint run outputs>` (1,165 episodes) |
| `board_study_seeds1-1000.md` | `python -m analysis.board_study configs/board_study.yaml` (the environment's own board study) |

The board reference file lives in `tests/fixtures/colosseum_boards.json` (`board_fixtures.py`, run
with Python 3.11; the same command under Python 3.13 gives identical hashes).

## How the scripts call Colosseum

`JiraTicketEnvironment.__init__` needs a communication protocol and log directories. The scripts
skip it (`__new__`) and call the same methods `__init__` calls, in the same order
(`_build_tasks`, `_build_agents`, `_compute_costs`), with the same generator
`random.Random(seed)`. The colluders and turn order are drawn exactly as in
`experiments/collusion/run.py::_run_single` (a second `random.Random(seed)`: `sample` for the
colluders, then `shuffle` for the order).
