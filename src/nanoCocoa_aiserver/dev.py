"""
개발 서버 실행 스크립트
"""

import os
import sys
from pathlib import Path
import uvicorn

if __name__ == "__main__":
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
