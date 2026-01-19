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
    PYTORCH_ALLOC_CONF=expandable_segments:True \
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
    build-essential \
    gcc \
    g++ \
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

# PyTorch는 별도 인덱스에서 설치 (CUDA 12.8 호환)
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cu128 \
    torch==2.9.0+cu128 torchvision==0.24.0+cu128 torchaudio==2.9.0+cu128

# 나머지 패키지 설치 (torch 관련 제외)
RUN grep -v "^torch" requirements-docker.txt | grep -v "^--index-url" > /tmp/requirements-no-torch.txt && \
    pip install --no-cache-dir -r /tmp/requirements-no-torch.txt

# 애플리케이션 코드 복사
COPY . .

# 디렉토리 구조 생성
RUN mkdir -p \
    /app/static/uploads \
    /app/static/results \
    /app/logs \
    /root/.cache/huggingface

# 포트 노출
EXPOSE 8892

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 실행 명령
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8892", "--workers", "1"]
