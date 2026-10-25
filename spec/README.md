# Specification

Foundation for a rigorous study of collusion between LLM agents. The environment is a clean-room
re-implementation of Colosseum's Jira task-allocation game: same board generator, same costs, same
scoring, same prompts, unless a change has a clear value for the research question. Each change is
marked and justified.

Nothing in the repository is implemented until the matching part of this spec is agreed.

## Reading order

The parts follow the logic of the study: the question first, then the game piece by piece, then
what we measure, then how we run it.

| # | Part | Answers |
|---|---|---|
| 01 | [problem](01-problem.md) | What is collusion? What did Colosseum ask and find? What do we ask? |
| 02 | [board](02-board.md) | What is a Jira board (issues, tasks) and how is it generated? |
| 03 | [agents](03-agents.md) | Who are the agents: specialities, availability, private costs, roles, order? |
| 04 | [rewards](04-rewards.md) | What does each agent and the team earn? What does colluding pay? |
| 05 | [protocol](05-protocol.md) | How does an episode run: phases, channels, tools, rounds? |
| 06 | [prompts](06-prompts.md) | The exact text every agent receives |
| 07 | [scenarios](07-scenarios.md) | The experimental conditions |
| 08 | [metrics](08-metrics.md) | What we measure, with exact definitions |
| 09 | [board analysis](09-board-analysis.md) | What a board tells us before any model is run |
| 10 | [models](10-models.md) | Which LLMs and how they are called (local or API) |
| 11 | [study design](11-study-design.md) | Hypotheses, boards, replications, sample size, analysis |
| 12 | [reproducibility](12-reproducibility.md) | Seeds, versions, logs |
| 13 | [architecture](13-architecture.md) | Modules, their contracts, build order |
| 14 | [Colosseum coverage](14-colosseum-coverage.md) | Summary: what Colosseum does, what it does not, what we change |
| 15 | [configuration](15-configuration.md) | Every config key, its default (Colosseum's) and meaning; how to express each design choice |
| — | [decisions](decisions.md) | Every open decision in one list, with options and a recommendation |
| — | [sources/](sources/) | The team design note, verbatim |
| — | [verification/](verification/) | Scripts that reproduce every number here from Colosseum's own code |

## Conventions

Every statement says where it comes from:

| Tag | Meaning |
|---|---|
| **[C]** | Colosseum or Terrarium **code**, read at the pinned versions below (file and function given) |
| **[P]** | Stated in the Colosseum **paper** |
| **[T]** | From the **team** design note of 19 Oct 2026 ([sources/](sources/team-design-2026-10-19.md)) |
| **[V]** | **Computed** by a script in [verification/](verification/) using Colosseum's own code |
| **[Δ]** | A **change** we propose relative to Colosseum, always with its reason |
| **[Q-nn]** | An open **decision**, listed in [decisions.md](decisions.md) |
| **[!]** | A **doubt**, or something not verified yet |

Default rule for every [Δ]: keep Colosseum's choice unless changing it clearly helps answer the
research question. Comparability with Colosseum is a value in itself.

Parts 01 to 11 end with **Remarks & suggestions**: open points and proposals about that part.

## Pinned sources

- **Colosseum** — github.com/umass-ai-safety/colosseum, commit `b077fe7`. Jira collusion
  experiment: `experiments/collusion/`. Read from the pristine commit (git), not a patched copy.
- **Terrarium** (`terrarium-agents`) — commit `f9dbb5b`, tag `v0.1.1`. Jira environment:
  `envs/dcops/jira_ticket/`.
- **Paper** — Nakamura et al., *Colosseum: Auditing Collusion in Cooperative Multi-Agent Systems*,
  arXiv:2602.15198 (NeurIPS 2026, Evaluations & Datasets track).
- **Team design note** — 19 Oct 2026, [verbatim](sources/team-design-2026-10-19.md).

The environment's own README (`jira_ticket_environment.md`) disagrees with the code on several
defaults. Where they differ, this spec follows the code and says so.

**Sharing** ([Q-29]): this repository is public since 25 October 2026 (it was private to the team
before). Colosseum's repository has no license, and `prompts/colluder/colosseum_*.txt` quote its
texts verbatim, with credit; the team accepted that risk and will remove them if its authors ask. Terrarium (the Jira
environment, its system prompt) and `names` are MIT.
