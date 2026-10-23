# runs/

Results shared with the team: one folder per run (`<date>-<time>__<study>[__<model>]`), plus
`board_study/` (model-free board analysis). How to read them: [README section 8.1](../README.md#81-reading-a-teammates-run)
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
| `20261023-174516__actions_v04` | stage-1 pilot, seeds 1-3 (PLANT-1, PLANT-2, PLANT-0), $3.21 | the positive control (private chat) shows no coalition gain; not to be resumed until the skipping below is understood |
| `20261023-181442__skip_ablation` | diagnostic (`configs/diagnostics/skip_ablation.yaml`): planted vs Colosseum boards x with vs without reservations, team players, $0.98 | every cell skips about 20% of claims (Colosseum reproduction: 5-13%); round 1 about 11% |
| `20261023-182104__skip_ablation2` | diagnostic (`configs/diagnostics/skip_ablation2.yaml`): with vs without the sprint history x with vs without the reward-per-task list | in progress |

Diagnostics are not results: they use ad-hoc conditions (game + overrides), so they live outside
`configs/studies/`.
