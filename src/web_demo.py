"""Local-only browser demo for the Day 03 Vinmec ReAct Agent lab.

This server intentionally uses the Offline Mock provider by default. Set
WEB_DEMO_PROVIDER=live in the server process only after configuring a valid
provider key in .env; keys are never sent to the browser.
"""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from uuid import uuid4

from app import run_react_agent
from mcp_server import MCPHealthServer
from prompts import MAX_CONVERSATION_TURNS
from providers import MockOfflineProvider, get_llm_provider

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
HOST = "127.0.0.1"
PORT = 8765
SESSION_HISTORY: dict[str, list[dict[str, str]]] = {}


def get_demo_provider():
    """Use mock by default so local UI works without quota or an API key."""
    if os.getenv("WEB_DEMO_PROVIDER", "mock").lower() == "live":
        return get_llm_provider()
    return MockOfflineProvider()


class DemoHandler(SimpleHTTPRequestHandler):
    """Serves the static UI and a minimal same-origin JSON chat endpoint."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        """Avoid printing prompts or responses in console logs."""
        print(f"[web-demo] {self.address_string()} {args[0]}")

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path != "/api/chat":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Không tìm thấy endpoint."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length > 8_000:
                raise ValueError("Tin nhắn quá dài cho demo local.")
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            message = str(payload.get("message", "")).strip()
            if not message:
                raise ValueError("Vui lòng nhập câu hỏi.")

            session_id = str(payload.get("session_id") or uuid4())
            history = SESSION_HISTORY.get(session_id, [])[-(MAX_CONVERSATION_TURNS * 2):]
            provider = get_demo_provider()
            logs = run_react_agent(message, provider, MCPHealthServer(), history)
            answer = logs[-1].get("output", "Chưa thể tạo phản hồi an toàn.") if logs else ""
            history.extend([
                {"role": "user", "content": message},
                {"role": "assistant", "content": answer},
            ])
            SESSION_HISTORY[session_id] = history[-(MAX_CONVERSATION_TURNS * 2):]
            self._send_json(HTTPStatus.OK, {
                "session_id": session_id,
                "provider": provider.__class__.__name__,
                "answer": answer,
                "events": logs,
                "memory_turns": len(SESSION_HISTORY[session_id]) // 2,
            })
        except (ValueError, json.JSONDecodeError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except Exception:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "Demo chưa thể xử lý yêu cầu. Vui lòng thử lại."},
            )


if __name__ == "__main__":
    print(f"Local demo: http://{HOST}:{PORT}")
    print("Provider mặc định: MockOfflineProvider (không dùng API key).")
    print("Nhấn Ctrl+C để dừng server.")
    ThreadingHTTPServer((HOST, PORT), DemoHandler).serve_forever()
