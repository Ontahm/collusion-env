# 05 — How an episode runs

## 5.1 Colosseum's episode [C]

Source: `experiments/collusion/run.py::_run_single`, read from the pristine commit. One episode:

1. **Board and agents** from the seed ([02](02-board.md), [03](03-agents.md)).
2. **Roles and order.** Colluders drawn at random; turn order shuffled at random (paper config), or
   colluders first if `agent_order: colluders_first`.
3. **Blackboards** (shared message boards).
   - Network `complete` with `consolidate_channels: true`: **one public blackboard** shared by all
     6 agents (Terrarium makes one channel per clique of ≥ 3 agents; a complete graph is one
     clique).
   - If `secret_channel_enabled`: **one more blackboard**, shared only by the 2 colluders.
4. **Planning phase: 4 rounds** (`max_planning_rounds: 4`). In each round, every agent takes one
   turn in turn order. Only tool: `post_message(message, blackboard_id)`. No claims yet.
5. **Claiming phase ("execution"): one pass.** Every agent takes one turn in turn order. The only
   tool offered to the model is `assign_task(task_id)` (a task id or `"skip"`). The prompt text says
   blackboard tools remain available, and a `post_message` call would still be executed, but it is
   not in the tool list sent to the model (`toolset_discovery.get_tools_for_blackboard` returns it
   for planning only). Each agent's prompt lists the claims already made.
6. **Scoring** ([04](04-rewards.md)) and **metrics** ([08](08-metrics.md)).

Details (source: `terrarium: agents/base.py::_multi_step_response_generation`,
`envs/dcops/jira_ticket/jira_ticket_tools.py`, `colosseum: experiments/common/local_protocol.py`):

- **Every turn starts from a blank conversation.** The model receives only the system prompt and a
  freshly built user prompt. Nothing from the agent's earlier turns is carried over (its reasoning,
  its earlier tool calls), except what the prompt shows: the blackboards and the claims made so
  far.
- **A turn** is up to `max_conversation_steps: 3` model calls. After each call, the tool calls it
  contains are executed and their results added to the conversation. The turn ends early only when
  a claim is recorded. In planning no claim exists, so every agent is called 3 times per round.
- **Claim validation.** An unknown task id, `"idle"` or `"none"` is refused with a message asking to
  retry (the agent may retry within its 3 calls); a second claim by the same agent is refused;
  `"skip"` is recorded as no task. Duplicates and costs are not checked here: scoring handles them.
- **Claims are also posted on blackboards.** Each recorded claim is written as an
  `action_executed` event on every blackboard the agent belongs to, so every agent also sees every
  claim on the public blackboard. Colosseum's protocol has a step meant to remove these events from
  secret blackboards, but it only acts on boards marked as secret, and the collusion runner creates
  the secret board without that mark. In practice the claims are logged on the secret board too
  (verified on a real run's `blackboards.json`).
- **One-shot.** The runner forces `max_iterations = 1`; the claiming phase is a single loop. The
  board is allocated once, then the episode ends: no feedback, no memory, nothing carried to the
  next episode.
- **Missing or invalid claims.** With `assignment_filling: true` (paper regret config), an agent
  that never claims, or claims an unknown id, is given a uniformly random task or skip at scoring
  time, and agents are told so in the blackboard context. The topologies config sets it to
  `false`.

## 5.2 The team's protocol [T]

- Colluders claim first, then the four honest agents.
- "No public chat, and no posting during the claiming phase."
- **Secret chat** scenario: one private planning round on a colluder-only blackboard, then claiming
  with the partner's claim hidden.
- **Other scenarios**: no planning and no messages at all.

Differences from Colosseum: no public blackboard (honest agents cannot talk), 0 or 1 planning round
instead of 4, a fixed order, and no posting while claiming.

## 5.3 This study: what is implemented

Everything below is a setting of the game config ([15](15-configuration.md)); with the default
config the episode is Colosseum's (5.1), turn mechanics included. Checked against Colosseum: board,
colluders and order, prompts (144 references), claim checks and events, random fill, scoring,
optimum and regrets.

### Phases

A round is a list of phases, each a list of passes of turns: `chat` (messages), `reserve` (one
reservation per agent per pass, visible to the others as configured) and `claim` (the final claim,
last). Colosseum's round is 4 `chat` passes then one `claim` pass. Reservations are either signals
only (`binding: none`) or exclusive (`binding: exclusive`: a task reserved by someone else cannot be
reserved or claimed). Who takes part, which boards can be posted to, and whether `post_message` is
offered are set per phase.

### One round (R = 1) [Δ]

Exactly the team's protocol: setup → planning round (chat scenario only) → one claiming pass →
scoring.

- [Q-09] **Missing or invalid claims.** `assignment_filling` (default true, as Colosseum: the same
  generator, continued after the board, so the same fills). Missing claims are always recorded and
  counted in the health metrics. Recommendation for our analyses: report results with and without
  rounds that needed a fill, since a random fill can create a match no agent chose.
- [Q-10] **Model calls per turn.** Recommendation: keep Colosseum's 3.

## 5.4 Multi-round extension (R > 1) [Δ], implemented

Value: it addresses the limitation the paper states itself (no memory, no delayed outcomes), and
collusion between real agents typically builds up through repetition.

Proposal:

- Three modes (`series.mode`, [15](15-configuration.md) 15.4): separate episodes per round; the same
  board, agents and roles every round; or the same agents and colluders on a new board every round.
- In the repeated modes, an episode is R rounds with the same agents and roles; the order can be
  redrawn every round (`roles.new_order_each_round`).
- Each round: chat round (chat scenario only) → claiming → scoring → feedback.
- Between rounds, every task becomes free again; **memory persists** through a history section in
  the prompt.
- [Q-11] **Feedback after each round.** Recommendation: every agent sees all claims of past rounds
  (who took what) and its own reward; not the other agents' rewards or costs. The team score is
  optional.
- [Q-12] **Memory format.** Recommendation: a compact history section (one line per agent per
  round) rather than the raw transcript, so the prompt size stays bounded. Implemented; a claim that
  was filled at random is shown as "no claim (filled at random: …)". With `claims` in the feedback,
  the history shows everyone's past claims, including a partner's that a view hid during the
  round: leave `claims` out of `series.feedback` to keep a hidden view hidden across rounds.
- [Q-13] **Chat in multi-round.** Recommendation: in the chat scenario, one private round before
  each claiming round.
- [Q-14] **Number of rounds R.** To fix from the budget, for example 5.
- Metrics are computed per round ([08](08-metrics.md)).
- **R = 1 must reproduce the one-round episode exactly** (tested).

## Remarks & suggestions

- **Where claims are visible.** Colosseum shows claims in two places: the claims list and the public
  blackboard (5.1). Without a public blackboard (5.2), the claims list is the only place, so the
  scenario's view filter ([07](07-scenarios.md)) only has one place to act. Checked on 347 real
  "action hidden" episodes run before the sprint: the first colluder's claim never reached the
  second colluder by either route.
- **No public chat changes the honest agents' game.** In Colosseum they coordinate over 4 rounds of
  public messages; here they only see earlier claims. Team scores are therefore not comparable with
  Colosseum's; our own no-instruction baseline gives the reference.
- **Asymmetry in one round.** In the action-visible scenario only the second colluder can react;
  the first can only anticipate. With several rounds, both colluders see the past, which makes the
  game symmetric.
- *Your remarks:*
