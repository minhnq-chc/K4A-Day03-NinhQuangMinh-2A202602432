"""
🚀 CORE AGENT APPLICATION (DAY 03: CHATBOT VS REACT AGENT)
Thực thi so sánh giữa Chatbot Baseline (Cấp 2) và ReAct Agent kết nối MCP Server (Cấp 3).
"""

import json
import os
import sys
import time
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from mcp_server import MCPHealthServer
from prompts import (
    CHATBOT_BASELINE_PROMPT,
    REACT_AGENT_SYSTEM_PROMPT,
    MAX_ITERATIONS,
    MAX_CONVERSATION_TURNS
)
from providers import get_llm_provider

load_dotenv()

# Gemini Free Tier trong project của lab giới hạn 5 request/phút. 13 giây tạo
# khoảng đệm nhỏ hơn giới hạn đó khi chạy batch --all, còn interactive không bị
# làm chậm để người dùng chủ động điều tiết nhịp hội thoại.
GEMINI_FREE_TIER_INTERVAL_SECONDS = 13


class RequestPacer:
    """Giãn nhịp request trong test suite để không làm sai bằng chứng live API."""
    def __init__(self, interval_seconds: float = 0.0):
        self.interval_seconds = interval_seconds
        self._next_request_at = 0.0

    def wait_before_request(self):
        if self.interval_seconds <= 0:
            return
        wait_seconds = self._next_request_at - time.monotonic()
        if wait_seconds > 0:
            print(f"⏳ [Rate Limit Guard]: Chờ {wait_seconds:.1f}s trước live API request tiếp theo.")
            time.sleep(wait_seconds)
        self._next_request_at = time.monotonic() + self.interval_seconds

def load_test_cases():
    """Tải danh sách 5 test cases từ config/test_cases.json hoặc config/test_cases.example.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")
    if not os.path.exists(config_path):
        example_path = os.path.join(base_dir, "config", "test_cases.example.json")
        if os.path.exists(example_path):
            print("⚠️ [CONFIG NOTICE]: Chưa thấy file 'config/test_cases.json'. Đang dùng mẫu 'config/test_cases.example.json'.")
            print("👉 Hãy chạy: copy config/test_cases.example.json config/test_cases.json và viết test cases theo đề tài của bạn!\n")
            config_path = example_path
        else:
            config_path = "test_cases.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_waterfall_trace(trace_data: list):
    """Ghi vết log Waterfall Trace Log ra file docs/trace_waterfall.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(base_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    trace_path = os.path.join(docs_dir, "trace_waterfall.json")
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(trace_data, f, ensure_ascii=False, indent=2)
    print(f"📊 [OBSERVABILITY]: Đã lưu {len(trace_data)} sự kiện Waterfall Trace tại '{trace_path}'!")


def run_baseline_chatbot(user_query: str, provider):
    """Chạy Chatbot gốc (Cấp 2) không có công cụ gọi Tool"""
    print(f"\n💬 [CHATBOT BASELINE] Câu hỏi: {user_query}")
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT)
    print(f"🤖 Chatbot phản hồi:\n{response}")


def _has_emergency_signal(user_query: str) -> bool:
    """Guardrail minh bạch cho lab, không phải logic sàng lọc lâm sàng triển khai thực tế."""
    normalized = user_query.lower()
    emergency_phrases = ["đau ngực dữ dội", "khó thở", "ngất"]
    return sum(phrase in normalized for phrase in emergency_phrases) >= 2


def _is_scope_only_query(user_query: str) -> bool:
    """Câu hỏi chỉ về phạm vi hỗ trợ phải trả lời trực tiếp, không gọi tool."""
    normalized = user_query.lower()
    scope_markers = ["hỗ trợ những gì", "hỗ trợ gì", "phạm vi hỗ trợ"]
    return any(marker in normalized for marker in scope_markers)


def run_react_agent(
    user_query: str,
    provider,
    mcp_server: MCPHealthServer,
    conversation_history: list[dict[str, str]] | None = None,
    request_pacer: RequestPacer | None = None
) -> list:
    """
    [REACT AGENT LOOP] Thực thi vòng lặp Thought -> Action -> Observation với MCP Server
    Trả về danh sách trace log của phiên thực thi.
    """
    print(f"\n🤖 [REACT AGENT] Câu hỏi: {user_query}")
    
    trace_logs = []
    # Không gửi function declarations cho câu hỏi phạm vi; đây là policy routing
    # minh bạch để TC01 không phát sinh tool call không cần thiết.
    tools_list = [] if _is_scope_only_query(user_query) else mcp_server.list_tools()
    session_context = (conversation_history or [])[-(MAX_CONVERSATION_TURNS * 2):]

    if _has_emergency_signal(user_query):
        final_content = (
            "Tôi không thể đánh giá hoặc chẩn đoán tình trạng này. Các tín hiệu được mô tả có thể cần được "
            "đánh giá khẩn; hãy liên hệ dịch vụ cấp cứu hoặc đến cơ sở y tế ngay. Tôi không tiếp tục luồng tra lịch/đặt lịch."
        )
        print("🛡️ [Safety Routing]: Guardrail khẩn cấp được kích hoạt.")
        print(f"🏁 [Final Answer]: {final_content}")
        return [{
            "step": 1,
            "query": user_query,
            "provider": provider.__class__.__name__,
            "action_type": "SAFETY_ROUTING",
            "thought": "Tín hiệu khẩn cấp theo guardrail lab; dừng tool calling và chuyển hướng an toàn.",
            "output": final_content,
            "latency_ms": 0.0
        }]

    observations = []
    for step in range(1, MAX_ITERATIONS + 1):
        step_start_time = time.time()
        print(f"\n--- 🔄 Vòng lặp ReAct Loop (Step {step}/{MAX_ITERATIONS}) ---")

        if request_pacer:
            request_pacer.wait_before_request()
        llm_response = provider.generate_with_tools(
            user_query,
            tools_list,
            system_prompt=REACT_AGENT_SYSTEM_PROMPT,
            observations=observations,
            conversation_history=session_context
        )
        latency_ms = round((time.time() - step_start_time) * 1000, 2)
        
        thought = llm_response.get("thought", "Đang suy luận...")
        print(f"🧠 [Thought]: {thought}")

        if llm_response.get("type") == "provider_error":
            error_content = llm_response.get("content", "Live provider không trả được phản hồi.")
            print(f"⛔ [Provider Error]: {error_content}")
            trace_logs.append({
                "step": step,
                "query": user_query,
                "provider": provider.__class__.__name__,
                "action_type": "PROVIDER_ERROR",
                "thought": thought,
                "output": error_content,
                "latency_ms": latency_ms
            })
            return trace_logs
        
        # Trường hợp 1: LLM quyết định trả lời bằng văn bản trực tiếp
        if llm_response.get("type") == "text":
            final_content = llm_response.get("content", "")
            print(f"🏁 [Final Answer]: {final_content}")
            trace_logs.append({
                "step": step,
                "query": user_query,
                "provider": provider.__class__.__name__,
                "action_type": "FINAL_ANSWER",
                "thought": thought,
                "output": final_content,
                "latency_ms": latency_ms
            })
            return trace_logs

        elif llm_response.get("type") == "tool_call":
            tool_name = llm_response.get("tool_name")
            arguments = llm_response.get("arguments", {})
            
            print(f"🛠️ [Action Proposed]: {tool_name}({arguments})")
            
            # Thực thi Tool qua MCP Server
            mcp_result = mcp_server.call_tool(tool_name, arguments)
            obs_data = mcp_result.get("result", {
                "status": "MCP_ERROR",
                "message": "MCP Server không trả observation hợp lệ."
            })
            print(f"👁️ [Observation từ MCP Server]: {json.dumps(obs_data, ensure_ascii=False)}")
            
            trace_logs.append({
                "step": step,
                "query": user_query,
                "provider": provider.__class__.__name__,
                "action_type": "TOOL_EXECUTION",
                "tool_name": tool_name,
                "arguments": arguments,
                "observation": obs_data,
                "latency_ms": latency_ms
            })
            
            observations.append({"tool_name": tool_name, "result": obs_data})
            continue

        trace_logs.append({
            "step": step,
            "query": user_query,
            "provider": provider.__class__.__name__,
            "action_type": "FINAL_ANSWER",
            "thought": "Provider trả về định dạng không hỗ trợ.",
            "output": "Chưa thể xử lý phản hồi của model một cách an toàn.",
            "latency_ms": latency_ms
        })
        return trace_logs

    trace_logs.append({
        "step": MAX_ITERATIONS,
        "query": user_query,
        "provider": provider.__class__.__name__,
        "action_type": "FINAL_ANSWER",
        "thought": "Đạt giới hạn số vòng lặp để tránh lặp vô hạn.",
        "output": "Chưa thể hoàn tất yêu cầu trong giới hạn vòng lặp; vui lòng xác nhận lại lựa chọn hoặc liên hệ cơ sở y tế.",
        "latency_ms": 0.0
    })
    return trace_logs


if __name__ == "__main__":
    print("==========================================================")
    print("🏫 VINUNI AI COURSE - DAY 03 LAB: CHATBOT VS REACT AGENT")
    print("==========================================================")
    
    provider = get_llm_provider()
    mcp_server = MCPHealthServer()
    
    print(f"🔌 LLM Provider: {provider.__class__.__name__}")
    print(f"🌐 MCP Server: {mcp_server.server_name}\n")
    
    tests = load_test_cases()
    print(f"✅ Đã tải thành công {len(tests)} Test Cases thử nghiệm.\n")
    
    if "--interactive" in sys.argv:
        print("🎮 [INTERACTIVE MODE] Trò chuyện trực tiếp với ReAct Agent Vinmec mô phỏng:")
        print(f"🧠 Context window: tối đa {MAX_CONVERSATION_TURNS} lượt gần nhất, chỉ lưu trong RAM của phiên hiện tại.")
        print("💡 Gợi ý câu hỏi thử nghiệm:")
        print("   - Phạm vi: 'Trợ lý có dùng nguồn nào và hỗ trợ gì?'")
        print("   - Tra lịch: 'Tôi muốn khám Da liễu tại Vinmec ngày 20/09/2026'")
        print("   - Đặt lịch: dùng TC03 trong config/test_cases.json")
        print("   - Gõ 'exit' hoặc 'quit' để kết thúc phiên trò chuyện.\n")
        conversation_history = []
        while True:
            try:
                user_input = input("👤 Người dùng hỏi: ").strip()
                if not user_input or user_input.lower() in ["exit", "quit"]:
                    print("👋 Tạm biệt! Kết thúc phiên trò chuyện.")
                    break
                logs = run_react_agent(
                    user_input, provider, mcp_server, conversation_history=conversation_history
                )
                final_output = logs[-1].get("output", "") if logs else ""
                conversation_history.extend([
                    {"role": "user", "content": user_input},
                    {"role": "assistant", "content": final_output}
                ])
                conversation_history = conversation_history[-(MAX_CONVERSATION_TURNS * 2):]
                save_waterfall_trace(logs)
            except (KeyboardInterrupt, EOFError):
                print("\n👋 Đã thoát phiên tương tác.")
                break
    elif "--all" in sys.argv:
        print(f"🚀 [TEST SUITE MODE] Kiểm tra {len(tests)} Test Cases:")
        completed_count = 0
        todo_count = 0
        failed_count = 0
        all_traces = []
        request_pacer = RequestPacer(
            GEMINI_FREE_TIER_INTERVAL_SECONDS
            if provider.__class__.__name__ == "GeminiProvider" else 0
        )
        if request_pacer.interval_seconds:
            print(
                f"⏳ [Rate Limit Guard]: Gemini batch test sẽ giãn tối thiểu "
                f"{request_pacer.interval_seconds}s giữa các request live API."
            )
        
        for tc in tests:
            print(f"\n==================================================")
            print(f"🧪 [{tc['id']}] Loại test: {tc['type']} (Độ phức tạp: {tc['complexity']})")
            print(f"📌 Kỳ vọng: {tc['expected_behavior']}")
            
            if tc["question"].strip().startswith("TODO"):
                print(f"⏸️ [CHƯA KÍCH HOẠT - ĐANG LÀ TODO]:")
                print(f"   {tc['question']}")
                print(f"   👉 Hãy mở file 'config/test_cases.json' để viết câu hỏi thực tế cho Test Case này!")
                todo_count += 1
            else:
                logs = run_react_agent(
                    tc["question"], provider, mcp_server, request_pacer=request_pacer
                )
                all_traces.extend(logs)
                if any(log.get("action_type") == "PROVIDER_ERROR" for log in logs):
                    failed_count += 1
                else:
                    completed_count += 1
                
        print(f"\n==================================================")
        print(
            f"📊 [KẾT QUẢ TEST SUITE]: Thành công {completed_count}/{len(tests)} Test Cases "
            f"| Lỗi provider {failed_count} | {todo_count} Test Cases đang chờ điền câu hỏi (TODO)"
        )
        if all_traces:
            save_waterfall_trace(all_traces)
        print(f"💡 Để trò chuyện trực tiếp từng câu: Chạy 'python src/app.py --interactive'")
    else:
        # Chế độ mặc định khi chỉ gõ 'python src/app.py'
        print("ℹ️ HƯỚNG DẪN SỬ DỤNG CHƯƠNG TRÌNH:")
        print("  1. Chat trực tiếp liên tục:   python src/app.py --interactive")
        print("  2. Chạy toàn bộ Test Cases:    python src/app.py --all\n")
        
        sample_query = tests[1]["question"]
        print("--- 🏁 DEMO CHẠY THỬ 1 TEST CASE MẪU (TC02: Tra lịch bác sĩ mô phỏng) ---")
        logs = run_react_agent(sample_query, provider, mcp_server)
        save_waterfall_trace(logs)
        print("\n💡 Hãy thử ngay lệnh: python src/app.py --interactive để chat trực tiếp!")
