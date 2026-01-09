# nanoCocoa MCP Server - Docker 이미지
FROM python:3.11-slim

LABEL maintainer="CodeIt Team 3"
LABEL description="nanoCocoa MCP Server - AI 광고 생성을 위한 MCP 브릿지 서버"

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필수 도구 설치
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 복사 및 설치
COPY requirements-mcpserver.txt .
RUN pip install --no-cache-dir -r requirements-mcpserver.txt

# 애플리케이션 소스 복사
COPY . /app

# 환경 변수 기본값
ENV MCP_TRANSPORT=sse \
    MCP_PORT=3000 \
    MCP_HOST=0.0.0.0 \
    AISERVER_BASE_URL=http://nanococoa-aiserver:8000 \
    LOG_LEVEL=INFO

# 포트 노출
EXPOSE 3000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# 실행 명령
CMD ["python", "server.py"]
