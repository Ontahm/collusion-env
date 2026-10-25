# Run a study on your own GPU

Qwen3-4B, served by llama.cpp on your machine. No key, no cost. Do [getting started](../getting-started.md)
first.

## 1. Get the models (once)

```bash
make models
```

Downloads Qwen3-4B and its abliterated variant (2.5 GB each) into `deploy/local-weights/` and checks their
SHA-256: one `OK` line per file. Sources: [deploy/local-weights/](../../deploy/local-weights/README.md).

## 2. Start the server

In a first terminal, leave it running:

```bash
make local-server
```

It serves `deploy/local-weights/Qwen3-4B-Q4_K_M.gguf` on `http://127.0.0.1:8080` as `qwen3-4b-q4km`. Ctrl+C stops
it.

- On Nix it uses the flake's `server` shell (llama.cpp with CUDA). The first time on a machine it
  compiles llama.cpp, which takes long. Set your GPU in `flake.nix` (`cudaCapabilities`).
- Elsewhere, install llama.cpp so that `llama-server` is on your PATH.
- Out of memory: lower the context, for example `CTX=8192 make local-server` (default 12288). See
  [context size](#context-size).

## 3. Check the model

In a second terminal:

```bash
make check-model
```

It must end with `[ok] tool call: assign_task(...)` and `result : ready`.

## 4. Run the pilot

```bash
make dry-run STUDY=configs/studies/local_pilot.yaml    # what will run; nothing is called
make run     STUDY=configs/studies/local_pilot.yaml
```

Every game for 2 rounds: a check of the whole chain, not a result. It took 15 minutes on an RTX
2060. The run ends by printing its folder, with `summary.md` and `figures/` inside
([read results](read-results.md)).

## Rehearse a study

Each main study has a local version with the same conditions and boards, sized for one GPU:

```bash
make run STUDY=configs/studies/local_paper.yaml
```

The list: [studies and models](../reference/studies-and-models.md#local-rehearsals). A 4B model
does not predict what gpt-4.1-mini will do. A rehearsal finds problems in the pipeline, the prompts
and the charts.

## Other local models

| Model | Serve it with | Model file |
|---|---|---|
| Qwen3-4B, thinking off | `make local-server` | `configs/models/local-qwen3-4b.yaml` |
| Qwen3-4B, thinking on | `make local-server` | `configs/models/local-qwen3-4b-thinking.yaml` |
| Qwen3-4B abliterated (refusals removed) | `make local-server-abliterated` | `configs/models/local-qwen3-4b-abliterated.yaml` |
| another GGUF model | `make local-server MODEL_FILE=deploy/local-weights/<file>.gguf ALIAS=<name>` | a copy of `local-qwen3-4b.yaml` with a new `label` and `model: <name>` |

Play any study on another model: `ARGS='--use-model configs/models/<file>.yaml'`.

Before playing, a run checks that the server serves the model's name. If not, the episodes are
marked "not run" and the run exits with code 3: start the right server, then add
`--resume runs/<folder>`.

## Context size

The context must hold the longest prompt plus the answer. Longest prompts measured on 23 Oct
(Qwen3-4B, 1,572 calls):

| Games | Longest prompt |
|---|---|
| 4 chat passes (paper conditions, team game 1) | 7,846 tokens |
| team game 2 | 3,478 tokens |
| without chat | under 1,400 tokens |

`CTX=8192` was just enough for the chat games. Lower can cut answers and break tool calls. With
thinking on, an answer can take 4,096 tokens: chat games then need about 12,000.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `llama-server not found` | install llama.cpp, or use Nix |
| out of memory at start | `CTX=8192 make local-server` |
| `make check-model` cannot connect | start the server in another terminal |
| episodes "not run", exit code 3 | start the server of the right model, then `--resume` |
| `ENV_PY_LD_LIBRARY_PATH is empty` (NixOS) | `exit`, then `nix develop` again |
