"""
시스템 리소스 모니터링 모듈.

CPU, RAM, GPU, VRAM 사용량을 추적하고 GPU 메모리를 정리합니다.
"""

import gc
from typing import Dict, List, Any

import psutil
import torch

try:
    import pynvml
except ImportError:
    pynvml = None

from config import logger


def flush_gpu() -> None:
    """
    GPU 메모리를 강제로 정리합니다.
    
    모델 Load/Unload 시 캐시를 비우고 메모리를 확보하는 핵심 함수입니다.
    """
    gc.collect()
    torch.cuda.empty_cache()
    try:
        torch.cuda.ipc_collect()
    except RuntimeError:
        pass


def get_system_metrics() -> Dict[str, Any]:
    """
    현재 시스템(CPU, RAM, GPU, VRAM) 상태를 반환합니다.
    
    Returns:
        dict: 다음 키를 포함하는 딕셔너리
            - cpu_percent (float): CPU 사용률 (%)
            - ram_used_gb (float): 사용 중인 RAM (GB)
            - ram_total_gb (float): 전체 RAM (GB)
            - ram_percent (float): RAM 사용률 (%)
            - gpu_info (List[Dict]): GPU 정보 리스트
                - index (int): GPU 인덱스
                - name (str): GPU 이름
                - gpu_util (int): GPU 사용률 (%)
                - vram_used_gb (float): 사용 중인 VRAM (GB)
                - vram_total_gb (float): 전체 VRAM (GB)
                - vram_percent (float): VRAM 사용률 (%)
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
