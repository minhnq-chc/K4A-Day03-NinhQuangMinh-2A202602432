# 📊 BÁO CÁO THU HOẠCH NGHIỆM THU BÀI LAB 3 (BƯỚC 3 — SUBMISSION ARTIFACT)

> **Họ và Tên Học viên:** Ninh Quang Minh
> **Mã Sinh Viên / Mã Học viên:** 2A202602432
> **Chủ đề Lựa chọn:** Trợ lý Tư vấn Sức khỏe & Đặt lịch khám Vinmec (mô phỏng an toàn)

---

## 1. BẢNG CHẤM ĐIỂM AGENTIC FIT SCORING MATRIX (ĐÁNH GIÁ CHỦ ĐỀ)

| Tiêu chí Đánh giá | Mức độ (1 - 5) | Giải trình chi tiết lý do chọn điểm |
| :--- | :---: | :--- |
| **1. Multi-step Reasoning** | 5 / 5 | Agent phải thu thập thông tin tối thiểu, áp dụng luồng sàng lọc an toàn đã được phê duyệt, xác định nhu cầu khám/chuyên khoa, tra khung giờ, rồi xác nhận lịch. Hệ thống không chẩn đoán hay kê đơn. |
| **2. Tool Interaction** | 5 / 5 | Cần gọi các tool/dịch vụ ngoài cho dữ liệu chuyên khoa, lịch làm việc và khung giờ bác sĩ, kiểm tra khả dụng, và tạo lịch hẹn. Dữ liệu lịch/bác sĩ phải là dữ liệu được ủy quyền, không do LLM bịa ra. |
| **3. Dynamic Decision** | 5 / 5 | Hành động tiếp theo phụ thuộc vào quan sát trước đó: tín hiệu khẩn cấp thì dừng luồng đặt lịch và hướng dẫn liên hệ cấp cứu/cơ sở y tế; không khẩn cấp thì chuyên khoa và lựa chọn lịch phụ thuộc vào dữ liệu tool trả về. |
| **4. Long Horizon Goal** | 4 / 5 | Mục tiêu được duy trì qua nhiều lượt là hoàn tất một lịch khám hợp lệ hoặc đóng luồng an toàn. Chưa chấm 5 vì phiên bản lab chưa có planner, memory dài hạn hay quyền tự hành động ngoài phạm vi lịch hẹn. |
| **TỔNG ĐIỂM AGENTIC FIT** | **19 / 20** | *Bài toán phù hợp triển khai ReAct Agent: cần nhiều bước, tool, quan sát và quyết định động; chưa phải Autonomous Agent.* |

---

## 2. TRÍCH XUẤT KẾT QUẢ WATERFALL TRACE LOG (SAU KHI CHẠY TEST SUITE TRÊN API THẬT)

> ⚠️ **YÊU CẦU NGHIỆM THU:** Mở tệp `.env` điền `GEMINI_API_KEY` (hoặc `OPENAI_API_KEY`) để kết nối LLM thật trước khi thực thi `python src/app.py --all`. Bài nộp chỉ dùng Mock Offline Provider sẽ không đạt điểm nghiệm thực tế.

Dán 1 đoạn trích xuất log tiêu biểu từ file `docs/trace_waterfall.json` sinh ra từ phản hồi LLM API thật.

> **Bằng chứng live API:** `provider` là `GeminiProvider`; Gemini đã chủ động gọi `get_doctor_availability`, nhận Observation từ MCP Server rồi sinh phản hồi dựa trên dữ liệu đó. Lịch và bác sĩ trong observation là `MOCK_LAB_DATA`, không phải dữ liệu Vinmec thật.

```json
[
  {
    "step": 1,
    "provider": "GeminiProvider",
    "action_type": "TOOL_EXECUTION",
    "tool_name": "get_doctor_availability",
    "arguments": {
      "preferred_date": "2026-09-20",
      "specialty": "Da liễu"
    },
    "observation": {
      "status": "SUCCESS",
      "data": {
        "doctors": [
          {
            "doctor_id": "DOC-DL-01",
            "display_name": "Bác sĩ Da liễu 01 (mô phỏng)",
            "available_slots": [
              "2026-09-20T09:00:00+07:00",
              "2026-09-20T10:30:00+07:00"
            ]
          }
        ]
      },
      "data_classification": "MOCK_LAB_DATA"
    },
    "latency_ms": 2947.06
  },
  {
    "step": 2,
    "provider": "GeminiProvider",
    "action_type": "FINAL_ANSWER",
    "latency_ms": 4403.73
  }
]
```

> **Giới hạn nghiệm thu:** Lần chạy live đầu tiên bị Free Tier throttle sau các request đầu (HTTP 429, 5 request/phút với model cấu hình), nên không dùng phần event `PROVIDER_ERROR` làm bằng chứng thành công. Mã nguồn đã được bổ sung guard giãn 13 giây/request khi chạy `--all`; toàn bộ 8 TC đã được regression offline sau thay đổi, còn chạy lại live 8/8 phụ thuộc quota Free Tier.

---

## 3. TỔNG KẾT KẾT QUẢ NGHIỆM THU & NỘP BÀI

- [x] Đã điền API Key thật trong `.env` và xác nhận luồng Gemini → Native Tool Calling → MCP Server hoạt động.
- **Kết quả test:** Gemini hoàn tất phản hồi live cho TC01–TC02; TC03 đã thực hiện hai tool call live (tra lịch rồi booking) trước khi Free Tier trả HTTP 429. TC05 được application guardrail dừng an toàn, không gọi tool. Sau bản sửa rate-limit, regression offline đạt 8/8 TC.
- **Số lượt gọi Tool qua MCP Server trong live trace trước throttle:** 4 lượt; tất cả observation dùng dữ liệu mô phỏng tối thiểu.
- **Context window:** Giữ tối đa 4 lượt hội thoại gần nhất trong RAM của phiên interactive; không ghi lịch sử hội thoại vào trace hoặc file.
- **Kết quả đẩy Repo nộp bài:** [ ] Anh thực hiện Commit và Push mã nguồn thành công lên GitHub cá nhân.

---

> ✅ **HOÀN TẤT NỘP BÀI:** Sao chép đường link GitHub Repository cá nhân của bạn và dán vào ô nộp bài trên hệ thống LMS VLearn để hoàn tất Bài Lab 3!
