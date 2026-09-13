"""
🔌 MULTI-PROVIDER LLM ADAPTER (Google Gemini, OpenAI & Offline Mock)
Hỗ trợ Native Tool Calling và chuyển đổi linh hoạt qua biến môi trường LLM_PROVIDER.
"""

import os
import sys
import json
import re
from typing import Dict, Any, List
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

class BaseLLMProvider:
    """Interface cơ sở cho các LLM Provider hỗ trợ Native Tool Calling"""
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError

    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: List[Dict[str, Any]],
        system_prompt: str = "",
        observations: List[Dict[str, Any]] | None = None,
        conversation_history: List[Dict[str, str]] | None = None
    ) -> Dict[str, Any]:
        raise NotImplementedError


class MockOfflineProvider(BaseLLMProvider):
    """Offline Mock Provider dùng để chạy thử mà không tốn API Key"""
    def __init__(self):
        self.model_name = "Offline-Mock-Model-2026"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return (
            "[Mock Chatbot Response]: Tôi hỗ trợ thông tin sức khỏe tổng quát và đặt lịch mô phỏng. "
            "Tôi không chẩn đoán, kê đơn hoặc có quyền truy cập dữ liệu thời gian thực."
        )

    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: List[Dict[str, Any]],
        system_prompt: str = "",
        observations: List[Dict[str, Any]] | None = None,
        conversation_history: List[Dict[str, str]] | None = None
    ) -> Dict[str, Any]:
        """Mô phỏng ReAct deterministically cho bộ TC của lab, không dùng dữ liệu y tế thật."""
        prompt_lower = prompt.lower()
        observations = observations or []

        if observations:
            latest = observations[-1]["result"]
            latest_status = latest.get("status")
            latest_tool = observations[-1]["tool_name"]
            if latest_tool == "get_doctor_availability":
                if latest_status == "NO_AVAILABILITY":
                    return {
                        "type": "text",
                        "content": "Lịch mô phỏng chưa có slot phù hợp. Tôi chỉ có thể đề xuất alternatives từ Observation và cần bạn xác nhận một lựa chọn mới.",
                        "thought": "Observation báo không có lịch; không được tạo booking và cần xin xác nhận mới."
                    }
                if latest_status == "SUCCESS":
                    doctors = latest.get("data", {}).get("doctors", [])
                    if "16:30" in prompt and all(
                        "T16:30:00+07:00" not in doctor.get("available_slots", [])
                        for doctor in doctors
                    ):
                        return {
                            "type": "text",
                            "content": "Slot 16:30 được yêu cầu không có trong Observation. Tôi chỉ có thể đề xuất các slot thay thế từ lịch mô phỏng và chờ xác nhận mới.",
                            "thought": "Slot người dùng chọn không nằm trong dữ liệu lịch; không được tạo booking."
                        }
                    has_consent = "đồng ý" in prompt_lower
                    has_confirmation = "xác nhận" in prompt_lower or "đặt ngay" in prompt_lower
                    wants_booking = "đặt lịch" in prompt_lower or "đặt ngay" in prompt_lower
                    if wants_booking and has_consent and has_confirmation:
                        doctor_match = re.search(r"DOC-[A-Z]+-\d+", prompt.upper())
                        time_match = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+07:00", prompt)
                        patient_match = re.search(r"PT-\d+", prompt.upper())
                        doctor_id = doctor_match.group(0) if doctor_match else doctors[0]["doctor_id"]
                        datetime_str = time_match.group(0) if time_match else doctors[0]["available_slots"][0]
                        patient_id = patient_match.group(0) if patient_match else "PT-MOCK"
                        return {
                            "type": "tool_call",
                            "tool_name": "book_medical_appointment",
                            "arguments": {
                                "patient_id": patient_id,
                                "doctor_id": doctor_id,
                                "datetime_str": datetime_str,
                                "consent_to_share": True,
                                "patient_confirmed": True
                            },
                            "thought": "Đã quan sát slot, consent và xác nhận; gọi tool booking với dữ liệu tối thiểu."
                        }
                    observation_summary = json.dumps(doctors, ensure_ascii=False)
                    return {
                        "type": "text",
                        "content": f"Lịch khả dụng mô phỏng từ Observation: {observation_summary}. Vui lòng chọn bác sĩ/slot và xác nhận đồng ý chia sẻ dữ liệu tối thiểu trước khi đặt.",
                        "thought": "Có lịch; chỉ trình bày dữ liệu Observation và yêu cầu điều kiện booking còn thiếu."
                    }
            if latest_tool == "book_medical_appointment":
                return {
                    "type": "text",
                    "content": latest.get("message", "Đã nhận kết quả booking mô phỏng từ MCP Server."),
                    "thought": "Tổng hợp kết quả booking từ Observation, không bịa thêm dữ liệu."
                }
            if latest_tool == "retrieve_approved_health_information":
                return {
                    "type": "text",
                    "content": latest.get("data", {}).get("summary", latest.get("message", "Không có nội dung đã phê duyệt.")),
                    "thought": "Chỉ tóm tắt nội dung tổng quát có trong Observation."
                }

        if "nguồn" in prompt_lower or "phạm vi" in prompt_lower:
            return {
                "type": "tool_call",
                "tool_name": "retrieve_approved_health_information",
                "arguments": {"topic": "service_scope", "language": "vi"},
                "thought": "Cần tra nội dung tổng quát đã được phê duyệt thay vì tự bịa nguồn."
            }

        if "chưa đồng ý" in prompt_lower or "số điện thoại" in prompt_lower:
            return {
                "type": "text",
                "content": "Tôi chỉ có thể tiếp tục đến bước giải thích dữ liệu tối thiểu và tra lịch mô phỏng nếu chính sách cho phép. Tôi không tạo booking trước khi có sự đồng ý rõ ràng để chia sẻ dữ liệu tối thiểu.",
                "thought": "Thiếu consent bắt buộc; dừng trước booking và tối thiểu hóa dữ liệu."
            }

        specialty = None
        preferred_date = None
        doctor_id = None
        if "da liễu" in prompt_lower:
            specialty, preferred_date, doctor_id = "Da liễu", "2026-09-20", "DOC-DL-01"
        elif "thượng vị" in prompt_lower or "tiêu hóa" in prompt_lower:
            specialty, preferred_date, doctor_id = "Tiêu hóa", "2026-09-21", "DOC-TH-01"
        elif "nhi" in prompt_lower:
            specialty, preferred_date, doctor_id = "Nhi", "2026-09-22", "DOC-NHI-02"
        elif "nội tổng quát" in prompt_lower or "doc-nt-03" in prompt_lower:
            specialty, preferred_date, doctor_id = "Nội tổng quát", "2026-09-23", "DOC-NT-03"

        if specialty:
            return {
                "type": "tool_call",
                "tool_name": "get_doctor_availability",
                "arguments": {
                    "specialty": specialty,
                    "preferred_date": preferred_date,
                    "doctor_id": doctor_id,
                    "time_of_day": "any"
                },
                "thought": "Cần quan sát lịch khả dụng mô phỏng trước khi có thể đề xuất hoặc tạo booking."
            }
        return {
            "type": "text",
            "content": "Tôi có thể hỗ trợ thông tin tổng quát và đặt lịch mô phỏng; tôi không chẩn đoán hoặc kê đơn.",
            "thought": "Câu hỏi không cần dữ liệu tool hoặc cần làm rõ yêu cầu."
        }


class GeminiProvider(BaseLLMProvider):
    """Google Gemini Provider (Native Tool Calling với Google GenAI SDK)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-2.5-flash"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            return "[Gemini Error]: Chưa cấu hình GEMINI_API_KEY trong file .env! Đang sử dụng chế độ Mock."
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            contents = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = client.models.generate_content(model=self.model_name, contents=contents)
            return response.text
        except Exception as e:
            return f"[Gemini Exception]: {str(e)}"

    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: List[Dict[str, Any]],
        system_prompt: str = "",
        observations: List[Dict[str, Any]] | None = None,
        conversation_history: List[Dict[str, str]] | None = None
    ) -> Dict[str, Any]:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            print("ℹ️ [Gemini Provider]: Chưa tìm thấy GEMINI_API_KEY hợp lệ. Tự động chuyển sang Mock Offline.")
            return MockOfflineProvider().generate_with_tools(
                prompt, tools_schema, system_prompt, observations, conversation_history
            )
        
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            
            # Chuẩn hóa function declarations cho Gemini SDK
            function_declarations = []
            for tool in tools_schema:
                # Bỏ qua các tool schema chưa được định nghĩa hoàn chỉnh
                if not tool.get("name") or not tool.get("parameters"):
                    continue
                function_declarations.append({
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                })

            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                tools=[{"function_declarations": function_declarations}] if function_declarations else None,
                # Agent quản lý vòng Thought → Action → Observation; không để SDK
                # tự gọi hàm vì tool ở đây được thực thi qua MCPHealthServer.
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                temperature=0.2
            )

            conversation_context = ""
            if conversation_history:
                conversation_context = "\n\nNgữ cảnh tạm thời của phiên hiện tại:\n" + json.dumps(
                    conversation_history, ensure_ascii=False
                )
            observation_context = ""
            if observations:
                observation_context = "\n\nTool observations từ các bước trước:\n" + json.dumps(observations, ensure_ascii=False)
            response = client.models.generate_content(
                model=self.model_name,
                contents=conversation_context + "\n\nYêu cầu hiện tại:\n" + prompt + observation_context,
                config=config
            )

            # Kiểm tra xem Gemini có trả về Tool Call không
            if response.function_calls:
                call = response.function_calls[0]
                args = dict(call.args) if hasattr(call, 'args') and call.args else {}
                return {
                    "type": "tool_call",
                    "tool_name": call.name,
                    "arguments": args,
                    "thought": f"Gemini quyết định gọi công cụ '{call.name}' với tham số: {json.dumps(args, ensure_ascii=False)}"
                }
            else:
                return {
                    "type": "text",
                    "content": response.text or "",
                    "thought": "Gemini phản hồi trực tiếp bằng văn bản (không cần gọi công cụ)."
                }

        except Exception as e:
            return {
                "type": "provider_error",
                "content": f"Gemini API không thể xử lý request: {str(e)}",
                "thought": "Live provider lỗi; dừng thay vì fallback Mock để không làm sai bằng chứng nghiệm thu."
            }


class OpenAIProvider(BaseLLMProvider):
    """OpenAI Provider (Native Tool Calling với OpenAI SDK)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            return "[OpenAI Error]: Chưa cấu hình OPENAI_API_KEY trong file .env! Đang sử dụng chế độ Mock."
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(model=self.model_name, messages=messages)
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[OpenAI Exception]: {str(e)}"

    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: List[Dict[str, Any]],
        system_prompt: str = "",
        observations: List[Dict[str, Any]] | None = None,
        conversation_history: List[Dict[str, str]] | None = None
    ) -> Dict[str, Any]:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            print("ℹ️ [OpenAI Provider]: Chưa tìm thấy OPENAI_API_KEY hợp lệ. Tự động chuyển sang Mock Offline.")
            return MockOfflineProvider().generate_with_tools(
                prompt, tools_schema, system_prompt, observations, conversation_history
            )

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)

            tools = []
            for tool in tools_schema:
                if not tool.get("name"):
                    continue
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {})
                    }
                })

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            for turn in conversation_history or []:
                role = turn.get("role")
                content = turn.get("content")
                if role in {"user", "assistant"} and content:
                    messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": prompt})
            if observations:
                messages.append({
                    "role": "user",
                    "content": "Tool observations từ các bước trước:\n" + json.dumps(observations, ensure_ascii=False)
                })

            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None
            )

            msg = response.choices[0].message
            if msg.tool_calls:
                call = msg.tool_calls[0]
                args = json.loads(call.function.arguments) if call.function.arguments else {}
                return {
                    "type": "tool_call",
                    "tool_name": call.function.name,
                    "arguments": args,
                    "thought": f"OpenAI quyết định gọi công cụ '{call.function.name}' với tham số: {json.dumps(args, ensure_ascii=False)}"
                }
            else:
                return {
                    "type": "text",
                    "content": msg.content or "",
                    "thought": "OpenAI phản hồi trực tiếp bằng văn bản (không cần gọi công cụ)."
                }
        except Exception as e:
            return {
                "type": "provider_error",
                "content": f"OpenAI API không thể xử lý request: {str(e)}",
                "thought": "Live provider lỗi; dừng thay vì fallback Mock để không làm sai bằng chứng nghiệm thu."
            }


def get_llm_provider() -> BaseLLMProvider:
    """Factory function khởi tạo Provider theo LLM_PROVIDER env variable"""
    provider_type = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    if provider_type == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        if key and key != "your_gemini_api_key_here":
            return GeminiProvider()
        else:
            return MockOfflineProvider()
    elif provider_type == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if key and key != "your_openai_api_key_here":
            return OpenAIProvider()
        else:
            return MockOfflineProvider()
    elif provider_type == "mock":
        return MockOfflineProvider()
    else:
        return MockOfflineProvider()
