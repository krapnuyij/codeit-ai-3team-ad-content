"""
segmenter_pipeline.py

Hybrid Segmentation Pipeline (v4)
- Base: BiRefNet (fallback RMBG)
- Optional: CLAHE contrast enhancement (white container / low-contrast boundary)
- Mask post-processing:
  - Soft clamp (remove weak alpha)
  - Light morphology (close) to fill tiny holes
  - Edge feather (blur)
  - Anti-box / anti-halo tuning

Usage:
- 다른 파이프라인에서 import 해서 사용
- CLI 실행도 가능하게 main 포함
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents
sys.path.insert(0, str(project_root))

import traceback
import warnings

import cv2
import numpy as np
import torch
from helper_dev_utils import get_auto_logger
from PIL import Image, ImageFilter
from torchvision import transforms
from transformers import AutoModelForImageSegmentation

from config import DEVICE, MODEL_IDS
from services.monitor import log_gpu_memory
from utils import flush_gpu

# timm 라이브러리 deprecation 경고 억제
warnings.filterwarnings("ignore", category=FutureWarning, module="timm")

logger = get_auto_logger()

# Paths (로컬 실행용)
INPUT_DIR = Path("data/inputs")
OUT_FG = Path("outputs/fg_cut")
OUT_MASK = Path("outputs/fg_mask")
OUT_FG.mkdir(parents=True, exist_ok=True)
OUT_MASK.mkdir(parents=True, exist_ok=True)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
_cached_models = {}


# Config (튜닝 포인트)
CFG = {
    # 1) CLAHE (seg3 feature)
    "USE_CLAHE": True,
    "CLAHE_CLIP_LIMIT": 2.5,
    "CLAHE_TILE_GRID": (8, 8),
    # 2) Clamp (seg2 feature)
    "ALPHA_LOW_CUT": 20,  # 약한 알파 제거
    "ALPHA_HIGH_CUT": 235,  # 강한 알파 고정
    # 3) Morphology (seg3 feature but lighter)
    "USE_MORPH": True,
    "MORPH_CLOSE_KERNEL": 7,  # 5~9
    "MORPH_DILATE_KERNEL": 0,  # 0이면 비활성, 3 이상부터 의미
    "MORPH_DILATE_ITER": 1,
    # 4) Feather / Blur
    "FINAL_FEATHER_RADIUS": 2.0,  # 1~3
    "MID_SOFTEN_ENABLE": True,
    "MID_RANGE": (60, 200),
    "MID_SOFTEN_GAIN": 0.92,
    # 5) Output
    "SAVE_DEBUG_MASK": True,
}


class SegmentationModel:
    """
    BiRefNet을 사용하여 이미지 세그멘테이션(누끼 따기)을 수행하는 클래스입니다.
    """

    def __init__(self):
        self.device = DEVICE

    def load_model(self, repo: str):
        """
        BiRefNet / RMBG 로딩 (캐싱)
        """
        if repo in _cached_models:
            return _cached_models[repo]

        model = (
            AutoModelForImageSegmentation.from_pretrained(repo, trust_remote_code=True)
            .to(DEVICE)
            .eval()
        )

        _cached_models[repo] = model
        return model

    def apply_clahe_rgb(self, img_pil: Image.Image) -> Image.Image:
        """
        CLAHE 적용: 흰 용기/밝은 배경 경계 강화
        """
        img = np.array(img_pil)
        lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)

        clahe = cv2.createCLAHE(
            clipLimit=float(CFG["CLAHE_CLIP_LIMIT"]),
            tileGridSize=tuple(CFG["CLAHE_TILE_GRID"]),
        )
        cl = clahe.apply(l)

        merged = cv2.merge((cl, a, b))
        merged = cv2.cvtColor(merged, cv2.COLOR_LAB2RGB)
        return Image.fromarray(merged)

    def run_inference(self, img_pil: Image.Image, repo: str):
        """
        BiRefNet / RMBG 공통 추론
        - 출력 타입 (logits / list / tuple) 모두 대응
        """
        model = self.load_model(repo)

        # Optional CLAHE
        img_input = self.apply_clahe_rgb(img_pil) if CFG["USE_CLAHE"] else img_pil

        x = img_input.resize((1024, 1024), Image.LANCZOS)
        x = torch.from_numpy(np.array(x)).permute(2, 0, 1).float() / 255.0
        x = x.unsqueeze(0).to(DEVICE)

        with torch.no_grad():
            out = model(x)

        # 출력 타입 대응
        if hasattr(out, "logits"):
            out = out.logits
        elif isinstance(out, (list, tuple)):
            out = out[-1]

        return out, model

    def postprocess_mask_hybrid(self, out: torch.Tensor, size_wh):
        """
        Hybrid mask post-processing
        - seg2: clamp + feather + mid soften
        - seg3: morphology 최소 적용
        """
        W, H = size_wh

        # (1) raw mask
        mask = torch.sigmoid(out)[0, 0].detach().cpu().numpy()
        mask = (mask * 255.0).astype(np.uint8)

        # (2) resize with OpenCV (edge 유지)
        mask = cv2.resize(mask, (W, H), interpolation=cv2.INTER_LANCZOS4)

        # (3) clamp
        low = int(CFG["ALPHA_LOW_CUT"])
        high = int(CFG["ALPHA_HIGH_CUT"])
        mask[mask < low] = 0
        mask[mask > high] = 255

        # (4) light morphology
        if CFG["USE_MORPH"]:
            k_close = int(CFG["MORPH_CLOSE_KERNEL"])
            if k_close > 1:
                kernel = cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE, (k_close, k_close)
                )
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            k_dilate = int(CFG["MORPH_DILATE_KERNEL"])
            if k_dilate >= 3:
                kernel = cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE, (k_dilate, k_dilate)
                )
                mask = cv2.dilate(
                    mask, kernel, iterations=int(CFG["MORPH_DILATE_ITER"])
                )

        # (5) mid soften
        if CFG["MID_SOFTEN_ENABLE"]:
            lo, hi = CFG["MID_RANGE"]
            mid = (mask > lo) & (mask < hi)
            mask[mid] = np.clip(
                mask[mid].astype(np.float32) * float(CFG["MID_SOFTEN_GAIN"]), 0, 255
            ).astype(np.uint8)

        # (6) feather
        mask_pil = Image.fromarray(mask).convert("L")
        r = float(CFG["FINAL_FEATHER_RADIUS"])
        if r > 0:
            mask_pil = mask_pil.filter(ImageFilter.GaussianBlur(radius=r))

        return mask_pil

    # Public API
    def segment_image(self, img_pil: Image.Image) -> tuple[Image.Image, Image.Image]:
        """
        입력 PIL 이미지 -> (foreground_rgba, mask_pil) 반환
        """
        logger.debug("[Engine] Loading BiRefNet... (BiRefNet 모델 로딩 중)")
        flush_gpu()

        img = img_pil.convert("RGB")
        W, H = img.size

        try:
            out, model = self.run_inference(img, "ZhengPeng7/BiRefNet")
        except Exception:
            print(traceback.format_exc())
            out, model = self.run_inference(img, "briaai/RMBG-1.4")

        mask = self.postprocess_mask_hybrid(out, (W, H))

        fg = img.convert("RGBA")
        fg.putalpha(mask)

        # 리소스 정리
        del model

        flush_gpu()

        return fg, mask

    def segment_one(self, img_path: Path):
        img = Image.open(img_path).convert("RGB")

        fg, mask = self.segment_image(img)

        fg_path = OUT_FG / f"{img_path.stem}_fg.png"
        mask_path = OUT_MASK / f"{img_path.stem}_mask.png"

        fg.save(fg_path)
        mask.save(mask_path)

        if CFG["SAVE_DEBUG_MASK"]:
            bg = Image.new("RGB", img.size, "white")
            preview = bg.copy()
            preview.paste(img, mask=mask)
            preview.save(OUT_MASK / f"{img_path.stem}_preview.png")

        print("Saved:", fg_path.name, mask_path.name)

    def run(self, image: Image.Image) -> tuple[Image.Image, Image.Image]:
        """
        이미지의 배경을 제거합니다.

        Args:
            image (Image.Image): 입력 이미지

        Returns:
            tuple[Image.Image, Image.Image]: (배경 제거된 이미지, 마스크)
        """
        # logger.debug("[Engine] Loading BiRefNet... (BiRefNet 모델 로딩 중)")
        # flush_gpu()

        # model = (
        #     AutoModelForImageSegmentation.from_pretrained(
        #         MODEL_IDS["SEG"], trust_remote_code=True
        #     )
        #     .to(self.device)
        #     .eval()
        # )

        # W, H = image.size
        # # 고해상도 처리를 위해 리사이즈 (필요 시 조정 가능)
        # img_resized = image.resize((1024, 1024), Image.LANCZOS)

        # transform = transforms.Compose(
        #     [
        #         transforms.ToTensor(),
        #         transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        #     ]
        # )

        # input_tensor = transform(img_resized).unsqueeze(0).to(self.device)

        # with torch.no_grad():
        #     preds = model(input_tensor)[-1].sigmoid().cpu()

        # pred = preds[0].squeeze()
        # mask = transforms.ToPILImage()(pred).resize((W, H), Image.LANCZOS)

        # # 마스크 이진화 (Thresholding)
        # mask = mask.point(lambda x: 255 if x > 128 else 0)

        # result = image.copy()
        # result.putalpha(mask)

        # # 리소스 정리
        # del model, input_tensor
        # flush_gpu()

        # return result, mask

        fg, mask = self.segment_image(image)

        return fg, mask

    def unload(self) -> None:
        """
        명시적으로 모델 리소스를 정리합니다.

        현재 BiRefNet은 run() 호출 시마다 로드/언로드하므로
        별도 정리 작업이 불필요하지만, 인터페이스 통일을 위해 구현합니다.
        """
        log_gpu_memory("BiRefNet unload (no-op)")
        flush_gpu()
        logger.info("BiRefNet unloaded")
