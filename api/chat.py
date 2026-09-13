import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from uuid import uuid4

# Add src to python path so we can import Codex's code
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from app import run_react_agent
from mcp_server import MCPHealthServer
from prompts import MAX_CONVERSATION_TURNS
from providers import MockOfflineProvider, get_llm_provider

SESSION_HISTORY = {}

def get_demo_provider():
    if os.getenv("WEB_DEMO_PROVIDER", "mock").lower() == "live":
        return get_llm_provider()
    return MockOfflineProvider()

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length > 8_000:
                self.send_error_json(HTTPStatus.BAD_REQUEST, "Tin nhắn quá dài cho demo local.")
                return
                
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            message = str(payload.get("message", "")).strip()
            if not message:
                self.send_error_json(HTTPStatus.BAD_REQUEST, "Vui lòng nhập câu hỏi.")
                return

            session_id = str(payload.get("session_id") or uuid4())
            history = SESSION_HISTORY.get(session_id, [])[-(MAX_CONVERSATION_TURNS * 2):]
            
            provider = get_demo_provider()
            mcp_server = MCPHealthServer()
            
            logs = run_react_agent(message, provider, mcp_server, history)
            answer = logs[-1].get("output", "Chưa thể tạo phản hồi an toàn.") if logs else ""
            
            history.extend([
                {"role": "user", "content": message},
                {"role": "assistant", "content": answer},
            ])
            SESSION_HISTORY[session_id] = history[-(MAX_CONVERSATION_TURNS * 2):]
            
            self.send_success_json({
                "session_id": session_id,
                "provider": provider.__class__.__name__,
                "answer": answer,
                "events": logs,
                "memory_turns": len(SESSION_HISTORY[session_id]) // 2,
            })
            
        except Exception:
            self.send_error_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "Demo chưa thể xử lý yêu cầu. Vui lòng thử lại.",
            )

    def send_success_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        
    def send_error_json(self, status, error_msg):
        body = json.dumps({"error": error_msg}, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
