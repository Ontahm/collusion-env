"""A stand-in OpenAI-compatible server for tests: answers every chat request with a tool call for
the tool offered (claims and reservations: the first task listed in the prompt; posts: a short
message), plus reasoning text, and records the requests it received."""

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List


def start(status: int = 200) -> "tuple[HTTPServer, List[Dict[str, Any]]]":
    """`status` other than 200 makes every chat request fail with it (e.g. 401: wrong key)."""
    requests: List[Dict[str, Any]] = []

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
            self._send({"data": [{"id": "fake"}]})

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(req)
            if status != 200:
                data = json.dumps({"error": {"message": "refused"}}).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            tools = [t["function"]["name"] for t in req.get("tools", [])]
            user = next(m["content"] for m in req["messages"] if m["role"] == "user")
            task = re.search(r"^- (ISSUE-\d+::\w+):", user, re.M).group(1)
            done = any(m["role"] == "tool" for m in req["messages"])
            if "assign_task" in tools:
                name, args = "assign_task", {"task_id": task}
            elif "reserve_task" in tools:
                name, args = "reserve_task", {"task_id": task}
            elif "post_message" in tools and not done:
                name, args = "post_message", {"message": f"I will look at {task}.", "blackboard_id": 0}
            else:
                name = None
            message = {"role": "assistant", "content": "Done." if name is None else None,
                       "reasoning_content": f"My cheapest option seems to be {task}."}
            if name:
                message["tool_calls"] = [{"id": f"c{len(requests)}", "type": "function",
                                          "function": {"name": name, "arguments": json.dumps(args)}}]
            self._send({"choices": [{"message": message, "finish_reason": "tool_calls" if name else "stop"}],
                        "usage": {"prompt_tokens": 100, "completion_tokens": 10}})

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, requests
