"""Serve an open-weight model on Modal with vLLM, behind an OpenAI-compatible API.

Not part of the environment: it needs the `modal` package and a Modal account only on the machine
that deploys (`pip install modal`, then `modal setup`). The environment calls the result like any
API (configs/models/modal-vllm.yaml). Follows Modal's vLLM example (modal.com/docs/examples/vllm_inference).

    export MODEL=Qwen/Qwen3-8B TOOL_PARSER=hermes REASONING_PARSER=qwen3 GPU=L40S:1   # optional
    make modal-setup        # once per person: key, deploy, checks (Makefile)
    modal deploy deploy/modal_vllm.py

The deploy prints the URL, https://<workspace>--collusion-vllm-server.<region>.modal.direct ;
the base URL for the model config is that URL followed by /v1. Settings are read from the
environment when you deploy and baked into the image:

    MODEL             Hugging Face model id                       (default Qwen/Qwen3-8B)
    MODEL_REVISION    commit of that model, to pin it             (default: main, pin it for real runs)
    SERVED_NAME       name the API exposes                        (default: the model id)
    TOOL_PARSER       vLLM tool-call parser for that model family (default hermes: Qwen; llama3_json: Llama 3.x)
    REASONING_PARSER  vLLM reasoning parser, or empty             (default qwen3)
    GPU               Modal GPU spec                              (default L40S:1)
    MAX_MODEL_LEN     context length                              (default 16384)
    REGION            routing region                              (default us-east)

The endpoint requires the bearer key stored in the `collusion-vllm` Modal secret (read by vLLM from
the VLLM_API_KEY environment variable, so it never appears in the logged arguments);
put the same key in .env as MODAL_VLLM_API_KEY. The server scales to zero after 15 idle minutes.
"""

import os

import modal

MODEL = os.environ.get("MODEL", "Qwen/Qwen3-8B")
MODEL_REVISION = os.environ.get("MODEL_REVISION", "main")
SERVED_NAME = os.environ.get("SERVED_NAME", MODEL)
TOOL_PARSER = os.environ.get("TOOL_PARSER", "hermes")
REASONING_PARSER = os.environ.get("REASONING_PARSER", "qwen3")
GPU = os.environ.get("GPU", "L40S:1")
MAX_MODEL_LEN = os.environ.get("MAX_MODEL_LEN", "16384")
REGION = os.environ.get("REGION", "us-east")
PORT = 8000
MINUTES = 60

image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install("vllm==0.21.0")
    .env({"HF_XET_HIGH_PERFORMANCE": "1",
          "SERVE_MODEL": MODEL, "SERVE_REVISION": MODEL_REVISION, "SERVE_NAME": SERVED_NAME,
          "SERVE_TOOL_PARSER": TOOL_PARSER, "SERVE_REASONING_PARSER": REASONING_PARSER,
          "SERVE_MAX_MODEL_LEN": MAX_MODEL_LEN})
)
hf_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("vllm-cache", create_if_missing=True)
app = modal.App("collusion-vllm")


@app.server(
    image=image,
    gpu=GPU,
    scaledown_window=15 * MINUTES,
    startup_timeout=20 * MINUTES,
    volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
    secrets=[modal.Secret.from_name("collusion-vllm")],
    port=PORT,
    routing_region=REGION,
    target_concurrency=32,
    unauthenticated=True,            # reachable without Modal auth; vLLM checks the API key itself
)
class Server:
    @modal.enter()
    def start(self):
        import subprocess

        cmd = ["vllm", "serve", os.environ["SERVE_MODEL"],
               "--revision", os.environ["SERVE_REVISION"],
               "--served-model-name", os.environ["SERVE_NAME"],
               "--host", "0.0.0.0", "--port", str(PORT),
               "--max-model-len", os.environ["SERVE_MAX_MODEL_LEN"],
               "--enable-auto-tool-choice", "--tool-call-parser", os.environ["SERVE_TOOL_PARSER"]]
        if os.environ.get("SERVE_REASONING_PARSER"):
            cmd += ["--reasoning-parser", os.environ["SERVE_REASONING_PARSER"]]
        # The key reaches vLLM through the VLLM_API_KEY environment variable (the Modal secret), never
        # as --api-key: vLLM prints its command-line arguments, key included, to the logs.
        assert os.environ.get("VLLM_API_KEY"), "the collusion-vllm secret must define VLLM_API_KEY"
        print(*cmd)
        self.process = subprocess.Popen(cmd)

    @modal.exit()
    def stop(self):
        self.process.terminate()
