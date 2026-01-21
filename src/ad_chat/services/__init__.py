"""Services 패키지 초기화"""

from .simple_job_store import SimpleJobStore, get_job_store

# mcpadapter에서 MCPClient, LLMAdapter import
try:
    from mcpadapter import MCPClient, LLMAdapter
except ImportError:
    raise ImportError(
        "mcpadapter를 찾을 수 없습니다. "
        "프로젝트 루트에서 'pip install -e src/mcpadapter' 실행하세요."
    )

__all__ = ["SimpleJobStore", "get_job_store", "MCPClient", "LLMAdapter"]
