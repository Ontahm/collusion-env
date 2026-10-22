# 11 — Study design (to freeze before the runs)

This part becomes the pre-registration once the open decisions are settled: written and committed
before any result exists.

## 11.1 Unit and factors

- **Unit**: one episode = one board × one scenario × one replication (with R rounds).
- **Factors**: scenario ([07](07-scenarios.md)); board, sampled as in 11.3; replication. Optional:
  bonus `k` ([Q-07]), rounds `R`, model.

## 11.2 Hypotheses (draft, tied to the questions of [01](01-problem.md))

| Id | Hypothesis | Test |
|---|---|---|
| H-A1 | In action visible, M1 is higher than in the baseline on the same boards | paired difference by board, one-sided |
| H-A2 | M1: secret chat > action visible > action hidden | ordered comparisons, Holm-corrected |
| H-B1 | Share of costless boards | computed exactly, no test needed ([09](09-board-analysis.md)) |
| H-B2 | `π` and `m` predict M1 beyond the scenario | logistic model with board features, evaluated on held-out boards |
| H-C1 | In action visible, M1 increases over rounds | trend over rounds, by board |

Each hypothesis gets a decision rule, and the reading of every possible outcome is written before
the runs.

## 11.3 Boards

- Drawn from generator seeds; the list is **fixed before running** and committed.
- **Stratified** by conflict / costless and by `m`, rather than drawn uniformly.
- Boards whose exact optimum contains a duplicate are excluded ([04](04-rewards.md)).
- If a claim rests on choosing the best condition after seeing results, it is confirmed on
  **held-out boards** never used for that choice.

## 11.4 Replications and pairing

- Every scenario **and** the baseline run on the same boards.
- A replication is an independent model draw of the same episode.
- Analyses are **paired by board** (differences within a board), which removes board-to-board
  variation from comparisons.

## 11.5 Sample size

Episodes per arm to detect a difference in M1 at α = 0.05 (two-sided) with 80% power,
two-proportion test, **without** pairing:

| Baseline rate | +10 points | +15 | +20 | +30 |
|---|---|---|---|---|
| 10% | 199 | 100 | 62 | 32 |
| 20% | 294 | 138 | 82 | 39 |
| 30% | 356 | 163 | 93 | 42 |
| 45% | 392 | 173 | 96 | 41 |

Pairing by board lowers these numbers when board effects are strong. Reading: detecting a
15-point effect needs about 100–170 episodes per arm; anything smaller than 10 points is out of
reach for a weekend. A lower chance level (more issues, [Q-02]) makes the same effect cheaper to
detect. [Q-24] Number of boards and replications, from the budget.

## 11.6 Analysis

- Rates with **Wilson 95% intervals**.
- Scenario vs baseline: **paired differences**, with bootstrap intervals that resample **boards**
  (episodes of one board are not independent).
- Board effects: logistic regression with board features, evaluated by cross-validation grouped by
  board.
- Several primary comparisons: **Holm** correction.
- Health metrics read first: a model with failing tool calls is reported, not interpreted.

## Remarks & suggestions

- Arms beyond the four recommended scenarios ([Q-18]) cost about 100+ episodes each to be
  informative; add them only if the budget allows.
- *Your remarks:*
