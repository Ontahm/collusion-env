# collusion-env commands. Run inside `nix develop` (or any shell with Python 3.11+ and uv).
.DEFAULT_GOAL := help
.PHONY: help setup test smoke models local-server local-server-abliterated check-model dry-run run summarize runs episode scenarios prompts board-study check-env

# Python with the libraries prebuilt wheels need on NixOS (empty elsewhere).
PY := LD_LIBRARY_PATH="$${ENV_PY_LD_LIBRARY_PATH:-}" uv run --locked python
STUDY ?= configs/studies/colosseum_paper.yaml
BOARD_STUDY ?= configs/board_study.yaml
MODEL ?= configs/models/local-qwen3-4b.yaml

# Local model server (scripts/serve.sh). The abliterated model: make local-server-abliterated.
MODEL_FILE ?= models/Qwen3-4B-Q4_K_M.gguf
ALIAS ?= qwen3-4b-q4km
PORT ?= 8080
CTX ?= 12288
QWEN_URL := https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/bc640142c66e1fdd12af0bd68f40445458f3869b/Qwen3-4B-Q4_K_M.gguf
ABLIT_URL := https://huggingface.co/Mungert/Qwen3-4B-abliterated-GGUF/resolve/56175aed285a884480f49bb18d2a1b0e05a7749f/Qwen3-4B-abliterated-q4_k_m.gguf
ARGS ?=
LOG ?=
LOG_ARG := $(if $(LOG),--log-level $(LOG),)

help: ## List commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-26s %s\n", $$1, $$2}'
	@echo "  variables: STUDY=$(STUDY)  MODEL=$(MODEL)  RUN=<run dir>  LOG=<level>  ARGS='<extra options>'"

# On NixOS, numpy/scipy wheels need the libraries `nix develop` puts in ENV_PY_LD_LIBRARY_PATH.
check-env:
	@if [ -e /etc/NIXOS ] && [ -z "$${ENV_PY_LD_LIBRARY_PATH:-}" ]; then \
	  echo "ENV_PY_LD_LIBRARY_PATH is empty: this shell predates the flake. Run 'exit', then 'nix develop'."; exit 1; fi

setup: hooks ## Create .venv with the locked dependencies (and install the git hooks)
	uv sync --locked

.PHONY: hooks check-secrets
hooks: ## Install the git hooks: refuse commits that contain secrets (scripts/check_secrets.py)
	git config core.hooksPath .githooks
	@echo "git hooks installed (.githooks/): commits are checked for secrets"

check-secrets: ## Check every tracked file for secrets (API keys, tokens, .env values)
	python3 scripts/check_secrets.py

test: check-env ## Run all tests (no model, no network)
	$(PY) -m pytest

smoke: check-env ## Free end-to-end run with scripted agents (configs/studies/smoke_scripted.yaml)
	$(PY) -m run configs/studies/smoke_scripted.yaml $(LOG_ARG) $(ARGS)

models: ## Download the local models (pinned revisions, 2.5 GB each) and check their SHA-256
	@mkdir -p models
	@for pair in "Qwen3-4B-Q4_K_M.gguf $(QWEN_URL)" "Qwen3-4B-abliterated-q4_k_m.gguf $(ABLIT_URL)"; do \
	  set -- $$pair; \
	  if [ ! -f "models/$$1" ]; then echo "downloading $$1"; \
	    curl -L --fail --continue-at - -o "models/$$1.part" "$$2" && mv "models/$$1.part" "models/$$1"; fi; \
	done
	cd models && sha256sum --check SHA256SUMS

local-server: ## Serve a local model on http://127.0.0.1:8080 (Ctrl+C stops). MODEL_FILE=, ALIAS=, PORT=, CTX=
	@export MODEL_FILE="$(MODEL_FILE)" ALIAS="$(ALIAS)" PORT="$(PORT)" CTX="$(CTX)"; \
	if command -v llama-server >/dev/null; then exec scripts/serve.sh; \
	elif command -v nix >/dev/null; then exec nix develop .#server --command scripts/serve.sh; \
	else echo "llama-server not found: install llama.cpp (README, section 5)"; exit 1; fi

local-server-abliterated: ## Serve the abliterated Qwen3-4B (name qwen3-4b-ablit-q4km)
	@$(MAKE) --no-print-directory local-server MODEL_FILE=models/Qwen3-4B-abliterated-q4_k_m.gguf ALIAS=qwen3-4b-ablit-q4km

check-model: check-env ## Check a model endpoint answers with tool calls (MODEL=configs/models/<file>.yaml)
	$(PY) -m agents.check $(MODEL)

dry-run: check-env ## Show what STUDY would run (episodes, turns, maximum model calls)
	$(PY) -m run $(STUDY) --dry-run $(ARGS)

run: check-env ## Run STUDY (LOG=quiet|normal|verbose|debug; asks before calling a remote model, ARGS=--yes to skip)
	$(PY) -m run $(STUDY) $(LOG_ARG) $(ARGS)

summarize: check-env ## Summarise a run: make summarize RUN=runs/<run dir>
	$(PY) -m analysis.summarize $(RUN)

runs: check-env ## List the runs (SC=<scenario>: every run of one scenario, with its results; ARGS='-v', '--grep modal')
	$(PY) -m analysis.runs $(if $(SC),--scenario $(SC),) $(ARGS)

episode: check-env ## Read one game as a story: make episode RUN=runs/<run> SC=<scenario> SEED=<k> (or COND=; without them: list the games)
	$(PY) -m analysis.episode $(RUN) $(if $(SC),--scenario $(SC),) $(if $(COND),--cond $(COND),) $(if $(SEED),--seed $(SEED),) $(ARGS)

scenarios: check-env ## The scenario table (configs/scenarios.yaml): print it and regenerate SCENARIOS.md
	$(PY) -m scenarios

prompts: check-env ## The exact prompts of a scenario, on a sample board: make prompts SC=HV-2 [SEED=3]
	$(PY) -m scenarios --prompts $(SC) $(if $(SEED),--seed $(SEED),)

board-study: check-env ## Model-free board study (BOARD_STUDY=configs/board_study.yaml)
	$(PY) -m analysis.board_study $(BOARD_STUDY) $(ARGS)
