"""
segmentation_engine.py

GCP 환경 배포용 하이브리드 세그멘테이션 엔진
- 주요 기능: 상품 이미지 배경 제거 (누끼)
- 모델: BiRefNet (Fallback: RMBG-1.4)
- 특징: CLAHE 전처리, 정교한 마스크 후처리(Clamp, Morph, Feather)
- 튜닝된 파라미터(v5)를 그대로 유지하여 최적의 엣지 품질 보장
"""

import os
import gc
import logging
import traceback
from pathlib import Path
from typing import Optional, Tuple

import torch
import numpy as np
import cv2
from PIL import Image, ImageFilter

# -----------------------------------------------------------------------------
# 로깅 및 라이브러리 설정
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("SegmentationEngine")

try:
    from transformers import AutoModelForImageSegmentation
    AI_AVAILABLE = True
except ImportError:
    logger.error("transformers 라이브러리가 설치되지 않았습니다.")
    AI_AVAILABLE = False

# -----------------------------------------------------------------------------
# 설정 및 상수
# -----------------------------------------------------------------------------
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# 사용자 튜닝 파라미터 (v5 값 유지)
CFG = {
    # 1) CLAHE: 대비가 낮은 경계선 강화
    "USE_CLAHE": True,
    "CLAHE_CLIP_LIMIT": 2.5,
    "CLAHE_TILE_GRID": (8, 8),

    # 2) 임계값: 흐릿한 경계 제거 (타이트한 엣지)
    "ALPHA_LOW_CUT": 60,
    "ALPHA_HIGH_CUT": 235,

    # 3) 모폴로지: 구멍 메우기 (확장 방지를 위해 Dilate 0 설정 유지)
    "USE_MORPH": True,
    "MORPH_CLOSE_KERNEL": 15,
    "MORPH_DILATE_KERNEL": 0,
    "MORPH_DILATE_ITER": 1,

    # 4) 페더링: 엣지 부드럽게 처리 (1.0 유지)
    "FINAL_FEATHER_RADIUS": 1.0,
    "MID_SOFTEN_ENABLE": True,
    "MID_RANGE": (60, 200),
    "MID_SOFTEN_GAIN": 0.92
}

# -----------------------------------------------------------------------------
# 유틸리티 함수
# -----------------------------------------------------------------------------
def apply_clahe_rgb(img_pil: Image.Image) -> Image.Image:
    """
    CLAHE 적용: LAB 색상 공간에서 L 채널만 강조하여 색감 변화 없이 경계 강화
    """
    img = np.array(img_pil)
    lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)

    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(
        clipLimit=float(CFG["CLAHE_CLIP_LIMIT"]),
        tileGridSize=tuple(CFG["CLAHE_TILE_GRID"])
    )
    cl = clahe.apply(l)
    merged = cv2.merge((cl, a, b))
    merged = cv2.cvtColor(merged, cv2.COLOR_LAB2RGB)

    return Image.fromarray(merged)


def postprocess_mask_hybrid(out: torch.Tensor, size_wh: Tuple[int, int]) -> Image.Image:
    """
    하이브리드 마스크 후처리 (v5 로직)
    """
    W, H = size_wh

    # 1. 원본 마스크 추출 (Sigmoid -> 0~255)
    mask = torch.sigmoid(out)[0, 0].detach().cpu().numpy()
    mask = (mask * 255.0).astype(np.uint8)

    # 2. 리사이즈 (OpenCV Lanczos4 사용으로 엣지 보존)
    mask = cv2.resize(mask, (W, H), interpolation=cv2.INTER_LANCZOS4)

    # 3. 클램프 (흐릿한 영역 제거)
    low = int(CFG["ALPHA_LOW_CUT"])
    high = int(CFG["ALPHA_HIGH_CUT"])
    mask[mask < low] = 0
    mask[mask > high] = 255

    # 4. 모폴로지 (구멍 메우기)
    if CFG["USE_MORPH"]:
        k_close = int(CFG["MORPH_CLOSE_KERNEL"])
        if k_close > 1:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_close, k_close))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        k_dilate = int(CFG["MORPH_DILATE_KERNEL"])
        if k_dilate >= 3:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_dilate, k_dilate))
            mask = cv2.dilate(mask, kernel, iterations=int(CFG["MORPH_DILATE_ITER"]))

    # 5. 중간값 부드럽게 처리
    if CFG["MID_SOFTEN_ENABLE"]:
        lo, hi = CFG["MID_RANGE"]
        mid = (mask > lo) & (mask < hi)
        mask[mid] = np.clip(
            mask[mid].astype(np.float32) * float(CFG["MID_SOFTEN_GAIN"]), 0, 255
        ).astype(np.uint8)

    # 6. 페더링 (최종 블러)
    mask_pil = Image.fromarray(mask).convert("L")
    r = float(CFG["FINAL_FEATHER_RADIUS"])
    if r > 0:
        mask_pil = mask_pil.filter(ImageFilter.GaussianBlur(radius=r))

    return mask_pil


class ProductSegmentationEngine:
    """
    대시보드용 상품 누끼(Segmentation) 엔진 클래스
    """
    def __init__(self):
        self._cache = {}
        logger.info(f"Segmentation 엔진 초기화 완료 (Device: {DEVICE})")

    def unload(self):
        """GPU 메모리 정리"""
        for k in list(self._cache.keys()):
            del self._cache[k]
        if DEVICE == "cuda":
            gc.collect()
            torch.cuda.empty_cache()
        logger.info("메모리 정리 완료 (Unload)")

    def _load_model(self, repo: str):
        """모델 로드 및 캐싱"""
        if repo in self._cache:
            return self._cache[repo]

        logger.info(f"모델 로딩 중: {repo}")
        model = AutoModelForImageSegmentation.from_pretrained(
            repo, trust_remote_code=True
        ).to(DEVICE).eval()

        self._cache[repo] = model
        return model

    def _run_inference(self, img_pil: Image.Image, repo: str):
        """추론 실행 공통 함수"""
        model = self._load_model(repo)

        # CLAHE 전처리 적용 여부
        if CFG["USE_CLAHE"]:
            img_input = apply_clahe_rgb(img_pil)
        else:
            img_input = img_pil

        # 입력 전처리 (1024x1024 리사이즈)
        x = img_input.resize((1024, 1024), Image.LANCZOS)
        x = torch.from_numpy(np.array(x)).permute(2, 0, 1).float() / 255.0
        x = x.unsqueeze(0).to(DEVICE)

        # 추론
        with torch.no_grad():
            out = model(x)

        # 모델별 출력 형식 대응
        if hasattr(out, "logits"):
            return out.logits
        elif isinstance(out, (list, tuple)):
            return out[-1]
        return out

    def process(self, img_path: str, save_dir: Optional[str] = None) -> str:
        """
        이미지 경로를 받아 배경을 제거하고 저장된 경로를 반환합니다.
        
        Args:
            img_path (str): 입력 이미지 경로
            save_dir (str, optional): 저장할 디렉토리 (기본값: outputs/fg_cut)
            
        Returns:
            str: 처리된 이미지(RGBA)가 저장된 경로
        """
        try:
            path_obj = Path(img_path)
            if not path_obj.exists():
                raise FileNotFoundError(f"파일을 찾을 수 없습니다: {img_path}")

            # 1. 이미지 로드
            img = Image.open(path_obj).convert("RGB")
            W, H = img.size
            logger.info(f"누끼 처리 시작: {path_obj.name} ({W}x{H})")

            # 2. 모델 추론 (BiRefNet 우선 -> 실패 시 RMBG)
            try:
                out = self._run_inference(img, "ZhengPeng7/BiRefNet")
            except Exception as e:
                logger.warning(f"BiRefNet 실패, RMBG로 재시도: {e}")
                out = self._run_inference(img, "briaai/RMBG-1.4")

            # 3. 마스크 후처리
            mask = postprocess_mask_hybrid(out, (W, H))

            # 4. 배경 제거 적용 (RGBA)
            fg = img.convert("RGBA")
            fg.putalpha(mask)

            # 5. 저장
            if save_dir:
                out_dir = Path(save_dir)
            else:
                out_dir = Path("outputs/fg_cut")
            
            out_dir.mkdir(parents=True, exist_ok=True)
            
            # 원본 파일명 유지하며 _fg 접미사 추가 (선택 사항)
            # 여기서는 편의상 원본 이름 그대로 사용하거나, 필요시 변경 가능
            save_path = out_dir / f"{path_obj.stem}.png"
            
            fg.save(save_path)
            logger.info(f"누끼 저장 완료: {save_path}")
            
            # 메모리 정리
            self.unload()
            
            return str(save_path)

        except Exception as e:
            logger.error(f"세그멘테이션 처리 중 오류: {e}")
            traceback.print_exc()
            self.unload()
            raise e

# -----------------------------------------------------------------------------
# 실행 진입점 (테스트용)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # 테스트 경로 설정
    TEST_INPUT_DIR = Path("data/inputs")
    TEST_OUTPUT_DIR = Path("outputs/fg_cut")
    
    if not TEST_INPUT_DIR.exists():
        print(f"테스트 폴더가 없습니다: {TEST_INPUT_DIR}")
    else:
        engine = ProductSegmentationEngine()
        files = sorted(TEST_INPUT_DIR.glob("*.*"))
        
        for f in files:
            if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                result_path = engine.process(str(f), str(TEST_OUTPUT_DIR))
                print(f"Processed: {result_path}")

# Backward compatibility alias
SegmentationModel = ProductSegmentationEngine
