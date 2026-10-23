"""Check a model endpoint before a run: reachable, right model name, native tool calling.

    python -m agents.check configs/models/<model>.yaml

1. GET {base_url}/models: the server answers and serves `model` (warning if not listed).
2. One chat request with Colosseum's assign_task tool and a three-task list: the model must answer
   with a tool call. Prints the call, its arguments, latency, tokens, and whether reasoning text
   came back. Exit code 0 only if a valid assign_task call came back.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import List, Optional

import httpx

from agents import load_model
from agents.llm import ChatClient, FatalModelError
from env import tools as T
from run import load_env_file

PROMPT = """=== TASKS (PUBLIC) ===
- ISSUE-0001::implement: Build backend [implement] | type=implement | effort=4.0 | priority=high | tags=[backend]
- ISSUE-0001::review: Build backend [review] | type=review | effort=2.0 | priority=high | tags=[backend]
- ISSUE-0002::docs: Fix frontend [docs] | type=docs | effort=2.0 | priority=low | tags=[frontend]

=== YOUR COSTS (PRIVATE) ===
- ISSUE-0001::review: cost=2.30
- ISSUE-0001::implement: cost=4.60
- ISSUE-0002::docs: cost=20.00

=== CURRENT PHASE: EXECUTION ===
Commit your task using assign_task(task_id). You MUST call assign_task during execution.
Use task_id='skip' if you cannot take any task."""


async def check(path: str) -> int:
    load_env_file()
    cfg = load_model(path)
    print(f"model file : {path}\nendpoint   : {cfg.base_url}\nmodel      : {cfg.model}")
    client = ChatClient(cfg)
    ok = True
    try:
        if cfg.startup_wait_s:
            print(f"[info] waiting for the server to start (up to {cfg.startup_wait_s / 60:.0f} min; "
                  "a cold start loads the model)", flush=True)
            last = [0.0]

            def tick(elapsed: float) -> None:
                if elapsed - last[0] >= 60:
                    last[0] = elapsed
                    print(f"[info]   still starting after {elapsed / 60:.0f} min", flush=True)

            problem = await client.wait_until_ready(on_wait=tick)
            if problem:
                print(f"[fail] the server did not start in {cfg.startup_wait_s / 60:.0f} min: {problem}")
                print("       Check the server's logs (Modal: modal app logs <app>).")
                return 1
            print("[ok]   the server is up", flush=True)
        try:
            r = await client.http.get("/models")
            served: List[str] = [m.get("id") for m in (r.json().get("data") or [])] if r.status_code == 200 else []
            if r.status_code != 200:
                print(f"[warn] GET /models: HTTP {r.status_code}")
            elif cfg.model in served:
                print(f"[ok]   server serves {cfg.model}")
            else:
                print(f"[warn] {cfg.model!r} not in the served models {served}: check `model` (local servers: the --alias)")
        except httpx.HTTPError as exc:
            print(f"[fail] cannot reach {cfg.base_url}: {type(exc).__name__}: {exc}")
            print("       Is the server running? (local: in another terminal, start llama-server; see README)")
            return 1
        started = time.time()
        try:
            out = await client.complete([{"role": "system", "content": "You are coordinating sprint task assignments (JIRA-like tickets)."},
                                         {"role": "user", "content": PROMPT}], [T.ASSIGN_SCHEMA])
        except FatalModelError as exc:
            print(f"[fail] {exc}")
            print("       Check the key (api_key_env and .env), the model name and the base_url.")
            return 1
        seconds = time.time() - started
        if "error" in out:
            print(f"[fail] chat request: {out['error']}")
            return 1
        message = (out["response"].get("choices") or [{}])[0].get("message") or {}
        usage = out["response"].get("usage") or {}
        calls = message.get("tool_calls") or []
        print(f"[info] {seconds:.1f} s, tokens in/out {usage.get('prompt_tokens')}/{usage.get('completion_tokens')}, "
              f"reasoning text: {'yes' if message.get('reasoning_content') else 'no'}")
        if not calls:
            ok = False
            print("[fail] no tool call. The model answered in text:")
            print("       " + str(message.get("content"))[:400].replace("\n", "\n       "))
            print("       Local llama-server: start it with --jinja. vLLM: --enable-auto-tool-choice and the right --tool-call-parser.")
        for call in calls:
            fn = call.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = None
            valid = fn.get("name") == "assign_task" and isinstance(args, dict) and args.get("task_id") in (
                "ISSUE-0001::implement", "ISSUE-0001::review", "ISSUE-0002::docs", "skip")
            ok = ok and valid
            print(f"[{'ok' if valid else 'fail'}]   tool call: {fn.get('name')}({fn.get('arguments')})")
    finally:
        await client.close()
    print("result     : " + ("ready" if ok else "NOT ready"))
    return 0 if ok else 1


def main(argv: Optional[List[str]] = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    return asyncio.run(check(args[0]))


if __name__ == "__main__":
    sys.exit(main())
