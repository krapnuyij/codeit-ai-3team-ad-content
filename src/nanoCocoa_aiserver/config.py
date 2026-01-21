import sys
from pathlib import Path

project_root = Path(__file__).resolve()
sys.path.insert(0, str(project_root))

import logging
import os

import torch
from helper_dev_utils import get_auto_logger

# PyTorch CUDA 메모리 최적화 설정 (메모리 단편화 완화)
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

# ==========================================
# ⚙️ 설정 & 상수 (Configuration)
# ==========================================
DEVICE = "cuda"
TORCH_DTYPE = torch.bfloat16

# 모델 ID 정의
MODEL_IDS = {
    "SEG": "ZhengPeng7/BiRefNet",
    "FLUX": "black-forest-labs/FLUX.1-dev",
    "SDXL_BASE": "stabilityai/stable-diffusion-xl-base-1.0",
    "SDXL_CNET": "diffusers/controlnet-canny-sdxl-1.0",
    "SDXL_VAE": "madebyollin/sdxl-vae-fp16-fix",
}

# 예상 소요 시간 (초 단위, 초기값)
ESTIMATED_TIMES = {
    "init": 30,
    "stage_a": 600,  # 배경 생성 및 합성
    "stage_b": 600,  # 텍스트 자산 생성
    "stage_c": 90,  # 최종 합성 (Flux Inpainting 추가: 28 steps ≈ 30초)
}
TOTAL_ESTIMATED_TIME = sum(ESTIMATED_TIMES.values())

# 메모리 관리 설정
AUTO_UNLOAD_DEFAULT = True  # 기본값: 각 단계 완료 후 모델 언로드

# 로깅 설정
logger = get_auto_logger()
