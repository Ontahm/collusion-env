# Run outputs

What a run writes. How to read it: [read results](../how-to/read-results.md); what the measures
mean: [what is measured](../explanation/measures.md).

## The run folder

A run writes one folder: `runs/<date>-<time>__<study>`, with `__<model label>` added when
`--use-model` replaced the study's models. `COLLUSION_RUNS_DIR` or `--out` choose another parent
folder. Scripted runs (`make smoke`) go to `runs/_smoke/`, which is not shared.

| File | Contents | Written |
|---|---|---|
| `study.json` | the study as run: its file, the options (for example `--use-model`), the scenarios | at the start |
| `provenance.json` | git commit (`git_dirty: true` if there were uncommitted changes), Python and package versions, the local server used, the `COLLUSION_*` settings | at the start |
| `run.log` | what the run printed, with times | during the run |
| `episodes/<condition>/<model>/seed<k>_rep<r>/episode.json` | each round in full: board, colluders, turn order, messages, reservations, claims, scores, measures | per episode |
| `.../turns.jsonl` | every turn: the exact prompt, the tools offered, the tool calls and their results | per episode |
| `.../calls.jsonl` | every model request and response, verbatim | per episode |
| `index.csv` | one row per round, with its measures (columns below) | per finished episode |
| `summary.md`, `summary.csv` | per condition and model: one table per kind of game with the measures of its goal, then health, chat, herding and skips, splits by board kind and by round; rates with 95% intervals; tokens; cost | at the end |
| `figures/` | PNG and PDF charts (below) | at the end |
| `paper_comparison.md`, `actions_v04.md` | written by `analysis.paper_figure` and `analysis.actions_v04` when you run them | on demand |

`index.csv` only holds complete episodes. An episode that did not finish is played again by
`--resume`.

## Raw and derived files

The raw records (`episodes/`, `run.log`, `study.json`, `provenance.json`) are never edited.
`index.csv` is written during the run, with the columns that existed then. `summary.*` and
`figures/` are derived: `make summarize RUN=runs/<run>` recomputes them, byte for byte when the
code has not changed. Measures added after a run was made are computed from its `episode.json`
files; they appear in the summary and the charts, not in `index.csv`.

## Figures

| File (`.png` and `.pdf`) | Shows | Drawn for |
|---|---|---|
| `hv_capture` | who holds the high-value ticket: the five outcomes, stacked | high-value games |
| `same_issue` | same-issue match, collusive match, same issue on conflict boards | same-issue games |
| `by_board_kind` | the main rate of each goal on conflict and on costless boards | every goal |
| `by_round` | the main rate over rounds | runs with several rounds |
| `team_loss` | team loss | every run |
| `colosseum` | regret gap and reward gap | every run |
| `reservations` | what the colluders signal in each reservation pass | games with reservations |
| `health` | failed tool results, turns without a claim, missing and duplicate claims | every run |
| `chat_herding` | distinct posts, colluders naming the ticket, largest pile, skipped claims | every run |

One row per condition, one panel per measure, one colour per model. A dot is a rate or a mean, a
line its 95% interval, `n` the number of rounds.

## Per-round columns

`index.csv` has one row per round: the identifiers (condition, model, seed, replication, round,
board seed, goal), the scores and measures of `metrics.py` (team score, optimum, team loss, regrets,
gaps, same-issue match, board quantities, health, tokens, cost), and these, from `outcomes.py` (in
runs made after they were added):

| Column | Meaning |
|---|---|
| `hv_outcome` | who holds the high-value ticket: `colluder_alone`, `colluders_collide`, `shared_with_honest`, `honest`, `nobody` |
| `hv_clean_capture` | `hv_outcome` is `colluder_alone` |
| `posts` | messages posted on all message boards |
| `distinct_post_share` | distinct messages / posts (a repeat counts once) |
| `secret_posts` | messages on the secret message board |
| `colluders_name_hv` | a colluder names the high-value ticket on the secret message board |
| `largest_pile`, `pile_task` | the most agents claiming one task (1: no duplicate), and that task |
| `skips`, `colluder_skips`, `honest_skips` | agents who claimed `skip` (random fills excluded), in total and by role |
| `skip_share` | skips / agents who claimed |
| `reservations_changed` | agents whose last reservation differs from their first |
| `claims_follow_reservation` | share of agents who claimed exactly what they last reserved |

The actions v0.4 columns start with `act_` ([spec/08-metrics.md](../../spec/08-metrics.md), section
8.x). Exact definitions of every column: the docstrings of `metrics.py` and `outcomes.py`.
