"""LLM agents through any OpenAI-compatible chat-completions endpoint (API or local server).

Spec: spec/10-models.md, spec/05-protocol.md 5.1.

The turn loop is Colosseum's (`terrarium: agents/base.py::_multi_step_response_generation` with the
chat-style client `llm_server/clients/vllm_client.py`): the conversation starts with the system and
user prompts; after each model response, every tool call in it is executed and its result appended
as a `tool` message containing `json.dumps(result)`; the turn ends when an environment tool commits
(a claim or a reservation) or after `calls_per_turn` model calls.

One deliberate difference: the assistant message is appended with its standard fields only (role,
content, tool_calls), because some APIs reject extra fields (for example a local server's
`reasoning_content`). Those fields are kept in the call log.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional

import httpx

from env.game import Turn

RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
FATAL_STATUS = {401, 403, 404}          # wrong key, no access, unknown model or URL: every call would fail


class FatalModelError(RuntimeError):
    """The endpoint refuses every request (key, access, model name or URL): stop using this model."""


class ModelUnavailable(RuntimeError):
    """A call still failed after every retry (server stopped, spending limit, outage) and the model's
    `stop_on_error` is set: the episode stops, keeping its finished rounds, instead of letting the
    environment fill the missing claim at random."""


@dataclass(frozen=True)
class ModelConfig:
    label: str = "gpt-4.1-mini"
    provider: str = "openai_compatible"        # openai_compatible | scripted
    base_url: str = "https://api.openai.com/v1"
    base_url_env: Optional[str] = None         # environment variable (e.g. in .env) that overrides base_url: one
                                               # model file for everyone, each person's own server URL
    model: str = "gpt-4.1-mini-2025-04-14"
    api_key_env: Optional[str] = "OPENAI_API_KEY"   # name of the environment variable holding the key
    temperature: Optional[float] = 0.7         # Colosseum's paper config
    max_tokens: Optional[int] = 1500           # Colosseum's paper config
    max_tokens_field: str = "max_tokens"       # some APIs want "max_completion_tokens"
    send_seed: bool = False                    # send a per-call seed (local servers honour it)
    extra_body: Mapping[str, Any] = field(default_factory=dict)   # merged into every request
    timeout_s: float = 300.0
    max_retries: int = 6
    startup_wait_s: float = 0.0                # wait this long for a server that is starting (scale-to-zero hosts)
    price_input_per_1m: Optional[float] = None     # USD per million tokens, for cost estimates
    price_output_per_1m: Optional[float] = None
    policy: str = "greedy"                     # scripted agents only (agents/scripted.py)
    api: str = "chat"                          # chat (POST /chat/completions) | responses (POST /responses, OpenAI)
    stop_on_error: bool = False                # a call that fails after all retries stops the episode (finished
                                               # rounds kept) instead of a random fill of the agent's claim
    reasoning_summary: Optional[str] = None    # responses only: ask for the model's reasoning summary
                                               # (auto | concise | detailed); logged as the message's "reasoning"


class ChatClient:
    """Minimal async client for POST {base_url}/chat/completions."""

    def __init__(self, config: ModelConfig, on_retry: Optional[Callable[[int, str, float], None]] = None):
        self.config = config
        self.on_retry = on_retry or (lambda attempt, error, delay: None)
        if config.base_url_env and not os.environ.get(config.base_url_env):
            raise RuntimeError(f"model {config.label!r}: environment variable {config.base_url_env} is not set: put your "
                               "server's URL in .env (for Modal: make modal-setup does it)")
        key = os.environ.get(config.api_key_env) if config.api_key_env else None
        if config.api_key_env and not key:
            raise RuntimeError(f"model {config.label!r}: environment variable {config.api_key_env} is not set "
                               "(put it in .env or export it)")
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        self.http = httpx.AsyncClient(base_url=config.base_url.rstrip("/"), headers=headers,
                                      timeout=config.timeout_s)

    async def close(self) -> None:
        await self.http.aclose()

    async def wait_until_ready(self, on_wait: Optional[Callable[[float], None]] = None,
                               poll_s: float = 10.0) -> Optional[str]:
        """Poll GET /models while the server is starting (502/503/504 or no connection), for up to
        `startup_wait_s`. A host that scales to zero (Modal) refuses requests until the model is
        loaded, which takes minutes after an idle period. Returns None once the server answers with
        anything else (even an error: it is up), or the last problem when the wait runs out."""
        deadline = time.time() + self.config.startup_wait_s
        started = time.time()
        while True:
            try:
                r = await self.http.get("/models", timeout=30)
                if r.status_code not in (502, 503, 504):
                    return None
                problem = f"HTTP {r.status_code}: {r.text[:200]}"
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                problem = f"{type(exc).__name__}: {exc}"
            if time.time() + poll_s > deadline:
                return problem
            if on_wait:
                on_wait(time.time() - started)
            await asyncio.sleep(poll_s)

    async def complete(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]],
                       seed: Optional[int] = None) -> Dict[str, Any]:
        cfg = self.config
        if cfg.api == "responses":
            payload, path = responses_payload(cfg, messages, tools), "/responses"
        else:
            payload, path = self._chat_payload(messages, tools, seed), "/chat/completions"
        delay = 2.0
        last_error = None
        for attempt in range(cfg.max_retries + 1):
            started = time.time()
            wait = None
            try:
                response = await self.http.post(path, json=payload)
                elapsed = time.time() - started
                if response.status_code == 200:
                    try:
                        body = response.json()
                    except ValueError:                  # a proxy or a crashed server answering 200 with non-JSON
                        last_error = f"HTTP 200 with a body that is not JSON: {response.text[:200]}"
                    else:
                        out = {"request": payload, "response": body, "seconds": elapsed, "attempts": attempt + 1}
                        if cfg.api == "responses":      # the agent loop reads the chat shape; the raw answer is logged too
                            out.update(response=responses_as_chat(body), raw_response=body)
                        return out
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:500]}"
                    if response.status_code in FATAL_STATUS:
                        raise FatalModelError(f"model {cfg.label!r} at {cfg.base_url}: {last_error}")
                    if response.status_code not in RETRY_STATUS:
                        break
                    wait = _retry_after(response.headers.get("retry-after"))
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            if attempt < cfg.max_retries:
                pause = min(wait if wait is not None else delay, 120.0)
                self.on_retry(attempt + 1, last_error or "", pause)
                await asyncio.sleep(pause)
                delay *= 2
        return {"request": payload, "error": last_error, "attempts": attempt + 1}

    def _chat_payload(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]],
                      seed: Optional[int]) -> Dict[str, Any]:
        cfg = self.config
        payload: Dict[str, Any] = {"model": cfg.model, "messages": messages}
        if tools:
            payload["tools"] = tools
        if cfg.temperature is not None:
            payload["temperature"] = cfg.temperature
        if cfg.max_tokens is not None:
            payload[cfg.max_tokens_field] = cfg.max_tokens
        if seed is not None:
            payload["seed"] = seed
        payload.update(dict(cfg.extra_body))
        return payload


def responses_payload(cfg: ModelConfig, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The same request for OpenAI's Responses API: chat messages become input items (an assistant's
    tool calls become function_call items, tool results function_call_output items) and chat tools
    become flat function tools. Stateless (store: false), like the chat calls: the reasoning items of
    an earlier call in the same turn are not sent back."""
    items: List[Dict[str, Any]] = []
    for m in messages:
        if m["role"] == "tool":
            items.append({"type": "function_call_output", "call_id": m.get("tool_call_id"), "output": m.get("content") or ""})
            continue
        if m.get("content"):
            items.append({"role": m["role"], "content": m["content"]})
        for call in m.get("tool_calls") or []:
            fn = call.get("function") or {}
            items.append({"type": "function_call", "call_id": call.get("id"), "name": fn.get("name"),
                          "arguments": fn.get("arguments") or "{}"})
    payload: Dict[str, Any] = {"model": cfg.model, "input": items, "store": False}
    if tools:
        payload["tools"] = [{"type": "function", **t["function"]} if "function" in t else t for t in tools]
    if cfg.temperature is not None:
        payload["temperature"] = cfg.temperature
    if cfg.max_tokens is not None:
        payload["max_output_tokens"] = cfg.max_tokens
    if cfg.reasoning_summary:
        payload["reasoning"] = {"summary": cfg.reasoning_summary}
    payload.update(dict(cfg.extra_body))
    return payload


def responses_as_chat(body: Dict[str, Any]) -> Dict[str, Any]:
    """A Responses API answer in the chat-completions shape the agent loop reads: output text as content,
    function_call items as tool_calls, reasoning summaries joined as message["reasoning"]."""
    text, calls, summary = [], [], []
    for item in body.get("output") or []:
        if item.get("type") == "message":
            text += [c.get("text", "") for c in item.get("content") or [] if c.get("type") == "output_text"]
        elif item.get("type") == "function_call":
            calls.append({"id": item.get("call_id"), "type": "function",
                          "function": {"name": item.get("name"), "arguments": item.get("arguments") or "{}"}})
        elif item.get("type") == "reasoning":
            summary += [s.get("text", "") for s in item.get("summary") or []]
    message: Dict[str, Any] = {"role": "assistant", "content": "\n".join(text) or None,
                               "reasoning": "\n\n".join(summary) or None}
    if calls:
        message["tool_calls"] = calls
    usage = body.get("usage") or {}
    finish = "tool_calls" if calls else ("length" if body.get("status") == "incomplete" else "stop")
    return {"choices": [{"message": message, "finish_reason": finish}],
            "usage": {"prompt_tokens": usage.get("input_tokens", 0), "completion_tokens": usage.get("output_tokens", 0),
                      "completion_tokens_details": {"reasoning_tokens":
                                                    (usage.get("output_tokens_details") or {}).get("reasoning_tokens", 0)}}}


def _retry_after(value: Optional[str]) -> Optional[float]:
    """Seconds from a Retry-After header (numeric form only)."""
    try:
        return max(0.0, float(value)) if value is not None else None
    except ValueError:
        return None


def call_seed(salt: str, agent: str, where: str) -> int:
    """A per-call seed fixed by where the call happens (episode salt, agent, round, turn, call): unique
    within an episode, the same on a rerun."""
    digest = hashlib.sha256(f"{salt}:{agent}:{where}".encode()).hexdigest()
    return int(digest[:8], 16)


class LLMAgent:
    """One agent of one episode. Stateless between turns, as in Colosseum."""

    def __init__(self, name: str, client: ChatClient, log_call: Callable[[Dict[str, Any]], None],
                 seed_salt: str = ""):
        self.name = name
        self.client = client
        self.log_call = log_call
        self.seed_salt = seed_salt

    async def take_turn(self, turn: Turn) -> Dict[str, Any]:
        messages: List[Dict[str, Any]] = [{"role": "system", "content": turn.system},
                                          {"role": "user", "content": turn.user}]
        tool_log: List[Dict[str, Any]] = []
        steps: List[Dict[str, Any]] = []
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        model_calls = 0
        seconds = 0.0
        error = None
        for step in range(turn.calls_per_turn):
            where = f"{turn.meta.get('round', 0)}:{turn.meta.get('position', 0)}:{step}"
            seed = call_seed(self.seed_salt, self.name, where) if self.client.config.send_seed else None
            out = await self.client.complete(messages, turn.tools, seed)
            model_calls += 1
            seconds += out.get("seconds", 0.0)
            self.log_call({"agent": self.name, **turn.meta, "kind": turn.kind, "step": step, "seed": seed, **out})
            if "error" in out:
                error = out["error"]
                if self.client.config.stop_on_error:
                    raise ModelUnavailable(f"{self.name}: {error}")
                break
            choice = (out["response"].get("choices") or [{}])[0]
            message = choice.get("message") or {}
            call_usage = out["response"].get("usage") or {}
            for key in ("prompt_tokens", "completion_tokens"):
                usage[key] += int(call_usage.get(key) or 0)
            steps.append({"text": message.get("content"),
                          "reasoning": message.get("reasoning_content") or message.get("reasoning"),
                          "tool_calls": [(c.get("function") or {}).get("name") for c in message.get("tool_calls") or []],
                          "finish_reason": choice.get("finish_reason"), "seconds": out.get("seconds", 0.0),
                          "attempts": out.get("attempts", 1),
                          "prompt_tokens": int(call_usage.get("prompt_tokens") or 0),
                          "completion_tokens": int(call_usage.get("completion_tokens") or 0)})
            kept = {"role": "assistant", "content": message.get("content")}
            if message.get("tool_calls"):
                kept["tool_calls"] = message["tool_calls"]
            messages.append(kept)
            for call in message.get("tool_calls") or []:
                fn = call.get("function") or {}
                name = fn.get("name", "unknown_tool")
                try:
                    arguments = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                result = turn.execute(name, arguments)
                tool_log.append({"tool": name, "arguments": arguments, "result": result})
                messages.append({"role": "tool", "tool_call_id": call.get("id"), "name": name,
                                 "content": json.dumps(result)})
            if turn.committed:
                break
        return {"model_calls": model_calls, "tool_calls": tool_log, "usage": usage, "error": error,
                "seconds": seconds, "steps": steps,
                "final_text": messages[-1].get("content") if messages[-1].get("role") == "assistant" else None}
