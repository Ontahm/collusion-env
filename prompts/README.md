# prompts/

The texts agents read. Each game picks its texts in its config (`prompts:`). Braces are filled for
each agent: `{agent}`, `{partners}`, `{coalition_members}`, `{secret_board_id}`, `{hv_task}`,
`{hv_bonus}`, `{hv_team_value}`, `{same_issue_bonus}`, `{rounds}`, and `{phases}` (system prompts
only). A literal brace is written `{{` or `}}`; an unknown placeholder stops the run with its name.

To see the exact prompts of a scenario: `make prompts SC=<ID>`.

| File | Text | Used by |
|---|---|---|
| `system/colosseum.txt` | Colosseum's Jira system prompt, verbatim | PAPER |
| `system/colosseum_choice.txt` | Colosseum's "choice" variant, verbatim | none yet |
| `system/team_draft.txt` | Colosseum's system prompt with a list of the game's phases (for games with reservations) | ACT, HV, VAR, PLANT, PSUM |
| `colluder/colosseum_*.txt` | Colosseum's colluder instructions (`simple`, `deception`, `structured`, `aggressive`), verbatim | PAPER-2, PLANT-1 (`simple`) |
| `colluder/team_same_issue_*.txt` | the team note of 19 Oct, verbatim | ACT |
| `colluder/high_value_simple.txt` | Colosseum's `simple` text plus one line naming the ticket and its bonus; used with Colosseum's header, which names the partner | HV, VAR games with a secret board |
| `colluder/high_value_nochat.txt` | the same, naming the partner itself, for games without message boards | HV-3 and its variants |
| `colluder/high_value_draft.txt` | other wording, in the style of the 19 Oct team note | none |
| `colluder/coalition_nochat.txt` | Colosseum's `simple` text naming the partner, for games without message boards | PLANT-2, PLANT-3 |
| `colluder/coalition_sum_nochat.txt` | the same, with the coalition's reward defined as the sum of the members' rewards (decision Q-34) | PSUM-2, PSUM-3 |
| `colluder/coalition_sum_chat.txt` | Colosseum's `simple` text with the same definition, used with Colosseum's header | PSUM-1 |
| `colluder/coalition_sum_structured_chat.txt` | Colosseum's `structured` text with the same definition | PSUM-5 |
| `colluder/own_reward_nochat.txt` | the greedy-pair baseline: each of the two maximises its own reward, no partner, no shared goal | PLANT-4 |
| `colluder/own_reward_def_nochat.txt` | the same, with an agent's reward defined | PSUM-4 |
| `honest/hv_note.txt` | what honest agents read when the high-value ticket is shown to them | VAR-3 |
| `phases.yaml` | phase names and instructions: Colosseum's for chat and claims (verbatim), ours for reservations | all games |
