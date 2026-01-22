FROM python:3.12-slim

LABEL maintainer="CodeIt Team 3"
LABEL description="homepage_generator - AI 광고 홈페이지 생성기"

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# src 폴더 구조 유지하여 복사 (mcpadapter와 homepage_generator 모두 포함)
COPY src/mcpadapter /app/src/mcpadapter
COPY src/homepage_generator /app/src/homepage_generator

# mcpadapter 설치 (editable mode)
RUN pip install --no-cache-dir -e /app/src/mcpadapter

# homepage_generator requirements 설치
RUN pip install --no-cache-dir -r /app/src/homepage_generator/requirements.txt

# homepage_generator 폴더를 작업 디렉토리로 설정
WORKDIR /app/src/homepage_generator

# 환경 변수 기본값
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src:/app/src/mcpadapter:${PYTHONPATH}

# API 서버 포트 노출
EXPOSE 8891

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8891/health || exit 1

# FastAPI 서버 실행
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8891"]
