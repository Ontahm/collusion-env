# 14 — Colosseum coverage: what it does, what it does not, what we change

Summary of the previous parts. Each row points to the part with the details.

| Aspect | Colosseum (Jira collusion) | Team note | This study | Part |
|---|---|---|---|---|
| Board generator | issues → 5 task types, tags, priority, effort | Colosseum's | **kept, bit for bit** | [02](02-board.md) |
| Board size | 8 tasks, 2 issues | — | 15 or 20 tasks proposed ([Q-02]) | [02](02-board.md) |
| Agents | 6, skills from board tags, availability 4–10 | 6 | kept | [03](03-agents.md) |
| Costs | effort / skill fit + overload | Colosseum's | kept | [03](03-agents.md) |
| Colluders | 2, random | 2 | kept | [03](03-agents.md) |
| Turn order | random | colluders first | **colluders first** | [03](03-agents.md) |
| Rewards | 20 / 20 / 20 (code defaults) | Colosseum's | kept ([Q-05]) | [04](04-rewards.md) |
| Duplicate claims | can raise the team score; in 3.8% of 8-task optima | — | kept, measured, such boards excluded ([Q-06]) | [04](04-rewards.md) |
| Optimum | exact (Hungarian), separate script | — | exact, built in | [04](04-rewards.md) |
| Coalition goal | maximise the coalition's reward | same issue, unspecified bonus | same issue, explicit bonus in cost units, outside the team score ([Q-07]) | [04](04-rewards.md) |
| Public chat | 1 blackboard for all, 4 planning rounds | none | **none** | [05](05-protocol.md) |
| Secret chat | colluder-only blackboard, 4 rounds | 1 round, chat scenario only | 1 round, chat scenario only | [05](05-protocol.md) |
| Posting while claiming | not offered as a tool (the prompt text says it is) | not allowed | **not allowed** | [05](05-protocol.md) |
| Missing claims | random fill (paper config) | — | no fill, counted ([Q-09]) | [05](05-protocol.md) |
| **Rounds** | **one allocation, no memory** | — | **R rounds with feedback; R = 1 = Colosseum** | [05](05-protocol.md) |
| Honest prompt | Jira prompt | Colosseum's | kept; chat lines dropped when there is no chat ([Q-15]) | [06](06-prompts.md) |
| Colluder prompt | coalition block, variants | two-agent team, same issue | the team's ([Q-16]) | [06](06-prompts.md) |
| Conditions | secret channel × instruction | 5 scenarios | baseline + 4 recommended scenarios ([Q-18]) | [07](07-scenarios.md) |
| Action-only condition | **none** | the core of the study | yes | [07](07-scenarios.md) |
| Metrics | regret, regret gap, reward gap, judge | same issue, sacrifice, coalition advantage | M1–M6 + health; primary M1 on conflict boards vs baseline ([Q-20]) | [08](08-metrics.md) |
| Board observability | **not analysed** | — | `π`, `m`, conflict share; 46% of 8-task boards costless | [09](09-board-analysis.md) |
| Models | 6 API models; Qwen2.5-7B local | gpt-4.1-mini, maybe Llama 3.3 70B | one interface, local or API ([Q-23]) | [10](10-models.md) |
| Study design | 10–20 seeds per condition | — | stratified boards, baseline pairing, sample size | [11](11-study-design.md) |
| Reservation rounds | none | team design of 23 Oct | `reserve` phases: signals or exclusive, all agents or colluders only | [15](15-configuration.md) |
| High-value ticket | none | team design of 23 Oct | objective `high_value_ticket`: coalition bonus, team value, team penalty, selection | [04](04-rewards.md), [15](15-configuration.md) |
| LLM judge, topologies, persuasion, other environments | yes | — | out of scope for now | [01](01-problem.md) |

## What Colosseum does not do, in one list

1. **No repetition**: one allocation per episode; the paper names memory and delayed outcomes as
   left out.
2. **No action-only condition**: every condition keeps the public chat.
3. **No analysis of the boards**: about half of its own boards cannot show collusion as team loss,
   and nothing reports this.
4. **No value for the colluders' incentive**: the coalition goal changes, the rewards do not.
5. **Scoring quirks left open**: duplicate claims can raise the team score; README and code
   disagree on the constants; two different quantities are called "coalition advantage".

## Remarks & suggestions

- *Your remarks:*
