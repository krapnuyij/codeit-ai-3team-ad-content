# ad_chat Streamlit 애플리케이션 - Docker 이미지
FROM continuumio/miniconda3:latest

LABEL maintainer="CodeIt Team 3"
LABEL description="ad_chat - AI 광고 생성 Streamlit 애플리케이션"

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 설치 (curl for healthcheck)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# conda 기본 환경에 Python 3.11 설치
RUN conda install -y python=3.11 && \
    conda clean -afy

# src 폴더 구조 유지하여 복사 (mcpadapter와 ad_chat 모두 포함)
COPY src/mcpadapter /app/src/mcpadapter
COPY src/ad_chat /app/src/ad_chat

# mcpadapter 설치 (editable mode)
RUN pip install --no-cache-dir -e /app/src/mcpadapter

# ad_chat requirements 설치
RUN pip install --no-cache-dir -r /app/src/ad_chat/requirements.txt

# ad_chat 폴더를 작업 디렉토리로 설정
WORKDIR /app/src/ad_chat

# 환경 변수 기본값 (Docker 모드)
ENV RUNTIME_ENV=docker \
    STATIC_BASE_PATH=/app/static \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# 포트 노출
EXPOSE 8501

# 헬스체크 (단순 HTTP 체크 - Streamlit 메인 페이지)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8501 || exit 1

# 실행 명령
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
