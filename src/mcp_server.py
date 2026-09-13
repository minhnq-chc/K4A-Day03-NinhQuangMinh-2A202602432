"""
🔌 MODEL CONTEXT PROTOCOL (MCP) SERVER MODULE
Mô phỏng kiến trúc MCP Server (Client-Server Architecture) cung cấp công cụ chuẩn hóa.
"""

import json
import sys
from typing import Dict, Any, List
from tools import TOOLS_SCHEMA, dispatch_tool_call

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

class MCPHealthServer:
    """
    Giả lập MCP Server tuân thủ chuẩn giao thức Model Context Protocol
    """
    def __init__(self, server_name: str = "vinmec-health-mcp-server-mock"):
        self.server_name = server_name
        self.version = "2026.1.0"
        
    def list_tools(self) -> List[Dict[str, Any]]:
        """Trả về danh sách các Tools chuẩn giao thức MCP"""
        return TOOLS_SCHEMA
        
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        [TASK 2.1] Thực thi request gọi Tool theo chuẩn MCP JSON-RPC.
        Execution layer dùng dữ liệu mô phỏng, không kết nối hệ thống Vinmec thật.
        """
        raw_result = dispatch_tool_call(tool_name, arguments)
        content = json.loads(raw_result)
        return {
            "jsonrpc": "2.0",
            "server": self.server_name,
            "tool": tool_name,
            "result": content
        }


if __name__ == "__main__":
    print("==========================================================")
    print("🔌 KIỂM THỬ ĐỘC LẬP MCP SERVER (vinmec-health-mcp-server-mock)")
    print("==========================================================")
    
    server = MCPHealthServer()
    tools = server.list_tools()
    print(f"✅ Khởi tạo thành công MCP Server: {server.server_name} (Version: {server.version})")
    print(f"📦 Số lượng Tools công bố: {len(tools)}")
    
    print("✅ [TASK 1.2]: Tool Schemas Vinmec mô phỏng đã sẵn sàng.")
    test_result = server.call_tool("get_doctor_availability", {
        "specialty": "Da liễu",
        "preferred_date": "2026-09-20"
    })
    print("✅ [TASK 2.1]: Test dispatch tool 'get_doctor_availability' thành công:")
    print(f"   Phản hồi JSON-RPC: {json.dumps(test_result, ensure_ascii=False)}")
