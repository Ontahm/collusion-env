# Run a study on Modal

An open-weight model on [Modal](https://modal.com), which rents GPUs by the second: Qwen3-8B by
default, or DeepSeek V4 Pro. The environment calls it like any OpenAI-compatible API. Tested on 23
Oct 2026 with Qwen3-8B on one L40S; DeepSeek V4 Pro has not been run yet.

Modal only runs models whose weights are public. gpt-4.1-mini is not: use
[OpenAI](run-on-openai.md) for it.

## Quick start

```bash
make modal-setup                                                          # once per person
make modal-run STUDY=configs/studies/action_channel.yaml                  # asks which model
make modal-run STUDY=configs/studies/action_channel.yaml MODAL=qwen3-8b   # or name it
```

`make modal-setup`:

1. installs the `modal` command if missing;
2. logs you in (browser);
3. creates a key for your server, in the Modal secret `collusion-vllm` and in `.env`;
4. deploys the server and saves its URL in `.env`;
5. checks that the model answers, and that a request without the key gets HTTP 401;
6. stops the server.

Run it again to get a new key.

`make modal-run` downloads the model's weights (on a CPU container, the first time only), deploys,
runs the study, then stops the server, also on error or Ctrl+C.

| Variable | Default | Meaning |
|---|---|---|
| `MODAL` | asked in a terminal, else `qwen3-8b` | the model: a file of `deploy/models/` (below) |
| `CONC` | 16 | episodes played at once |
| `ARGS` | | more run options, for example `ARGS='--seeds 1-3'` or `ARGS='--only baseline,secret_chat'` (condition names) |

Stop by hand: `modal app stop collusion-vllm`.

Everyone uses their own Modal account. The model file is shared; your URL and key stay in your
`.env`.

## Models

| `MODAL=` | Model | GPU | Modal price (Oct 2026) |
|---|---|---|---|
| `qwen3-8b` | Qwen3-8B, thinking off | 1 L40S | $1.95/h |
| `qwen3-8b-thinking` | Qwen3-8B, thinking on (same server) | 1 L40S | $1.95/h |
| `deepseek-v4-pro` | DeepSeek V4 Pro, release of 13 Aug 2026, thinking off | 8 H200 | $36.32/h |

DeepSeek V4 Pro's weights are 893 GB. The first `make modal-run` downloads them on a CPU container,
where no GPU is billed, into the Modal volume that keeps them for later runs: 63 minutes on 24 Oct.
The server may then take up to 60 minutes to start.

## What you need

- A Modal account with a payment method: Modal asks for one before any GPU runs, even with free
  credits. If you prefer, use a card with a low spending limit.
- `make install` done.

## What happens on Modal

- `modal run deploy/modal_vllm.py::download` fetches the weights into a Modal volume, on CPU. Once
  they are there, it only checks them.
- `modal deploy` builds an image (CUDA, vLLM) and registers a URL. No GPU runs yet.
- The first request starts a container on a GPU. vLLM loads the model, then answers: about 2.5
  minutes when the weights are cached, longer the first time (Qwen3-8B: 16 GB to download).
- 15 minutes after the last request, the container stops and billing stops.

Runs and `make check-model` wait for the start, up to `startup_wait_s` in the model file (20 minutes
for Qwen, 60 for DeepSeek), and print `'<model>' is up` when ready.

## How long a study takes

Measured on 23 Oct (Qwen3-8B, one L40S, server already started):

| Study | Episodes | Time (episodes at once) | Tokens in / out |
|---|---|---|---|
| `modal_paper.yaml` (paper conditions, seeds 1–5) | 15 | 7 min (8) | 3.9 M / 77 k |
| `action_channel.yaml` | 120 | 1.5 min (16) | 0.9 M / 28 k |
| `local_team_three_games.yaml` (5 rounds per game) | 4 | 12.5 min (4) | 1.7 M / 37 k |

An episode plays its turns one after another, so long episodes are slow on any GPU. Run several
studies in one session to pay for one start only.

## Stop the server and check costs

```bash
modal app stop collusion-vllm      # stop now (otherwise 15 idle minutes, billed)
modal app list                     # what is deployed
modal app logs collusion-vllm      # the server's log
```

The Modal dashboard shows whether a container is running and what each session cost.

## Add a model

Each file of `deploy/models/` holds one server's settings, read when it deploys, and the model file
the runs use. To add a model, copy a file, change it, then `make modal-run MODAL=<file name>`.

| Setting | Default | Meaning |
|---|---|---|
| `DESCRIPTION` | | shown in the menu |
| `MODEL_CONFIG` | | the model file runs use (`configs/models/`); its `model:` must equal `SERVED_NAME` |
| `MODEL` | `Qwen/Qwen3-8B` | Hugging Face model ID |
| `MODEL_REVISION` | `main` | the model's commit: pin it for any run you report |
| `SERVED_NAME` | = `MODEL` | the name the API exposes (`model:` in the model file) |
| `TOOL_PARSER` | `hermes` | how vLLM reads tool calls: `hermes` for Qwen, `llama3_json` for Llama 3.x |
| `REASONING_PARSER` | `qwen3` | separates the thinking text; empty for models without it |
| `GPU` | `L40S:1` | Modal GPU type and count |
| `MAX_MODEL_LEN` | `16384` | context length (the longest prompt measured is 7,846 tokens) |
| `REGION` | `us-east` | where requests are routed |
| `VLLM_VERSION` | `0.21.0` | vLLM release |
| `VLLM_ARGS` | | more `vllm serve` options, for example `--tensor-parallel-size 8` for 8 GPUs |
| `STARTUP_MINUTES` | 20 | how long the server may take to start; set `startup_wait_s` in the model file to match |

A wrong tool parser shows as turns without tool calls: `make check-model` fails.

Thinking: `modal-vllm.yaml` turns Qwen3's thinking off; `modal-vllm-thinking.yaml` turns it on.

## Share a server

To use someone else's server, get its key and URL privately (a password manager, not a chat or
git) and put them in your `.env` as `MODAL_VLLM_API_KEY` and `MODAL_VLLM_BASE_URL`. Keep the URL
private: without the key a request is refused, but it still wakes a billed GPU for 15 minutes.

## Set up by hand

The steps of `make modal-setup`, if one needs redoing:

```bash
uv tool install modal
modal setup                    # log in
KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
modal secret create collusion-vllm VLLM_API_KEY="$KEY" --force
echo "MODAL_VLLM_API_KEY=$KEY" >> .env       # replace an older key line instead, if there is one
set -a; . deploy/models/qwen3-8b.env; set +a # the server's settings
modal deploy deploy/modal_vllm.py
```

`modal deploy` prints the URL (`https://<workspace>--collusion-vllm-server.<region>.modal.direct`).
Put it in `.env`, followed by `/v1`, as `MODAL_VLLM_BASE_URL`. Then:

```bash
make check-model MODEL=configs/models/modal-vllm.yaml                    # ends with: result : ready
curl -s -o /dev/null -w "%{http_code}\n" https://<your URL>/v1/models    # must print 401
```

`401`: the key is enforced. `200`: the server is open, stop it now. `503`: still starting.

## Security

- "unauthenticated" in the deploy output is Modal's own login check, off on purpose: vLLM checks
  the key instead (the 401 above).
- The key reaches vLLM as an environment variable, never on its command line, because vLLM logs
  its arguments. In `modal app logs collusion-vllm`, the `non-default args` line must not show
  `api_key`.
- New key (leak, someone leaves, `.env` and Modal disagree): `make modal-setup`.

Never paste the key in a chat, an issue or a commit. More: [SECURITY.md](../../SECURITY.md).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Please add a payment method to use L40S GPU functions` | add a card to your Modal account |
| `HTTP 503 … no upstreams available` | the server is starting: wait (runs wait up to 20 minutes) |
| the check fails after 20 minutes | `modal app logs collusion-vllm`; out of memory: lower `MAX_MODEL_LEN` or use a bigger GPU |
| `HTTP 401` from `make check-model` | `.env` and Modal have different keys: `make modal-setup` |
| `curl` prints `200` | `modal app stop collusion-vllm`, then check the deploy file and logs |
| turns without tool calls | wrong `TOOL_PARSER`: redeploy with the right one |
| `modal: command not found` | `uv tool update-shell`, then open a new terminal |
| `MODAL_VLLM_BASE_URL is not set` | `make modal-setup` |

## Files

| File | Role |
|---|---|
| `deploy/modal_vllm.py` | the Modal app: image, GPU, caches, vLLM command, download step |
| `deploy/models/*.env` | one file per model: server settings and the model file runs use |
| `scripts/modal_profile.sh` | picks the model for `make modal-run` (name or menu) |
| `configs/models/modal-vllm.yaml` | how runs call Qwen3-8B: URL and key from `.env`, thinking off |
| `configs/models/modal-vllm-thinking.yaml` | the same server, thinking on |
| `configs/models/modal-deepseek-v4-pro.yaml` | how runs call DeepSeek V4 Pro, thinking off |
| `configs/studies/modal_paper.yaml` | the `local_paper` boards on this model |
