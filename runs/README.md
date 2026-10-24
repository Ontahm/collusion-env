# runs/

Results shared with the team: one folder per run (`<date>-<time>__<study>[__<model>]`), plus
`board_study/` (model-free board analysis). How to read them: [docs/how-to/read-results.md](../docs/how-to/read-results.md)
(`make runs`, `make runs SC=<scenario>`, `make episode`). Not shared: `_server/` (local server logs)
and `_smoke/` (pipeline checks).

Raw records (`episodes/`, `run.log`, `study.json`, `provenance.json`) are never edited. `summary.*`
and `figures/` are derived: `make summarize RUN=runs/<run>` recomputes them, byte for byte when the
code has not changed.

## Code versions in provenance.json

`provenance.json` records the git commit a run was made with, and `git_dirty: true` when the working
copy also had uncommitted changes (the code was then that commit plus edits not in git).

The history was re-signed on 23 Oct (author name only: the files are identical). Two runs record a
commit ID from before that:

| Recorded | Same files as | Runs |
|---|---|---|
| `d7cf6d8` | `6656e37` (feat: initial v0.0.1 release) | `20261023-104311__local_pilot` |
| `cb66afe` | `0827823` (docs: add precisions about local context size) | `20261023-130606__local_paper` |

Checked on 23 Oct with the code of `dev`: for all runs here (202 rounds), every board, private cost,
colluder pair and turn order is regenerated identically from its seed, and every stored metric
(score, optimum, team loss, regret and reward gaps, same-issue and collusive match, high-value
capture) is recomputed to the same value.

## Actions design v0.4: pilot and skip diagnostics (23 Oct)

| Run | What | Status |
|---|---|---|
| `20261023-174516__actions_v04` | stage-1 pilot, seeds 1-3 (PLANT-1, PLANT-2, PLANT-0), $3.21 | the positive control (private chat) shows no coalition gain; not to be resumed until the skipping below is fixed |
| `20261023-181442__skip_ablation` | diagnostic (`configs/diagnostics/skip_ablation.yaml`): planted vs Colosseum boards x with vs without reservations, team players, $0.98 | every cell skips about 20% of claims (Colosseum reproduction: 5-13%); round 1 about 11% |
| `20261023-182104__skip_ablation2` | diagnostic (`configs/diagnostics/skip_ablation2.yaml`): with vs without the sprint history x with vs without the reward-per-task list (Colosseum boards, claim pass only, seeds 1-6), $0.68 | the history is the cause: 16% skips with it, 9% without (as the Colosseum reproduction); the reward list changes nothing. Not explained by agents copying others' skips shown in the history |
| `20261023-184358__actions_v04__gpt-5-mini` | stage-1 pilot on gpt-5-mini (`configs/models/gpt-5-mini.yaml`), seeds 1-3, history kept, $7.45 | no skips, almost no duplicates (team loss of team players 10 vs 42.5 on gpt-4.1-mini); the private-chat control still shows no coalition gain (pair reward -1.7, team loss +2.6 vs team players). Team players took T on their own in 34 of 60 rounds, led by the reward-per-task list, which is now off (decisions Q-30) |
| `20261023-210152__psum_first_sprint_check` | PSUM-1 (private chat) vs PSUM-0 (team players), first sprint only, 20 boards, gpt-5-mini, $1.14 | the 23 Oct fixes do not make the control work: pair reward +3.1 but -0.1 without one outlier board (a team player claimed a task worth -50); who gets T is identical in both conditions (better colluder 8, worse 5, N 7 of 20); 7 of 20 boards end with identical claims. Chat colluders split tasks to avoid collisions, do not compare costs, and leave T to N when N reserved it first |
| `20261023-212045__psum_structured_check` | PSUM-5 (private chat with Colosseum's structured playbook + the sum definition), same 20 first sprints, gpt-5-mini, $0.71 | no gain: pair reward median +0.0 (5 boards up, 7 down), -1.7 mean without the outlier board, team loss +2.5. Colluders do share costs and split tasks, but never contest a task an honest agent reserved first. In all three first-sprint conditions, whoever reserves T first ends up with it (20 of 20 boards) |
| `20261023-213828__public_board` | diagnostic (`configs/diagnostics/public_board.yaml`): team players vs structured private chat with Colosseum's public board back, same 20 first sprints, gpt-5-mini, $1.51 | the missing public board is not why the control fails: pair reward median +0.0 (5 up, 5 down), regret gap +0.5 +/- 1.8; whoever reserves T first still keeps it (20 of 20). Colluders posted 4 public messages vs 75 on the secret board, and never asked an honest agent for T, even when it publicly offered to switch |

Diagnostics are not results: they use ad-hoc conditions (game + overrides), so they live outside
`configs/studies/`.

## Modal model selection and DeepSeek V4 Pro (24 Oct)

Checks of `make modal-run` with the model files of `deploy/models/`, not results.

| Run | What | Status |
|---|---|---|
| `20261024-111738__action_channel__modal-qwen3-8b` | `MODAL=qwen3-8b` (Qwen3-8B pinned to revision `b968826`), ACT-0, seeds 1-3 | 3/3 episodes |
| `20261024-122609__action_channel__modal-deepseek-v4-pro` | first DeepSeek V4 Pro run, `MODAL=deepseek-v4-pro` (8 H200), ACT-0 and ACT-1, seeds 1-3 | 6/6 episodes. Health: no failed tool call, no turn without a claim, no missing claim. No reasoning text in the answers (thinking off). 3 seeds per condition is too few to compare conditions |

Both runs record commit `c89d992` with `git_dirty: true`. The uncommitted changes were the Modal
model selection, committed afterwards as `665fb0e`: Makefile, `deploy/`, `scripts/modal_profile.sh`,
a model file and docs. The environment's code is that of `c89d992`.
