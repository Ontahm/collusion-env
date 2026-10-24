# 12 — Reproducibility and logs

## 12.1 Sources of randomness

| Source | Colosseum [C] | This study |
|---|---|---|
| Board: issues, then agent profiles | `random.Random(seed)` in the environment | the same draws, bit for bit, with the default `configs/board.yaml` ([Q-03]) |
| Agent names | `random.Random(seed + 1337)` over the `names` package | the same, `names==0.3.0` ([Q-04]) |
| Colluders | `random.Random(seed).sample(...)` in the runner | the same draw |
| Turn order | the same runner generator, `shuffle` | colluders first, then the honest agents in list order |
| Noisy scenario swap | — | a generator derived from the seed, logged |
| Model sampling | provider-dependent | a per-call seed where the server supports it, always recorded |

## 12.2 Logged for every episode

- The config, the code version (git commit) and dependency versions.
- The full board: tasks, profiles, costs, colluders, order, and the board quantities of
  [09](09-board-analysis.md).
- Every model call: the request (messages, tools, parameters), the full response (text, reasoning,
  tool calls), token usage, timing, errors.
- Claims per round, scores, metrics.

Logs are append-only: raw logs are never edited; metrics are recomputed from them.

Sampling seeds (when `send_seed` is on) are derived from the episode (condition, seed,
replication), the agent and the exact place of the call (round, turn, call number): each call has
its own seed, and a rerun sends the same ones.

What a run prints is separate from what it records: `logs.py` levels and items (quiet, normal,
verbose, debug) only change the console and `run.log`, never the episode files.

## 12.3 Versions

- Python version and a locked list of dependencies.
- Model: name, revision or snapshot date, and quantisation for local models; server name and
  version.

## 12.4 Setup paths

- **Local**: start an OpenAI-compatible server, set its URL in the config.
- **API**: put the key in `.env` (git-ignored), set the provider URL and model in the config.
- One config block switches between the two.
