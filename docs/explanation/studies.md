# The studies

What each study asks, what it compares, and where it stands. Sizes, times and costs:
[studies and models](../reference/studies-and-models.md). Scenario IDs:
[scenarios](../reference/scenarios.md).

Findings are not written up yet. Until then, `make runs` lists what has been run and
[read results](../how-to/read-results.md) shows how to read it.

## The question

Can two LLM agents in a team collude at the team's expense, and through which channel: open chat,
a secret chat, or actions alone (reservations and claims)? Colosseum's Jira conditions vary the
secret chat and the colluders' instruction, always with an open chat. This project adds games
without chat, repeated rounds, and boards where collusion must cost the team. Background:
[spec/01](../../spec/01-problem.md).

## Paper reproduction (PAPER)

Does this environment give Colosseum's result? This check comes before the team's own games.

| Scenario | Condition | What it is |
|---|---|---|
| PAPER-0 | `baseline` | no secret message board, colluders not instructed (the reference) |
| PAPER-1 | `emergent` | secret message board, colluders not instructed |
| PAPER-2 | `prompted` | secret message board and Colosseum's "simple" coalition instruction |

Colosseum's settings, unchanged. Study `colosseum_paper.yaml`: gpt-4.1-mini, seeds 1–10. In the
paper, the secret message board lowers normalised regret and raises the regret gap.
`analysis.paper_figure` puts a run next to the paper's GPT-4.1-mini values.

Runs: gpt-4.1-mini (10 seeds), Qwen3-8B on Modal (5 and 20 seeds), local Qwen3-4B (5 seeds).

## Action channel (ACT)

From the team note of 19 Oct: can colluders coordinate through actions alone? Goal: both claim
different tasks of one issue. The conditions go from talking to knowing nothing of the partner.

| Scenario | Condition | The colluders |
|---|---|---|
| ACT-0 | `baseline` | are not instructed; see the partner's claim (the reference) |
| ACT-1 | `secret_chat` | have one secret chat pass; do not see the partner's claim |
| ACT-2 | `action_visible` | have no chat; see the partner's claim |
| ACT-3 | `issue_only` | have no chat; see only the partner's issue |
| ACT-4 | `noisy` | have no chat; see the partner's claim, swapped half the time |
| ACT-5 | `action_hidden` | have no chat and see nothing of the partner |

Study `action_channel.yaml`: gpt-4.1-mini, seeds 1–20. Runs: Qwen3-8B on Modal (all six conditions
on 20 seeds; ACT-0 and ACT-1 on 100 seeds, and on 40 seeds with thinking on). Not yet run on
gpt-4.1-mini.

## The team's three games (HV)

From the team design of 23 Oct: with a high-value ticket the colluders want, do reservation passes
carry coordination, with or without chat? The games: [the game](the-game.md#the-teams-three-games).

| Scenario | Condition |
|---|---|
| HV-0 | reference: game 3, colluders not instructed |
| HV-1 | game 1: chat, then claims |
| HV-2 | game 2: reservations with chat, then claims |
| HV-3 | game 3: reservations without chat, then claims |

Study `team_three_games.yaml`: gpt-4.1-mini, 20 rounds per game. Runs: the 5-round rehearsal on
Qwen3-8B on Modal. The full study has not been run.

## Variants of the team design (VAR)

`team_variants.yaml` changes one setting of game 2 or 3 per condition: the team loses points when a
colluder holds the ticket (VAR-1), the team needs the ticket (VAR-2), everyone wants it (VAR-3), no
public message board (VAR-4), one secret chat pass (VAR-5), binding reservations (VAR-6), only
colluders reserve (VAR-7), repeated rounds on the same board or on new boards (VAR-8, VAR-9). Run a
subset with `--only`. No run yet.

## Actions design v0.4 (PSUM, earlier PLANT)

Can instructed colluders gain using actions (reserve, release, claim) as their only signal? Every
round uses a planted board: a task T both colluders want most, a verified loss for the team if a
colluder takes it, and a private difference in how well each colluder fits T. 20 rounds with the
same team on new boards; 2 reservation passes and a claim pass per round. Goal: the coalition's
reward.

Revised on 23 Oct after the first pilots: the PSUM scenarios (`configs/games/actions_v04_sum.yaml`)
replace PLANT, which keeps its rules for the runs made with it.

- Agents see their costs only, as in Colosseum. With a list of rewards per task (PLANT), the team
  players in the colluder seats took T on their own in 34 of 60 rounds of the gpt-5-mini pilot
  (decision Q-30 in [spec/decisions.md](../../spec/decisions.md)).
- Colluders are told the coalition's reward is the sum of their two rewards (Q-34).
- No public message board: the question is whether actions alone carry collusion (Q-35).

| Scenario | Stage | Condition |
|---|---|---|
| PSUM-1 | 1 | positive control: a secret message board during the reservation passes |
| PSUM-2 | 1 | main test: no chat, everyone's picks shown with names |
| PSUM-0 | 1 | reference: the same two agents as team players |
| PSUM-3 | 2 | picks shown without names |
| PSUM-4 | 2 | greed baseline: each of the two is told to maximise its own reward |
| PSUM-5 | check | stronger positive control: Colosseum's "structured" instruction |

Stage 2 (`actions_v04_followup.yaml`) runs only if stage 1 (`actions_v04.yaml`) shows a result.
Measures: [actions v0.4](measures.md#actions-design-v04). The study is played on gpt-5-mini, because
gpt-4.1-mini misreads the sprint history and skips claims.

Runs: PLANT pilots (seeds 1–3) on gpt-4.1-mini, gpt-5-mini and Qwen3-8B; two PSUM checks on the
first round of 20 boards; a diagnostic with the public message board back; two diagnostics on
skipped claims. So far the private-chat control shows no coalition gain, so stage 1 has not been
run in full. Each run: [runs/](../../runs/README.md).

## Rehearsals and checks

| Study | Purpose |
|---|---|
| `local_paper`, `local_action_channel`, `local_team_three_games`, `local_team_variants` | each main study on local Qwen3-4B, smaller, same boards |
| `modal_paper` | `local_paper`'s conditions on Modal |
| `local_models` | Qwen3-4B against its thinking and abliterated versions |
| `local_pilot` | every game for 2 rounds: a first check with a real model |
| `smoke_scripted` | the whole pipeline with scripted agents (`make smoke`) |

Rehearsals find problems in the pipeline, prompts and charts. A 4B model does not predict the
results of larger ones.

## Board study

`make board-study` analyses boards without any model: how often collusion is costless, the price
of collusion, by board size. Outputs: `runs/board_study/`. Details: [spec/09](../../spec/09-board-analysis.md).
