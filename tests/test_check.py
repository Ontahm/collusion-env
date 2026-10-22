"""Tests for agents/check.py and the HTTP client, against a stand-in OpenAI-compatible server."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from agents import check


def serve(reply_message):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, body):
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self._send({"data": [{"id": "fake-model"}]})

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert request["tools"][0]["function"]["name"] == "assign_task"
            self._send({"choices": [{"message": reply_message}], "usage": {"prompt_tokens": 50, "completion_tokens": 5}})

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def model_file(tmp_path, port):
    path = tmp_path / "model.yaml"
    path.write_text(f"label: fake\nbase_url: http://127.0.0.1:{port}/v1\nmodel: fake-model\napi_key_env: null\nmax_retries: 0\n")
    return str(path)


def test_ready_when_the_model_calls_the_tool(tmp_path, capsys):
    server = serve({"role": "assistant", "content": None, "tool_calls": [
        {"id": "1", "type": "function", "function": {"name": "assign_task", "arguments": json.dumps({"task_id": "ISSUE-0001::review"})}}]})
    try:
        assert check.main([model_file(tmp_path, server.server_port)]) == 0
    finally:
        server.shutdown()
    out = capsys.readouterr().out
    assert "server serves fake-model" in out and "result     : ready" in out


def test_not_ready_when_the_model_answers_in_text(tmp_path, capsys):
    server = serve({"role": "assistant", "content": "I would take the review task."})
    try:
        assert check.main([model_file(tmp_path, server.server_port)]) == 1
    finally:
        server.shutdown()
    assert "no tool call" in capsys.readouterr().out


def test_unreachable_server(tmp_path, capsys):
    assert check.main([model_file(tmp_path, 9)]) == 1
    assert "cannot reach" in capsys.readouterr().out
