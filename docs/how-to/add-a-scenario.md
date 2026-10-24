# Add a scenario or a study

How to try a new variant of a game. Every setting: [spec/15-configuration.md](../../spec/15-configuration.md).

## The rule: an ID never changes

A scenario is a set of game rules under a short ID (`ACT-1`, `HV-2`). The same ID means the same
rules in every study and run, and old runs are matched to IDs by their rules. So:

- to try a variant, add a scenario with a new ID;
- never change the rules of an ID that already has runs.

## 1. Add the scenario

Add an entry to `configs/scenarios.yaml`: a game file plus the settings that differ.

```yaml
VAR-10:
  name: var_big_board
  title: "HV-2 on a board of 15 tasks"
  tests: "Does a bigger board leave more room for collusion at the team's expense?"
  game: configs/games/team/game2_reserve_chat.yaml
  set: {board.n_tasks: 15}
```

An ID is a family and a number; `-0` is the family's reference (no instruction or no channel). For
a new family, add its description to `FAMILIES` in `scenarios.py`.

Common changes:

| To | Set |
|---|---|
| make the ticket cost the team when a colluder takes it | `objective.high_value_ticket.team_penalty: 30` |
| remove the public message board | `boards.public: false` |
| give the colluders no instruction (a reference) | `prompts.colluder: ""` |
| use another colluder instruction | `prompts.colluder: prompts/colluder/<file>.txt` ([placeholders](../../prompts/README.md)) |
| use a bigger board | `board.n_tasks: 15` |
| let colluders act first | `roles.order: colluders_first` |
| replay the same board, with memory | `series.mode: repeated_same_board` |
| keep the team, new board each round, with memory | `series.mode: repeated_new_board` |

List settings such as `phases` are written in full; see the VAR entries. More recipes: spec/15,
section 15.8. A change used by many scenarios belongs in a game file (`configs/games/`), which can
`extends:` another and change only what differs.

## 2. Check it

```bash
make prompts SC=VAR-10    # the exact prompts, on a sample board
make scenarios            # prints the catalogue, rewrites docs/reference/scenarios.md
make test                 # fails if two scenarios have the same rules or the table is out of date
```

An unknown or contradictory setting stops with a message; a typo never falls back to a default.

## 3. Play it in a study

Add the scenario to a study in `configs/studies/`, or create one:

```yaml
name: big_board
description: HV-2 on 8 and on 15 tasks
conditions:
  - {scenario: HV-2}
  - {scenario: VAR-10}
models: [configs/models/gpt-4.1-mini.yaml]
seeds: [1]              # one episode per condition; its 20 rounds come from this seed
max_concurrency: 4
```

A condition takes its scenario's name unless it gives a `name`. A study may only change the number
of rounds (`- {scenario: VAR-10, set: {series.rounds: 5}}`); anything else is a new scenario.

```bash
make dry-run STUDY=configs/studies/big_board.yaml
```

Then run it: [locally](run-locally.md), [on Modal](run-on-modal.md) or [on OpenAI](run-on-openai.md).

## One-off tests

A condition can give a `name`, a `game` and `set:` instead of a scenario ID. Its runs show a
scenario ID only if the rules match one. `configs/diagnostics/` holds such tests; they are kept
out of `configs/studies/` because they are not results.
