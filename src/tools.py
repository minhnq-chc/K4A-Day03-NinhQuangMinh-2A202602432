"""
🛠️ TOOL DEFINITIONS & EXECUTION BACKEND
Mã nguồn chứa danh sách Tool Schemas (JSON Schema) và Execution Layer phục vụ cho MCP Server.
"""

import json
from typing import Dict, Any

# ==============================================================================
# 1. KHAI BÁO TOOL SCHEMAS CHUẨN NATIVE JSON SCHEMA (TASK 1.2)
# ==============================================================================

TOOLS_SCHEMA = [
    {
        "name": "retrieve_approved_health_information",
        "description": (
            "Truy xuất thông tin sức khỏe tổng quát từ kho nội dung đã được phê duyệt. "
            "Không dùng để chẩn đoán, kê đơn, hay thay thế tư vấn của nhân viên y tế."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Chủ đề sức khỏe cần tra cứu, không bao gồm kết luận chẩn đoán."
                },
                "language": {
                    "type": "string",
                    "enum": ["vi", "en"],
                    "description": "Ngôn ngữ phản hồi mong muốn; mặc định là 'vi'."
                }
            },
            "required": ["topic"]
        }
    },
    {
        "name": "get_doctor_availability",
        "description": (
            "Tra cứu bác sĩ và khung giờ khám còn khả dụng theo chuyên khoa trong dữ liệu lịch "
            "được ủy quyền. Không tự tạo tên bác sĩ hoặc thời gian không có trong kết quả tool."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "specialty": {
                    "type": "string",
                    "description": "Chuyên khoa cần tra cứu, ví dụ: 'Da liễu', 'Nhi', 'Tim mạch'."
                },
                "preferred_date": {
                    "type": "string",
                    "format": "date",
                    "description": "Ngày mong muốn khám theo ISO 8601, ví dụ: '2026-09-20'."
                },
                "doctor_id": {
                    "type": "string",
                    "description": "Mã bác sĩ nếu người dùng đã chọn; bỏ qua nếu muốn xem tất cả bác sĩ phù hợp."
                },
                "time_of_day": {
                    "type": "string",
                    "enum": ["morning", "afternoon", "evening", "any"],
                    "description": "Buổi khám mong muốn; mặc định là 'any'."
                }
            },
            "required": ["specialty", "preferred_date"]
        }
    },
    {
        "name": "book_medical_appointment",
        "description": (
            "Tạo lịch khám sau khi người dùng đã xác nhận bác sĩ và khung giờ. "
            "Chỉ gửi dữ liệu tối thiểu cần cho booking và yêu cầu sự đồng ý rõ ràng."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "string",
                    "description": "Mã bệnh nhân hoặc mã mô phỏng đã được xác thực; không truyền thông tin định danh thừa."
                },
                "doctor_id": {
                    "type": "string",
                    "description": "Mã bác sĩ được chọn từ kết quả get_doctor_availability."
                },
                "datetime_str": {
                    "type": "string",
                    "description": "Khung giờ đã được tool xác nhận còn trống, theo ISO 8601 có múi giờ."
                },
                "consent_to_share": {
                    "type": "boolean",
                    "description": "True khi người dùng đã đồng ý chia sẻ dữ liệu tối thiểu cho việc đặt lịch."
                },
                "patient_confirmed": {
                    "type": "boolean",
                    "description": "True khi người dùng đã xác nhận rõ ràng bác sĩ và khung giờ trước khi tạo booking."
                }
            },
            "required": [
                "patient_id",
                "doctor_id",
                "datetime_str",
                "consent_to_share",
                "patient_confirmed"
            ]
        }
    }
]

# ==============================================================================
# 2. DỮ LIỆU MÔ PHỎNG & HÀM THỰC THI TOOL (TASK 2.1)
# ==============================================================================
# Dữ liệu dưới đây chỉ phục vụ lab: không phải dữ liệu Vinmec, hồ sơ bệnh nhân,
# lịch bác sĩ hoặc hướng dẫn chẩn đoán thực tế.

MOCK_APPROVED_HEALTH_KNOWLEDGE = {
    "service_scope": {
        "summary": (
            "Trợ lý chỉ cung cấp thông tin tổng quát từ nguồn đã phê duyệt và hỗ trợ "
            "đặt lịch; không chẩn đoán, kê đơn hoặc thay thế nhân viên y tế."
        ),
        "source": {
            "publisher": "World Health Organization",
            "title": "WHO calls for safe and ethical AI for health",
            "url": "https://www.who.int/news/item/16-05-2023-who-calls-for-safe-and-ethical-ai-for-health"
        }
    },
    "đau_thượng_vị": {
        "summary": (
            "Trong kịch bản lab, triệu chứng mô tả không có tín hiệu khẩn cấp sẽ được "
            "phân luồng hỗ trợ đặt lịch tới chuyên khoa Tiêu hóa. Đây không phải chẩn đoán "
            "hay khuyến nghị điều trị."
        ),
        "suggested_specialty": "Tiêu hóa",
        "disclaimer": "Nếu triệu chứng nặng lên hoặc xuất hiện tín hiệu khẩn cấp, cần liên hệ cơ sở y tế ngay."
    }
}

MOCK_DOCTOR_SCHEDULE = [
    {
        "doctor_id": "DOC-DL-01",
        "display_name": "Bác sĩ Da liễu 01 (mô phỏng)",
        "specialty": "Da liễu",
        "date": "2026-09-20",
        "available_slots": ["2026-09-20T09:00:00+07:00", "2026-09-20T10:30:00+07:00"]
    },
    {
        "doctor_id": "DOC-TH-01",
        "display_name": "Bác sĩ Tiêu hóa 01 (mô phỏng)",
        "specialty": "Tiêu hóa",
        "date": "2026-09-21",
        "available_slots": ["2026-09-21T14:00:00+07:00", "2026-09-21T15:30:00+07:00"]
    },
    {
        "doctor_id": "DOC-NHI-02",
        "display_name": "Bác sĩ Nhi 02 (mô phỏng)",
        "specialty": "Nhi",
        "date": "2026-09-22",
        "available_slots": ["2026-09-22T15:30:00+07:00", "2026-09-22T17:00:00+07:00"]
    },
    {
        "doctor_id": "DOC-NT-03",
        "display_name": "Bác sĩ Nội tổng quát 03 (mô phỏng)",
        "specialty": "Nội tổng quát",
        "date": "2026-09-23",
        "available_slots": ["2026-09-23T09:00:00+07:00"]
    }
]


def execute_retrieve_approved_health_information(topic: str, language: str = "vi") -> str:
    """Truy xuất nội dung tổng quát đã được phê duyệt trong dữ liệu mô phỏng."""
    normalized_topic = topic.strip().lower().replace(" ", "_")
    content = MOCK_APPROVED_HEALTH_KNOWLEDGE.get(normalized_topic)
    if content:
        return json.dumps({
            "status": "SUCCESS",
            "topic": normalized_topic,
            "language": language,
            "data": content,
            "disclaimer": "Thông tin tổng quát, không phải chẩn đoán hoặc chỉ định điều trị."
        }, ensure_ascii=False)
    return json.dumps({
        "status": "NOT_FOUND",
        "message": "Không có nội dung đã phê duyệt phù hợp trong kho mô phỏng."
    }, ensure_ascii=False)


def _matches_time_of_day(datetime_str: str, time_of_day: str) -> bool:
    """Lọc slot theo buổi trong dữ liệu mô phỏng."""
    if time_of_day == "any":
        return True
    hour = int(datetime_str[11:13])
    if time_of_day == "morning":
        return hour < 12
    if time_of_day == "afternoon":
        return 12 <= hour < 17
    return hour >= 17


def execute_get_doctor_availability(
    specialty: str,
    preferred_date: str,
    doctor_id: str | None = None,
    time_of_day: str = "any"
) -> str:
    """Tra cứu lịch bác sĩ mô phỏng; chỉ trả về slot có trong dữ liệu tool."""
    matches = [
        item for item in MOCK_DOCTOR_SCHEDULE
        if item["specialty"].lower() == specialty.strip().lower()
        and item["date"] == preferred_date
        and (doctor_id is None or item["doctor_id"] == doctor_id)
    ]
    doctors = []
    for item in matches:
        slots = [slot for slot in item["available_slots"] if _matches_time_of_day(slot, time_of_day)]
        if slots:
            doctors.append({
                "doctor_id": item["doctor_id"],
                "display_name": item["display_name"],
                "specialty": item["specialty"],
                "available_slots": slots
            })
    if doctors:
        return json.dumps({
            "status": "SUCCESS",
            "specialty": specialty,
            "preferred_date": preferred_date,
            "data": {"doctors": doctors},
            "data_classification": "MOCK_LAB_DATA"
        }, ensure_ascii=False)
    alternatives = [
        {
            "doctor_id": item["doctor_id"],
            "date": item["date"],
            "available_slots": item["available_slots"]
        }
        for item in MOCK_DOCTOR_SCHEDULE
        if item["specialty"].lower() == specialty.strip().lower()
    ]
    return json.dumps({
        "status": "NO_AVAILABILITY",
        "message": "Không có lịch phù hợp trong dữ liệu mô phỏng.",
        "alternatives": alternatives,
        "data_classification": "MOCK_LAB_DATA"
    }, ensure_ascii=False)


def execute_book_medical_appointment(
    patient_id: str,
    doctor_id: str,
    datetime_str: str,
    consent_to_share: bool,
    patient_confirmed: bool
) -> str:
    """Tạo booking mô phỏng sau khi kiểm tra đồng ý, xác nhận và slot còn trống."""
    if not consent_to_share:
        return json.dumps({
            "status": "CONSENT_REQUIRED",
            "message": "Cần sự đồng ý chia sẻ dữ liệu tối thiểu trước khi đặt lịch."
        }, ensure_ascii=False)
    if not patient_confirmed:
        return json.dumps({
            "status": "CONFIRMATION_REQUIRED",
            "message": "Cần người dùng xác nhận rõ ràng bác sĩ và khung giờ trước khi đặt lịch."
        }, ensure_ascii=False)

    schedule = next((item for item in MOCK_DOCTOR_SCHEDULE if item["doctor_id"] == doctor_id), None)
    if not schedule or datetime_str not in schedule["available_slots"]:
        return json.dumps({
            "status": "SLOT_UNAVAILABLE",
            "message": "Khung giờ không còn khả dụng trong dữ liệu mô phỏng; cần tra lại lịch và xin xác nhận lựa chọn khác."
        }, ensure_ascii=False)
    return json.dumps({
        "status": "SUCCESS",
        "booking_id": f"MOCK-BK-{patient_id}-{doctor_id}-{datetime_str[11:16].replace(':', '')}",
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "doctor_name": schedule["display_name"],
        "datetime": datetime_str,
        "message": "Đặt lịch mô phỏng thành công.",
        "data_classification": "MOCK_LAB_DATA"
    }, ensure_ascii=False)


TOOL_ROUTER = {
    "retrieve_approved_health_information": execute_retrieve_approved_health_information,
    "get_doctor_availability": execute_get_doctor_availability,
    "book_medical_appointment": execute_book_medical_appointment
}

def dispatch_tool_call(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Hàm trung chuyển thực thi tool"""
    if tool_name in TOOL_ROUTER:
        try:
            return TOOL_ROUTER[tool_name](**arguments)
        except Exception as e:
            return json.dumps({"status": "EXECUTION_ERROR", "error": str(e)}, ensure_ascii=False)
    return json.dumps({"status": "UNKNOWN_TOOL", "error": f"Tool '{tool_name}' không tồn tại!"}, ensure_ascii=False)
