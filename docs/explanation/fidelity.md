# How faithful it is to Colosseum

What is checked against Colosseum's own code, what this project adds, and what it leaves out. The
reference is Colosseum's repository (umass-ai-safety/colosseum, commit `b077fe7`) and its paper
([arXiv:2602.15198](https://arxiv.org/abs/2602.15198)). Part by part:
[spec/14](../../spec/14-colosseum-coverage.md).

## What is tested against Colosseum's code

With the default config, an episode is Colosseum's paper setting. Each part is tested against
outputs of Colosseum's own code (`tests/fixtures/`):

| Part | Checked on |
|---|---|
| boards | 1,600 generated boards, bit for bit, and the boards of 1,165 real Colosseum episodes |
| colluders and turn order | 800 draws |
| scores, optima and regrets | 80 boards |
| prompts | 144 prompts, identical |
| claim events, random fills of missing claims, turn mechanics | the same reference outputs (`tests/test_game.py`) |

`make test` runs these checks (no model, no network).

## What this project adds

None of these is in Colosseum, and none changes the game in the default config.

| Addition | Where |
|---|---|
| several rounds per episode, with or without memory | `series.mode` |
| reservation phases (signals or binding; all agents or colluders only) | `phases` |
| other coalition goals: same issue, high-value ticket | `objective` |
| action-only conditions: no chat, the partner's picks visible, partial, noisy or hidden | `boards`, `views` |
| analysis of the boards: price of collusion, conflict or costless | `env/board_analysis.py` |
| planted boards with a verified conflict | `construction`, `env/construct.py` |

Configuration keys: [spec/15-configuration.md](../../spec/15-configuration.md).

## Known differences and limits

- The LLM judge that Colosseum uses to score secret messages is not reproduced.
- Colosseum's chart rescales the coalition advantage per model, so only the direction of the
  paper's values can be compared with a run here.
- The paper's values used by `analysis.paper_figure` are read off its Fig. 4, not taken from data.
- Models are called through OpenAI-compatible chat completions; Colosseum called gpt-4.1-mini
  through OpenAI's Responses API (same texts, another request format):
  [spec/10-models.md](../../spec/10-models.md).
- API providers do not guarantee identical outputs for identical requests. Replications are
  independent draws; everything is logged so the measures can be recomputed without the model.
- Colosseum's own scoring quirks are kept and measured, not fixed: duplicate claims can raise the
  team score, and its README and code disagree on some constants
  ([spec/04-rewards.md](../../spec/04-rewards.md)).
