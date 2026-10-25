"""The Responses API path of agents/llm.py: request and answer translation (no network)."""
from agents import load_model
from agents.llm import responses_as_chat, responses_payload

TOOLS = [{"type": "function", "function": {"name": "assign_task", "description": "claim",
                                           "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}}}}}]


def test_model_file_uses_responses_with_summaries():
    cfg = load_model("configs/models/gpt-5-mini-summaries.yaml")
    assert (cfg.api, cfg.reasoning_summary, cfg.model) == ("responses", "detailed", "gpt-5-mini-2025-08-07")


def test_payload_translates_messages_and_tools():
    cfg = load_model("configs/models/gpt-5-mini-summaries.yaml")
    messages = [{"role": "system", "content": "S"}, {"role": "user", "content": "U"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "get_state", "arguments": "{}"}}]},
                {"role": "tool", "tool_call_id": "c1", "name": "get_state", "content": "{\"ok\": true}"}]
    p = responses_payload(cfg, messages, TOOLS)
    assert p["input"] == [{"role": "system", "content": "S"}, {"role": "user", "content": "U"},
                          {"type": "function_call", "call_id": "c1", "name": "get_state", "arguments": "{}"},
                          {"type": "function_call_output", "call_id": "c1", "output": "{\"ok\": true}"}]
    assert p["tools"][0]["name"] == "assign_task" and "function" not in p["tools"][0]
    assert p["reasoning"] == {"summary": "detailed"} and p["max_output_tokens"] == 8000 and p["store"] is False
    assert "temperature" not in p and "messages" not in p


def test_answer_becomes_chat_shape_with_reasoning():
    body = {"status": "completed", "output": [
        {"type": "reasoning", "summary": [{"type": "summary_text", "text": "I block the decoy."}]},
        {"type": "function_call", "call_id": "c9", "name": "assign_task", "arguments": "{\"task_id\": \"X\"}"}],
        "usage": {"input_tokens": 10, "output_tokens": 20, "output_tokens_details": {"reasoning_tokens": 15}}}
    out = responses_as_chat(body)
    msg = out["choices"][0]["message"]
    assert msg["reasoning"] == "I block the decoy." and msg["content"] is None
    assert msg["tool_calls"][0] == {"id": "c9", "type": "function",
                                    "function": {"name": "assign_task", "arguments": "{\"task_id\": \"X\"}"}}
    assert out["choices"][0]["finish_reason"] == "tool_calls"
    assert out["usage"]["prompt_tokens"] == 10 and out["usage"]["completion_tokens"] == 20
