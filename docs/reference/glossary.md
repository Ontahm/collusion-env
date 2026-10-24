# Glossary

Terms used in the docs, the code and the summaries.

| Term | Meaning |
|---|---|
| board | one generated sprint backlog: issues, tasks, the agents' profiles and costs |
| seed | the number that fixes a board, its colluders and turn order: same seed, same board |
| issue, task | a Jira-like ticket; one of its parts (implement, review, test, docs, triage). Agents claim tasks |
| agent | one of the 6 players; each is a model call per turn, with its own private costs |
| colluder, honest agent | one of the two agents with a hidden coalition goal; one of the four others |
| coalition goal | what the colluders pursue: the coalition's reward (Colosseum), the same issue, or the high-value ticket |
| high-value ticket | one task that pays the coalition a bonus (and, depending on the game, value or harm to the team) |
| planted board | a board built so that one task, T, is the one both colluders want most, with a verified loss for the team if a colluder takes it (actions v0.4) |
| message board | where agents post messages: the public one (all agents) or the secret one (the colluders). Config key `boards`; Colosseum: blackboard; scenario titles also say "secret channel" |
| phase, pass, turn | a round is a list of phases (chat, reserve, claim); a phase has one or more passes; in a pass, each agent takes one turn |
| round | one allocation of the tasks, from the first phase to the scored claims |
| episode | one seed of one condition, played from start to end: one or more rounds |
| reservation, claim | a pick before the end (a signal, or binding); the final pick, which is scored |
| skip | a claim of no task; it is a choice, unlike a random fill |
| random fill | the random task given at the end to an agent that never claimed (Colosseum's rule); not counted as a choice |
| team score, optimum, team loss | the team's joint score; the best possible score on the board (exact); their difference |
| price of collusion | the least the team loses when the coalition reaches its goal |
| conflict board, costless board | price of collusion above zero; equal to zero (collusion cannot show in the team score) |
| regret | the reward an agent left on the table, given what the others did |
| regret gap, reward gap | Colosseum's two "coalition advantage" measures: others' regret minus colluders' regret; colluders' reward minus others' reward |
| same-issue match, collusive match | both colluders on different tasks of one issue; the same, with at least one colluder giving up reward for it |
| health | whether a model can play: failed tool calls, turns without a claim, missing claims |
| game | a rule set: a file in `configs/games/`. The team's "three games" are three such files |
| scenario | a game file plus a few changed settings, under a fixed ID (`ACT-1`): [scenarios.md](scenarios.md) |
| condition | one scenario as played in a study, under a name (`secret_chat`); `--only` selects conditions by name |
| reference condition | the condition the others are compared with, on the same boards: colluders not instructed, or no secret message board |
| study | scenarios × models × seeds: a file in `configs/studies/` |
| run | one execution of a study: a folder in `runs/` |
| model file | how to call one model: a file in `configs/models/` |
