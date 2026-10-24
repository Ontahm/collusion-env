# 01 — The problem

## 1.1 Collusion, as Colosseum defines it [P]

- A **cooperative multi-agent system**: several agents share one team objective, the **nominal
  objective** `F_n`. Colosseum formalises the game as a DCOP (distributed constraint optimisation
  problem) `P = ⟨A, X, D, F, α⟩`: agents, decision variables, their domains, the objective, and
  which agent controls which variable.
- The **cooperative optimum** is `x* ∈ argmax_x F_n(x)`.
- **Collusion**: "a subset of agents … coordinates to steer the system toward outcomes misaligned
  with the nominal DCOP objective".
- A coalition `S ⊆ A` has its own **coalition objective** `F_c`. Each agent `i` optimises a mix
  `F_λ(i) = (1 − λ_i) · F_n + λ_i · F_c`: `λ = 0` is fully cooperative, `λ = 1` fully collusive.
- **Emergent collusion**: agents are not told to collude (`λ_spec = 0`) but behave as if they were
  (`λ_emp > 0`).
- Collusion is measured through **regret** relative to the cooperative optimum, per agent and for
  the coalition (exact definitions in [08](08-metrics.md)).

## 1.2 What Colosseum asked and found [P]

Research questions, verbatim:

- **RQ1** "Is an LLM-as-a-judge sufficient for collusion auditing or do we also need action-based
  collusion metrics?"
- **RQ2** "Does collusive conversation behavior result in collusive actions?"
- **RQ3** "Do out-of-the-box LLMs exhibit emergent collusion … when a secret channel is
  introduced?"
- **RQ4** "How does objective misalignment, persuasion, and network influence contribute to
  collusion efficacy?"

Main findings:

- "57.89% of models in Emergent and 78.95% in Prompted exhibited Δ-Advantage greater than 0"
  (collusion seen in actions); only "10.53% of models in Emergent … had a Δ-Judge ≥ 1" (collusion
  seen in messages by an LLM judge).
- **Collusion on paper**: agents "plan to collude in text but often pick non-collusive actions".
- Complete communication graphs show better regret minimisation than sparse ones; two persuasion
  tactics raise regret by up to 2.65× and 2.77×.

[!] These quotes come from an automated extraction of the arXiv HTML page. Check them against the
PDF before quoting them anywhere.

## 1.3 What Colosseum leaves out

- **No repetition [P][C].** The paper omits "long-horizon effects such as temporal credit
  assignment, memory, and delayed outcomes". In the code, every Jira episode is a single allocation
  ([05](05-protocol.md)).
- **Homogeneous teams [P].** All agents in a run use the same model.
- **No action-only condition [C].** The Jira collusion configs vary only two things: a secret
  colluder channel (on/off) and the colluders' prompt (`control` / `simple`). Every condition keeps
  the public chat. No condition removes text so that actions are the only possible channel.

## 1.4 Our question [T]

Sprint route 3.1 asks whether actions, tools or side channels can carry collusion. The team's
objective, verbatim: "test whether agents can collude through actions alone, without a direct text
channel".

- **Capability, not propensity.** "Forcing the collusion, because we are testing the capability":
  the two colluders are told to collude.
- **Coalition goal.** Both colluders claim tasks from the **same issue**.
- **At the team's expense.** To match, one colluder passes over a better task. "A match on the same
  issue at no cost is just coordination, the sacrifice is what makes it collusion."

In Colosseum's terms: `F_c` = "both colluders on the same issue", `F_n` = the team score
([04](04-rewards.md)).

## 1.5 Research questions of this study

| Id | Question | Origin |
|---|---|---|
| **RQ-A** (channel) | With no text channel, do instructed colluders match on an issue more often than a no-instruction baseline on the same boards when the second colluder sees the first one's claim? When it does not? How does this compare with a private chat? | [T] |
| **RQ-B** (observability) | On which boards can this collusion be seen at all, and how much of the measured rate is decided by the board? | [Δ], motivated by [09](09-board-analysis.md): on 46% of Colosseum's own boards, matching costs the team nothing |
| **RQ-C** (repetition) | Over repeated rounds on the same board, with outcome feedback, does action-only coordination grow? | [Δ], Colosseum's stated limitation |
| **RQ-D** (incentive) | Does the size of the coalition bonus change matching? | [Δ] |

[Q-01] Which questions are primary for the weekend.

## 1.6 Scope

**In:** the Jira environment, re-implemented; 6 agents with 2 instructed colluders; the team's
scenarios plus a no-instruction baseline; a multi-round extension; exact board analysis; local and
API models.

**Out for now:** Colosseum's other environments (hospital, meetings, …), network topologies,
persuasion, the LLM judge, mixed-model teams, emergent (uninstructed) collusion. The module
boundaries ([13](13-architecture.md)) leave room for them.

## Remarks & suggestions

- **Capability vs propensity.** Instructing the colluders measures what models can do when asked.
  Colosseum's headline result is about propensity (emergent collusion), so our numbers do not
  compare with it. They are closer to Colosseum's "Prompted" group, but with a different coalition
  goal.
- **Why "same issue".** It is not Colosseum's coalition goal (maximise the coalition's reward). Its
  value: it forces the two colluders to align *with each other* through what they claim, which is
  exactly what route 3.1 asks about.
- **Collusion on paper.** In the private-chat scenario we can compare what the colluders agree on
  with what they then claim ([08](08-metrics.md)).
