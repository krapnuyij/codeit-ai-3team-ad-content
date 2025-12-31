import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

import os
import gc
import base64
import psutil
import torch
try:
    import pynvml as pynvml  # nvidia-ml-py 패키지
except ImportError:
    pynvml = None
from io import BytesIO
from typing import List
from PIL import Image, ImageFilter
from config import logger

def pil_to_base64(image: Image.Image) -> str:
    """PIL 이미지를 Base64 문자열로 변환합니다."""
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def base64_to_pil(b64_str: str) -> Image.Image:
    """Base64 문자열을 PIL 이미지로 변환합니다."""
    return Image.open(BytesIO(base64.b64decode(b64_str))).convert("RGB")

def flush_gpu():
    """GPU 메모리를 강제로 정리합니다 (Load/Unload 핵심)."""
    gc.collect()
    torch.cuda.empty_cache()
    try:
        torch.cuda.ipc_collect()
    except RuntimeError:
        pass

def get_system_metrics():
    """
    현재 시스템(CPU, RAM, GPU, VRAM) 상태를 반환합니다.
    
    Returns:
        dict: CPU 사용량, RAM 사용량(현재 GB/최대 GB), GPU 사용률, VRAM 사용량(현재 GB/최대 GB)
    """
    cpu_usage = psutil.cpu_percent()
    ram_info = psutil.virtual_memory()
    
    gpu_metrics = []
    try:
        if pynvml:
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(gpu_name, bytes):
                    gpu_name = gpu_name.decode('utf-8')
                
                vram_used_gb = mem_info.used / 1024**3
                vram_total_gb = mem_info.total / 1024**3
                
                gpu_metrics.append({
                    "index": i,
                    "name": gpu_name,
                    "gpu_util": util.gpu,
                    "vram_used_gb": round(vram_used_gb, 2),
                    "vram_total_gb": round(vram_total_gb, 2),
                    "vram_percent": round((vram_used_gb / vram_total_gb * 100), 1) if vram_total_gb > 0 else 0.0
                })
            pynvml.nvmlShutdown()
        else:
            logger.warning("pynvml 라이브러리를 사용할 수 없습니다.")
    except Exception as e:
        logger.error(f"GPU Monitor Error (GPU 모니터링 오류): {e}")
        import traceback
        logger.error(traceback.format_exc())

    ram_used_gb = ram_info.used / 1024**3
    ram_total_gb = ram_info.total / 1024**3
    
    return {
        "cpu_percent": cpu_usage,
        "ram_used_gb": round(ram_used_gb, 2),
        "ram_total_gb": round(ram_total_gb, 2),
        "ram_percent": ram_info.percent,
        "gpu_info": gpu_metrics
    }

def get_fonts_dir() -> str:
    """폰트 디렉토리 경로를 반환합니다."""
    # 현재 파일(utils.py)의 디렉토리
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, "fonts")

def get_available_fonts() -> List[str]:
    """
    사용 가능한 폰트 파일 이름 목록을 반환합니다.
    하위 디렉토리까지 재귀적으로 검색합니다.
    
    Returns:
        List[str]: 폰트 파일의 상대 경로 리스트 (예: '나눔고딕/NanumGothic.ttf')
    """
    fonts_dir = get_fonts_dir()
    if not os.path.exists(fonts_dir):
        return []
    
    font_files = []
    for root, dirs, files in os.walk(fonts_dir):
        for file in files:
            if file.lower().endswith(('.ttf', '.otf')):
                # fonts_dir로부터의 상대 경로 저장
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, fonts_dir)
                font_files.append(rel_path)
    
    return sorted(font_files)

def get_font_path(font_name: str) -> str:
    """
    폰트 파일의 전체 경로를 반환합니다.
    
    Args:
        font_name (str): 폰트 파일 경로 (get_available_fonts에서 반환된 상대 경로)
        
    Returns:
        str: 폰트 파일 전체 경로. 존재하지 않으면 첫 번째 사용 가능한 폰트 반환.
    """
    fonts_dir = get_fonts_dir()
    # 입력받은 font_name이 절대경로일 수도 있고, 파일명만 있을 수도 있음.
    # 우선 fonts_dir와 결합하여 확인
    font_path = os.path.join(fonts_dir, font_name)
    
    if os.path.exists(font_path) and os.path.isfile(font_path):
        return font_path
    
    # 혹시 파일명만 넘어왔을 경우, 검색
    available = get_available_fonts()
    for rel_path in available:
        if os.path.basename(rel_path) == font_name:
             return os.path.join(fonts_dir, rel_path)

    # 그래도 없으면 기본값 (NanumMyeongjo-YetHangul.ttf 우선 시도)
    yet_hangul = "NanumMyeongjo-YetHangul.ttf"
    if available:
        # 1순위: NanumMyeongjo-YetHangul.ttf 찾기
        for rel_path in available:
            if os.path.basename(rel_path) == yet_hangul:
                # logger.info(f"Font '{font_name}' not found. Using '{yet_hangul}' instead.")
                return os.path.join(fonts_dir, rel_path)
        
        # 2순위: 그냥 첫 번째 폰트
        logger.warning(f"Font '{font_name}' not found. Using '{available[0]}' instead.")
        return os.path.join(fonts_dir, available[0])
    
    raise FileNotFoundError("No fonts available in 'fonts' directory.")

def pil_canny_edge(image):
    """
    PIL 이미지를 입력받아 Canny Edge 처리된 이미지를 반환합니다.
    
    Args:
        image (Image.Image): 입력 이미지
        
    Returns:
        Image.Image: 엣지 처리가 완료된 이미지
    """
    gray = image.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edges = edges.point(lambda x: 255 if x > 30 else 0)
    return edges.convert("RGB")
