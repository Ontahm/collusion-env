# Studies and models

Every study and model file. What each study asks: [the studies](../explanation/studies.md);
every scenario: [scenarios](scenarios.md).

## Studies

In `configs/studies/`. Each plays scenarios by ID, with models and seeds.

| Study | Scenarios | Model | Size |
|---|---|---|---|
| `colosseum_paper.yaml` | PAPER-0..2 | gpt-4.1-mini | seeds 1–10, one round each: 30 episodes |
| `action_channel.yaml` | ACT-0..5 | gpt-4.1-mini | seeds 1–20, one round each: 120 episodes |
| `team_three_games.yaml` | HV-0..3 | gpt-4.1-mini | one episode of 20 rounds per condition |
| `team_variants.yaml` | HV-2, VAR-1..9 | gpt-4.1-mini | one episode of 20 rounds per condition; a menu, run a subset with `--only` |
| `actions_v04.yaml` | PSUM-1, PSUM-2, PSUM-0 | gpt-4.1-mini in the file; play it on gpt-5-mini (`--use-model`) | seeds 1–10, 20 rounds each |
| `actions_v04_followup.yaml` | PSUM-3, PSUM-4 | as `actions_v04.yaml` | stage 2, only if stage 1 shows a result |
| `psum_first_sprint_check.yaml` | PSUM-1, PSUM-0 | gpt-5-mini | the first round only, seeds 1–20 |
| `psum_structured_check.yaml` | PSUM-5 | gpt-5-mini | the first round only, seeds 1–20 (the same boards as the check above) |
| `modal_paper.yaml` | PAPER-0..2 | Qwen3-8B on Modal | seeds 1–5 |
| `local_pilot.yaml` | PAPER-2, HV-1..3 | local Qwen3-4B | every game, 2 rounds: a first check with a real model |
| `local_*.yaml` | as their main study | local Qwen3-4B | rehearsals, below |
| `smoke_scripted.yaml` | PAPER-2, HV-2, ACT-5, VAR-8 | scripted agents | pipeline check (`make smoke`) |

Any study can be played on another model with `--use-model configs/models/<file>.yaml`.

`configs/diagnostics/` holds ad-hoc studies: two on the skip rate (`skip_ablation.yaml`,
`skip_ablation2.yaml`) and one with the public message board back in the PSUM game
(`public_board.yaml`). They are not results: [runs/README.md](../../runs/README.md).

### Local rehearsals

Each main study has a local version with the same conditions and boards (the same seeds, or the
first of them), sized for one GPU. Times measured on an RTX 2060 (Qwen3-4B, thinking off).

| Local study | Mirrors | Size | Time |
|---|---|---|---|
| `local_paper.yaml` | `colosseum_paper.yaml` | 3 conditions, seeds 1–5 | 46 min |
| `local_action_channel.yaml` | `action_channel.yaml` | 6 conditions, seeds 1–20 | not run yet |
| `local_team_three_games.yaml` | `team_three_games.yaml` | 4 conditions, 5 rounds instead of 20 | 12.5 min on Modal (Qwen3-8B) |
| `local_team_variants.yaml` | `team_variants.yaml` | 10 variants, 3 rounds each | not run yet |
| `local_models.yaml` | none | Qwen3-4B, thinking and abliterated, games without chat, seeds 1–3 | 2 h 16 min |

## Models

In `configs/models/`.

| Model file | Label | Needs |
|---|---|---|
| `gpt-4.1-mini.yaml` | `gpt-4.1-mini` | `OPENAI_API_KEY`; carries prices, so summaries report the cost |
| `gpt-5-mini.yaml` | `gpt-5-mini` | `OPENAI_API_KEY`; a reasoning model; carries prices |
| `together-llama-3.3-70b.yaml` | `llama-3.3-70b` | `TOGETHER_API_KEY` |
| `modal-vllm.yaml` | `modal-qwen3-8b` | your Modal server ([how-to](../how-to/run-on-modal.md)); thinking off |
| `modal-vllm-thinking.yaml` | `modal-qwen3-8b-thinking` | the same server, thinking on |
| `modal-deepseek-v4-pro.yaml` | `modal-deepseek-v4-pro` | DeepSeek V4 Pro on your Modal server (`MODAL=deepseek-v4-pro`); thinking off; not run yet |
| `local-qwen3-4b.yaml` | `local-qwen3-4b` | `make local-server` ([how-to](../how-to/run-locally.md)); thinking off |
| `local-qwen3-4b-thinking.yaml` | `local-qwen3-4b-thinking` | `make local-server`; thinking on |
| `local-qwen3-4b-abliterated.yaml` | `local-qwen3-4b-abliterated` | `make local-server-abliterated` |
| `local-llama-server.yaml` | `local` | any llama-server started by hand with `--alias local` |
| `scripted.yaml` | `scripted` | nothing (fixed policies, for checks) |

Any OpenAI-compatible endpoint works: copy a model file and change `label`, `base_url`, `model` and
`api_key_env`. Every setting: [spec/15-configuration.md](../../spec/15-configuration.md).

## Measured runs

The runs of 23 Oct in `runs/`, as `make runs` reports them. API costs come from the summaries;
Modal costs are on each person's Modal dashboard.

| Run | Model | Size | Time | Cost |
|---|---|---|---|---|
| `colosseum_paper` | gpt-4.1-mini | 30 episodes | 16 min | $3.72 |
| `actions_v04` (PLANT, seeds 1–3) | gpt-4.1-mini | 9 episodes, 180 rounds | 21 min | $3.21 |
| `skip_ablation` | gpt-4.1-mini | 12 episodes, 120 rounds | 5 min | $0.98 |
| `skip_ablation2` | gpt-4.1-mini | 24 episodes, 240 rounds | 5 min | $0.68 |
| `actions_v04` (PLANT, seeds 1–3) | gpt-5-mini | 9 episodes, 180 rounds | 51 min | $7.45 |
| `psum_first_sprint_check` | gpt-5-mini | 40 episodes, 1 round each | 8 min | $1.14 |
| `psum_structured_check` | gpt-5-mini | 20 episodes, 1 round each | 5 min | $0.71 |
| `public_board` | gpt-5-mini | 40 episodes, 1 round each | 9 min | $1.51 |
| `modal_paper` | Qwen3-8B (Modal, 8 at once) | 15 episodes | 7 min | |
| `colosseum_paper` (seeds 1–20) | Qwen3-8B (Modal) | 60 episodes | 20 min | |
| `action_channel` | Qwen3-8B (Modal, 16 at once) | 120 episodes | 1.5 min | |
| `action_channel` (ACT-0, ACT-1, seeds 1–100) | Qwen3-8B (Modal) | 200 episodes | 4 min | |
| `action_channel` (ACT-0, ACT-1, seeds 1–40) | Qwen3-8B thinking (Modal) | 80 episodes | 43 min | |
| `local_team_three_games` | Qwen3-8B (Modal, 4 at once) | 4 episodes, 20 rounds | 12.5 min | |
| `actions_v04` (PLANT, seeds 1–3) | Qwen3-8B (Modal) | 9 episodes, 180 rounds | 19 min | |
| `local_pilot` | local Qwen3-4B | 4 episodes, 8 rounds | 15 min | |
| `local_paper` | local Qwen3-4B | 15 episodes | 46 min | |
| `local_models` | three local Qwen3-4B models | 36 episodes | 2 h 16 min | |
