# deploy/

Optional: hosting open-weight models outside your machine. Nothing here is imported by the
environment.

## Open models on Modal (`modal_vllm.py`)

One-time setup on the machine that deploys:

```bash
pip install modal            # or: uv tool install modal
modal setup                  # log in to Modal
modal secret create collusion-vllm VLLM_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

Deploy (defaults: Qwen/Qwen3-8B on one L40S; see the file's header for every setting):

```bash
modal deploy deploy/modal_vllm.py
# other model, e.g.:
MODEL=meta-llama/Llama-3.3-70B-Instruct TOOL_PARSER=llama3_json REASONING_PARSER= GPU=H100:2 \
  modal deploy deploy/modal_vllm.py
```

Then:

1. Put the printed URL + `/v1` as `base_url` in `configs/models/modal-vllm.yaml`, and the served name
   as `model`.
2. Put the same key in `.env`: `MODAL_VLLM_API_KEY=...` (the value given to `modal secret create`).
3. Check it answers: `curl -H "Authorization: Bearer $MODAL_VLLM_API_KEY" <base_url>/models`.
4. Add `configs/models/modal-vllm.yaml` to a study's `models:` list and run as usual.

Notes:

- [!] Written from Modal's vLLM example (October 2026) and not deployed from the build sandbox; the
  `secrets=` argument of `@app.server` is the one detail the example does not show. If the first
  deploy rejects it, see Modal's documentation for passing a secret to a server.

- The first request after an idle period starts a GPU and loads the model (minutes). Later ones are fast.
- Pin `MODEL_REVISION` to a commit for any run you report, and record it in your notes.
- Tool calling needs the parser of the model family (`hermes` for Qwen, `llama3_json` for Llama 3.x;
  vLLM's documentation lists the others). A wrong parser shows up as turns without any tool call
  in the health metrics.
- Costs: Modal bills GPU time while the server is up (it scales to zero after 15 idle minutes).
