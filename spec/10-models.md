# 10 — Models and how they are called

## 10.1 Colosseum [C][P]

- Agents are tool-calling LLMs, called through Terrarium clients: `openai`, `anthropic`, `gemini`,
  `together`, and `vllm` (any OpenAI-compatible server, local or remote).
- **Paper's Jira regret config** (`collusion_jira_complete_n6_c2_regret_models.yaml`):
  gpt-4.1-mini-2025-04-14, gpt-4o-mini, claude-sonnet-4-5, gemini-2.5-flash,
  moonshotai/Kimi-K2-Instruct-0905, moonshotai/Kimi-K2-Thinking (gpt-oss-120b and DeepSeek-V3.1 are
  commented out). Parameters: temperature 0.7, max_tokens 1500.
- **Topologies config**: Qwen/Qwen2.5-7B-Instruct through vLLM, temperature 0.4, max_tokens 1024.
- **One model per run** [P]: all agents of a run use the same model.

## 10.2 The team [T]

- Main model: gpt-4.1-mini ("Matches the paper, reliable, low cost").
- If time allows, one open-weight model: Llama 3.3 70B. [!] The team note says it "is already in
  the configs of Colosseum". It appears only commented out, in another experiment
  (`experiments/network_influence/configs/misinformation_prop_mass.yaml`:
  `meta-llama/Llama-3.3-70B-Instruct-Turbo` via Together), not in the collusion configs.

## 10.3 This study [Δ]

- **One interface for every model**: OpenAI-compatible chat completions with tool calling.
  - Local: a llama.cpp `llama-server` or vLLM on the machine.
  - API: OpenAI, Together, or any OpenAI-compatible provider.
  - Switching is a config change only: base URL, model name, and key (read from the environment,
    never from a committed file).
- **Parameters**: Colosseum's paper values unless decided otherwise: temperature 0.7, max_tokens
  1500. [Q-22]
- **Native tool calling** when the server supports it. The text-based format Terrarium adds for
  local models ([06](06-prompts.md)) is a fallback, to be avoided if possible, because it changes
  the prompt.
- **Reasoning text**: when a model returns it (thinking models), it is kept in the logs.
- **Determinism [!]**: API providers do not guarantee identical outputs for identical requests, even
  with a seed; a local server can. Replications are therefore independent draws, and everything is
  logged so that metrics can be recomputed without calling the model again.
- **Models for the weekend** ([Q-23], decided 23 Oct): gpt-4.1-mini through OpenAI's API (as the
  paper), local models through llama-server, and open-weight models hosted on Modal with vLLM
  (`deploy/modal_vllm.py`). All through the same OpenAI-compatible client; one file per model in
  `configs/models/`.
- **Local test models**: `configs/models/local-qwen3-4b.yaml` (thinking off), `-thinking`, `-abliterated`,
  served by `make local-server` (scripts/serve.sh, models in `models/`); `make check-model MODEL=<file>` checks an endpoint answers
  with tool calls before any run (`agents/check.py`).
- **Costs**: model files can carry prices; every round then records its cost (tokens x price) and
  summaries total it. gpt-4.1-mini: $0.40 / $1.60 per million input / output tokens, from
  third-party listings (Sep 2026) [!] check OpenAI's page.
- **Differences from Colosseum's clients**: Colosseum called gpt-4.1-mini through OpenAI's Responses
  API; we use chat completions (same texts, another request format). The assistant message is sent
  back with its standard fields only (some APIs reject others such as `reasoning_content`, which is
  kept in the logs). Colosseum's text-based tool instructions for local models are reproduced as
  prompt text (`prompts.text_tool_instructions`), but tool calls are always native.

## Remarks & suggestions

- **Tool-calling reliability differs by model.** Report the health metrics ([08](08-metrics.md))
  per model, to separate "cannot use the tools" from "does not collude".
- *Your remarks:*
