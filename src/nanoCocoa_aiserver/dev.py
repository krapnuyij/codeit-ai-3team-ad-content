"""
개발 서버 실행 스크립트
"""

import os
import sys
from pathlib import Path
import uvicorn

if __name__ == "__main__":
    
    # Add src to path
    files= ["h2_stations.db", "service_areas.db", "h2_status.db"]
    for file in files:
        if Path(file).exists():
            Path(file).unlink()
        if (Path("src") / file).exists():
            (Path("src") / file).unlink()

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["tests", "**/__pycache__", "*.pyc", ".pytest_cache"],
    )
