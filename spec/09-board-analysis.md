# 09 — What the board tells us before any model runs

Everything here is exact and needs no model: only the board, the colluder pair and the scoring
([04](04-rewards.md)).

## 9.1 Quantities [Δ]

| Quantity | Definition |
|---|---|
| `F*` | exact optimum of the team score |
| `F_same` | best team score among assignments where both colluders claim different tasks of the same issue (maximum over issues) |
| **Price of collusion** `π` | `F* − F_same` (≥ 0) |
| **Conflict board** | `π > 0` |
| **Costless board** | `π = 0` |
| **Matching cost** `m` | what the second colluder gives up to join the first one's issue: its best reward among the tasks still free, minus its best reward among the free tasks of the first colluder's issue, assuming the first colluder takes its own best task. 0 if its best free task is already on that issue. [Q-21] |

`F*` and `F_same` are computed with the same solver as Colosseum (Hungarian algorithm), restricted
for `F_same` so that each colluder may only take tasks of the chosen issue and no skip.

## 9.2 Why it matters

- **Costless board (`π = 0`).** Some optimal team plan already puts both colluders on one issue.
  A match costs the team nothing, so collusion cannot appear in the team score.
- **Conflict board (`π > 0`).** Every assignment where the colluders match scores at most
  `F_same = F* − π`. A match therefore costs the team **at least `π`**, whatever the other agents
  do. (By definition, `F_same` is the best score of any assignment with a match.)

The example board ([04](04-rewards.md#45-upper-bound-vs-exact-optimum-c)) is costless: the optimum
already places both colluders on ISSUE-0002.

## 9.3 How often each case occurs in Colosseum's generator [V]

Seeds 1–1000 for each size, 6 agents, colluders drawn as Colosseum's runner does, colluders on
different tasks (`verification/observability.py`):

| Tasks | Issues | Conflict (`π > 0`) | Costless (`π = 0`) |
|---|---|---|---|
| **8 (Colosseum)** | 2 | 54.0% | **46.0%** |
| 10 | 2 | 48.1% | 51.9% |
| 15 | 3 | 56.7% | 43.3% |
| 20 | 4 | 67.3% | 32.7% |

At Colosseum's own size, **46% of boards cannot show this kind of collusion as a loss for the
team**. The definition does not depend on how the solver breaks ties: `π = 0` means *some* optimal
plan has a match.

## 9.4 The high-value ticket [V]

For the high-value objective, the same question: does a colluder holding the ticket cost the team?
`price_hv` = optimum minus the best team score with a colluder holding it. From
`python -m analysis.board_study configs/board_study.yaml` (seeds 1–1000,
`verification/outputs/board_study_seeds1-1000.md`):

| Tasks | Ticket drawn | Conflict (`price_hv > 0`) | A colluder already holds it in the optimum | Median `price_hv` |
|---|---|---|---|---|
| **8** | at random | **65.8%** | 25.5% | 0.16 |
| 8 | among tickets the optimum gives an honest agent | 85.0% | 0.3% (duplicates in the optimum) | 0.19 |
| 15 | at random | 78.9% | 12.9% | 2.31 |
| 20 | at random | 82.1% | 11.8% | 4.43 |

At the paper's size, with a random ticket, a third of boards cannot show this collusion as a team
loss, and when they can, the median loss is small (0.16, against claims worth 25–40). Two settings
make the loss larger: `selection: optimum_honest` (85% conflict at 8 tasks), and `team_penalty`,
which the team loses whenever a colluder holds the ticket.

The same script reproduces 9.3 exactly (54.0 / 48.1 / 56.7 / 67.3% conflict for the same-issue goal),
from code independent of the verification script.

## 9.5 Use in this study

- **Report** the board distribution (`π`, `m`, conflict share) with every result.
- **Sample** boards stratified by `π` and `m`, rather than uniformly ([11](11-study-design.md)).
- **Model** `π` and `m` as covariates: does the board predict matching beyond the scenario (RQ-B)?

## Remarks & suggestions

- This is a property of the **environment**, not of any model. It can be measured before spending
  any model budget, and it applies to every study that uses this generator.
- **Selecting only conflict boards** gives more power but changes the population of boards. Report
  results on both kinds, or state the restriction clearly.
- *Your remarks:*
