# Dockerfile for nanoCocoa AI Server
# Base: NVIDIA CUDA 12.9.1 with cuDNN runtime on Ubuntu 22.04

FROM nvidia/cuda:12.9.1-cudnn-runtime-ubuntu22.04

# Maintainer
LABEL maintainer="codeit-ai-3team"
LABEL description="nanoCocoa AI Server - Advertisement Content Generation"

# 환경 변수 설정
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    HF_HOME=/root/.cache/huggingface \
    TRANSFORMERS_CACHE=/root/.cache/huggingface/transformers \
    HF_HUB_CACHE=/root/.cache/huggingface/hub

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    python3-pip \
    git \
    wget \
    curl \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    ca-certificates \
    software-properties-common \
    && add-apt-repository ppa:ubuntu-toolchain-r/test -y \
    && apt-get update \
    && apt-get install -y --no-install-recommends gcc-13 g++-13 libstdc++6 \
    && update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-13 100 \
    && update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-13 100 \
    && rm -rf /var/lib/apt/lists/*

# Python 3.11을 기본으로 설정
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# pip 업그레이드
RUN python3 -m pip install --upgrade pip setuptools wheel

# 작업 디렉토리 생성
WORKDIR /app

# requirements 복사 및 설치
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

# 애플리케이션 코드 복사
COPY . .

# 디렉토리 구조 생성
RUN mkdir -p \
    /app/static/uploads \
    /app/static/results \
    /app/logs \
    /root/.cache/huggingface

# 포트 노출
EXPOSE 8000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 실행 명령
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
