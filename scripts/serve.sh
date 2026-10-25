#!/usr/bin/env bash
# Start llama-server for local models, in the foreground (Ctrl+C stops it).
# Settings come from the environment (the Makefile passes them). The exact command, llama.cpp
# version and model checksum go to runs/_server/current.json; run.py copies them into every run's
# provenance, so each result records which server answered.
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL_FILE="${MODEL_FILE:-deploy/local-weights/Qwen3-4B-Q4_K_M.gguf}"
ALIAS="${ALIAS:-qwen3-4b-q4km}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8080}"
CTX="${CTX:-12288}"
NGL="${NGL:-99}"
SEED="${SEED:-42}"

[[ -f "$MODEL_FILE" ]] || { echo "Missing $MODEL_FILE: run 'make models' first." >&2; exit 1; }
command -v llama-server >/dev/null || { echo "llama-server not found (see docs/how-to/run-locally.md)." >&2; exit 1; }
if [[ "$HOST" != "127.0.0.1" && "$HOST" != "localhost" ]]; then
  echo "Refusing HOST=$HOST: the server has no authentication, keep it on 127.0.0.1." >&2
  exit 1
fi

model_sha=$(grep " $(basename "$MODEL_FILE")\$" deploy/local-weights/SHA256SUMS | cut -d' ' -f1 || true)
[[ -n "$model_sha" ]] || { echo "$(basename "$MODEL_FILE") is not listed in deploy/local-weights/SHA256SUMS." >&2; exit 1; }
echo "Checking the model's checksum..."
(cd models && echo "$model_sha  $(basename "$MODEL_FILE")" | sha256sum --check --quiet)

mkdir -p runs/_server
stamp=$(date -u +%Y%m%d-%H%M%S)
log="runs/_server/${stamp}.log"
# -np 1: one request at a time (studies with a local model use max_concurrency 1).
# --jinja: the model's chat template, needed for native tool calls.
# --reasoning-format deepseek: thinking text comes back separately (reasoning_content).
# Sampling flags are Qwen3's defaults; requests send their own temperature, so these only apply
# to requests that omit them.
cmd=(llama-server
  -m "$MODEL_FILE" --alias "$ALIAS"
  --host "$HOST" --port "$PORT"
  -ngl "$NGL" -c "$CTX" -np 1
  --jinja --reasoning-format deepseek
  --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0 --presence-penalty 1.5
  --seed "$SEED"
  --log-file "$log")

version=$(llama-server --version 2>&1 | head -n 3 || true)
python3 - "$stamp" "$log" "$MODEL_FILE" "$model_sha" "$ALIAS" "$version" "${cmd[@]}" > runs/_server/current.json <<'PY'
import json, sys
stamp, log, model, sha, alias, version, *cmd = sys.argv[1:]
print(json.dumps({"started_utc": stamp, "log_file": log, "model_file": model, "model_sha256": sha,
                  "alias": alias, "llama_server_version": version, "command": cmd}, indent=2))
PY

echo "Serving $MODEL_FILE as '$ALIAS' on http://$HOST:$PORT/v1  (log: $log)"
exec "${cmd[@]}"
