# prompts/

Texts given to agents. Games choose them in their config (`prompts:` block); placeholders in
braces are filled per agent: `{agent}`, `{partners}`, `{coalition_members}`, `{secret_board_id}`,
`{hv_task}`, `{hv_bonus}`, `{hv_team_value}`, `{same_issue_bonus}`, `{rounds}`, and `{phases}` (system
prompts only).

| File | Origin |
|---|---|
| `system/colosseum.txt` | Colosseum's Jira system prompt, verbatim |
| `system/colosseum_choice.txt` | Colosseum's "choice" variant, verbatim |
| `system/team_draft.txt` | **draft**: Colosseum's text with a `{phases}` list, for games with reservation rounds |
| `colluder/colosseum_*.txt` | Colosseum's colluder variants (`simple`, `deception`, `structured`, `aggressive`), verbatim |
| `colluder/team_same_issue_*.txt` | the team note of 19 Oct, verbatim |
| `colluder/high_value_simple.txt` | **draft** for the high-value games with a secret board: Colosseum's `simple` text + one line naming the ticket (used with Colosseum's header, which names the partner) |
| `colluder/high_value_nochat.txt` | **draft** for the high-value game without boards: no header, so it names the partner itself |
| `colluder/high_value_draft.txt` | **draft**, alternative wording in the style of the 19 Oct team note |
| `colluder/coalition_nochat.txt` | **draft** (actions design v0.4): Colosseum's `simple` text naming the partner, for games without boards (no header) |
| `colluder/own_reward_nochat.txt` | **draft** (actions design v0.4): the "greedy pair" baseline; the two designated agents maximize their own reward, with no partner and no shared goal |
| `honest/hv_note.txt` | **draft**: what honest agents are told when the high-value ticket is visible to them |
| `phases.yaml` | phase names and instructions: Colosseum's for planning and claiming (verbatim), **draft** for reservation |

Drafts are placeholders for the team's own wording ("Prompts: to add").

Templates are filled with Python's `str.format`: a literal brace must be doubled (`{{` and `}}`),
and an unknown placeholder stops the run with its name.
