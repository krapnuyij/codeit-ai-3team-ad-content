"""
GPU 메모리 관리 및 이미지 작업을 위한 유틸리티 함수들
Utility functions for GPU memory management and image operations.
"""

import gc
import torch
from PIL import Image
from typing import Union
from pathlib import Path
import logging

# Try to import helper_dev_utils, fallback to standard logging if not available
try:
    from helper_dev_utils import get_auto_logger
    logger = get_auto_logger()
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


def flush_gpu():
    """
    GPU 메모리 캐시를 정리하고 가비지 컬렉션을 실행합니다.

    모델 언로드 후 VRAM을 확보하기 위해 이 함수를 호출하세요.
    각 파이프라인 단계가 끝날 때마다 호출하여 메모리 부족을 방지합니다.

    동작:
        1. Python 가비지 컬렉션 실행
        2. CUDA 캐시 메모리 비우기
        3. CUDA 동기화 (모든 작업 완료 대기)
    """
    gc.collect()  # Python 가비지 컬렉션
    if torch.cuda.is_available():
        torch.cuda.empty_cache()  # CUDA 캐시 메모리 정리
        torch.cuda.synchronize()  # GPU 작업 동기화
    print("✓ GPU 메모리 정리 완료")


def load_image(path: Union[str, Path]) -> Image.Image:
    """
    지정된 경로에서 이미지를 로드합니다.

    Args:
        path: 이미지 파일 경로

    Returns:
        RGB 또는 RGBA 모드의 PIL Image 객체

    Raises:
        FileNotFoundError: 이미지 파일이 존재하지 않을 때

    Example:
        >>> img = load_image("product.png")
        >>> print(img.size)  # (width, height)
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"이미지를 찾을 수 없습니다: {path}")

    image = Image.open(path)

    # RGB 또는 RGBA가 아니면 RGB로 변환
    if image.mode not in ["RGB", "RGBA"]:
        image = image.convert("RGB")

    print(
        f"✓ 이미지 로드 완료: {path.name} ({image.size[0]}x{image.size[1]}, {image.mode})"
    )
    return image


def save_image(image: Image.Image, path: Union[str, Path], quality: int = 95):
    """
    PIL 이미지를 지정된 경로에 저장합니다.

    Args:
        image: PIL Image 객체
        path: 저장할 경로 (확장자로 포맷 자동 결정)
        quality: JPEG 품질 (1-100, PNG는 무시됨)

    Note:
        - JPEG로 저장 시 RGBA는 자동으로 RGB로 변환 (흰 배경)
        - 저장 경로의 부모 디렉토리가 없으면 자동 생성

    Example:
        >>> save_image(image, "outputs/result.png")
        >>> save_image(image, "outputs/result.jpg", quality=90)
    """
    path = Path(path)
    # 부모 디렉토리가 없으면 생성
    path.parent.mkdir(parents=True, exist_ok=True)

    # 확장자로 포맷 결정
    ext = path.suffix.lower()
    if ext in [".jpg", ".jpeg"]:
        # JPEG는 투명도를 지원하지 않으므로 RGBA -> RGB 변환
        if image.mode == "RGBA":
            bg = Image.new("RGB", image.size, (255, 255, 255))  # 흰색 배경
            bg.paste(image, mask=image.split()[3])  # 알파 채널을 마스크로 사용
            image = bg
        image.save(path, "JPEG", quality=quality)
    elif ext == ".png":
        image.save(path, "PNG")  # PNG는 투명도 지원
    else:
        image.save(path)  # 기본 포맷으로 저장

    print(f"✓ 이미지 저장 완료: {path.name}")


def get_device() -> torch.device:
    """
    사용 가능한 최적의 디바이스를 반환합니다 (CUDA 또는 CPU).

    CUDA가 사용 가능하면 GPU를, 아니면 CPU를 선택합니다.
    GPU 정보(모델명, VRAM 크기)도 함께 출력합니다.

    Returns:
        torch.device 객체 ('cuda' 또는 'cpu')

    Example:
        >>> device = get_device()
        ✓ Using device: cuda (NVIDIA GeForce RTX 3090)
          Available VRAM: 24.00 GB
    """
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"✓ 사용 디바이스: {device} ({torch.cuda.get_device_name(0)})")
        print(
            f"  사용 가능 VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB"
        )
    else:
        device = torch.device("cpu")
        print("⚠ 사용 디바이스: CPU (CUDA 사용 불가)")

    return device


def print_gpu_memory():
    """
    현재 GPU 메모리 사용량을 출력합니다.

    할당된(Allocated) 메모리와 예약된(Reserved) 메모리를 GB 단위로 표시합니다.
    - Allocated: 실제 텐서가 사용 중인 메모리
    - Reserved: PyTorch가 캐시로 보유한 메모리

    Example:
        >>> print_gpu_memory()
        GPU 메모리 - 할당됨: 8.24 GB, 예약됨: 10.15 GB
    """
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated(0) / 1024**3  # 바이트 -> GB
        reserved = torch.cuda.memory_reserved(0) / 1024**3
        print(f"  GPU 메모리 - 할당됨: {allocated:.2f} GB, 예약됨: {reserved:.2f} GB")
    else:
        print("  GPU 사용 불가")
