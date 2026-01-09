"""
mcpadapter - MCP 클라이언트 어댑터 라이브러리

백엔드 애플리케이션에서 nanoCocoa MCP 서버와 통신하기 위한 경량 라이브러리
"""

__version__ = "1.0.0"

from .mcp_client import MCPClient
from .llm_adapter import LLMAdapter

__all__ = ["MCPClient", "LLMAdapter"]
