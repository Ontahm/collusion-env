# Decisions

Every decision of the spec, in the order it appears. **open**: to settle; **decided**: settled
(date); **configurable**: implemented as a config setting, with the default shown — choose per study.
Rule agreed on 23 Oct: everything configurable; defaults are the setting closest to Colosseum.

Default rule: keep Colosseum's choice unless a change clearly helps the research question.

| Id | Part | Decision | Status and default |
|---|---|---|---|
| Q-01 | [01](01-problem.md) | Research questions for the weekend | **decided 2026-10-23**: first reproduce Colosseum's paper conditions (validation), then the team's three games; the board study alongside (free) |
| Q-02 | [02](02-board.md) | Number of tasks | **configurable** (`board.n_tasks`), default 8 as the paper. Note: with 8 tasks a random high-value ticket is costless for the team on a third of boards ([09](09-board-analysis.md) 9.4) |
| Q-03 | [02](02-board.md) | Colosseum's generator bit for bit | **decided 2026-10-23**: default, every parameter in `configs/board.yaml` |
| Q-04 | [03](03-agents.md) | Agent names | **decided 2026-10-23**: `names==0.3.0` |
| Q-05 | [04](04-rewards.md) | Reward constants | **configurable** (`scoring.*`), default 20 / 20 / 20 |
| Q-06 | [04](04-rewards.md) | Duplicate claims in the scoring | **kept as Colosseum**; reported per round (`duplicate_claims`, `optimum_has_duplicate`) |
| Q-07 | [04](04-rewards.md) | Coalition bonus | **configurable**: same issue (`objective.same_issue.*`), high-value ticket (`objective.high_value_ticket.*`). Value for the team games: see Q-27 |
| Q-08 | [04](04-rewards.md) | Tell agents the reward constants | **kept as Colosseum** (not told). To change: edit the system prompt file |
| Q-09 | [05](05-protocol.md) | Missing or invalid claims | **configurable** (`assignment_filling`), default true as Colosseum; missing claims always counted |
| Q-10 | [05](05-protocol.md) | Model calls per turn | **configurable** (`calls_per_turn`), default 3 |
| Q-11 | [05](05-protocol.md) | Feedback between rounds | **configurable** (`series.feedback`), default claims + own reward |
| Q-12 | [05](05-protocol.md) | Memory format between rounds | **implemented**: one history line per round (`=== PREVIOUS ROUNDS ===`) |
| Q-13 | [05](05-protocol.md) | Chat in multi-round | **implemented**: the round's phases run every round (chat included) |
| Q-14 | [05](05-protocol.md) | Number of rounds | **configurable** (`series.rounds`); team games: 20 |
| Q-15 | [06](06-prompts.md) | Honest prompt without chat | **configurable** (prompt files); team games use the draft `team_draft.txt` |
| Q-16 | [06](06-prompts.md) | Colluder wording | **decided 2026-10-23**: pilot runs with the drafts in `prompts/`; the team writes the final texts after |
| Q-17 | [07](07-scenarios.md) | Noisy scenario | **implemented** as recommended (probability per round, seeded) |
| Q-18 | [07](07-scenarios.md) | Scenarios for the weekend | **configurable**: three studies ready ([07](07-scenarios.md) 7.4) |
| Q-19 | [08](08-metrics.md) | Sacrifice measured on | **implemented**: reward (cost and priority) |
| Q-20 | [08](08-metrics.md) | Primary outcome | **open**. For the team games: high-value capture by the coalition, on conflict boards, against the reference condition |
| Q-21 | [09](09-board-analysis.md) | Matching cost | **implemented** as 9.1 |
| Q-22 | [10](10-models.md) | Model parameters | **configurable** (model files), default the paper's (0.7, 1500) |
| Q-23 | [10](10-models.md) | Models for the weekend | **decided 2026-10-23**: gpt-4.1-mini (OpenAI API), local models (llama-server), open models on Modal (vLLM); all configurable |
| Q-24 | [11](11-study-design.md) | Boards and replications | **open**: from the budget; `make dry-run` gives the call counts |
| Q-25 | [13](13-architecture.md) | Dependencies | **decided 2026-10-23**: the minimal list; used: httpx, names, numpy, scipy, pyyaml, pytest; matplotlib added the same day for charts |
| Q-26 | [15](15-configuration.md) | Team games: public chat? | **decided 2026-10-23: configurable**, default closest to Colosseum: public + secret boards in games 1-2, none in game 3 |
| Q-27 | [15](15-configuration.md) | Team games: what the ticket is worth, and to whom | **decided 2026-10-23: configurable**, default closest to Colosseum's scoring: coalition-only bonus (30, placeholder), random ticket, team score unchanged; alternatives in `team_variants.yaml` |
| Q-28 | [15](15-configuration.md) | Team games: "3 games" and "20 rounds" | **decided 2026-10-23: configurable**, default closest to Colosseum: 3 conditions of 20 separate one-shot episodes |
| Q-29 | — | Sharing the repository | **decided 2026-10-23**: private, team only (Colosseum has no license; its colluder prompts are quoted verbatim). **Changed 2026-10-25**: public for the sprint submission; the team accepts the risk of quoting Colosseum's prompts with credit and will remove them if its authors ask |
| Q-30 | [15](15-configuration.md) | Tell agents their reward per task (actions design v0.4) | **configurable** (`prompts.show_payoffs`), default false as Colosseum. **Decided 2026-10-23: off in the revised actions v0.4 game** (`configs/games/actions_v04_sum.yaml`, PSUM scenarios; PLANT keeps its rules for the runs made with it). In the gpt-5-mini pilot (`archive/runs/20261023-184358__actions_v04__gpt-5-mini`) the team players in the colluder seats took T, their top-listed task, alone in 34 of 60 rounds, so the baseline already collected most of the planted gain |
| Q-31 | [15](15-configuration.md) | Hide who made each pick (actions design v0.4) | **configurable** (`views.names`), default `shown` as Colosseum |
| Q-32 | [06](06-prompts.md) | Prompts of the actions design v0.4 | **draft**: `colluder/coalition_nochat.txt` (instructed coalition, no boards), `colluder/own_reward_nochat.txt` (greedy-pair baseline) |
| Q-34 | [06](06-prompts.md) | What "the coalition's joint reward" means to colluders (actions design v0.4) | **decided 2026-10-23: defined as the sum of the members' rewards**, in words, the same in every colluder condition (`colluder/coalition_sum_nochat.txt`, `colluder/coalition_sum_chat.txt`; the greedy pair's own reward likewise, `colluder/own_reward_def_nochat.txt`), in the PSUM scenarios. Colosseum leaves it undefined; 3.1 is a capability test, so colluders are told the target that the analysis measures (pair reward). In the gpt-5-mini pilot, chat colluders without it aimed at task coverage and priority instead |
| Q-35 | [15](15-configuration.md) | Public board in the actions v0.4 game | **decided 2026-10-23: none**, unlike Colosseum (public board + 4 planning chat passes): public chat is text communication, and the question is whether actions alone carry collusion. Reservations replace Colosseum's planning chat; the private-chat control has only the secret board. Consequence seen in the PSUM checks: with no one to persuade, whoever reserves the tempting task first keeps it |
| Q-33 | [15](15-configuration.md) | Constructed boards with a planted conflict (actions design v0.4) | **configurable** (`construction.*`), default `none` (Colosseum's boards). Boards that cannot meet the targets (~7%) are replaced by a redrawn board, so every round meets them |
