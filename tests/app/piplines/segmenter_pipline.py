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

import traceback
from pathlib import Path

import torch
import numpy as np
import cv2
from PIL import Image, ImageFilter
from transformers import AutoModelForImageSegmentation

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
    "ALPHA_LOW_CUT": 20,     # 약한 알파 제거
    "ALPHA_HIGH_CUT": 235,   # 강한 알파 고정

    # 3) Morphology (seg3 feature but lighter)
    "USE_MORPH": True,
    "MORPH_CLOSE_KERNEL": 7,  # 5~9
    "MORPH_DILATE_KERNEL": 0, # 0이면 비활성, 3 이상부터 의미
    "MORPH_DILATE_ITER": 1,

    # 4) Feather / Blur
    "FINAL_FEATHER_RADIUS": 2.0,  # 1~3
    "MID_SOFTEN_ENABLE": True,
    "MID_RANGE": (60, 200),
    "MID_SOFTEN_GAIN": 0.92,

    # 5) Output
    "SAVE_DEBUG_MASK": True,
}


# Utils
def flush_gpu():
    if DEVICE == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()


def load_model(repo: str):
    """
    BiRefNet / RMBG 로딩 (캐싱)
    """
    if repo in _cached_models:
        return _cached_models[repo]

    model = AutoModelForImageSegmentation.from_pretrained(
        repo, trust_remote_code=True
    ).to(DEVICE).eval()

    _cached_models[repo] = model
    return model


def apply_clahe_rgb(img_pil: Image.Image) -> Image.Image:
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


def run_inference(img_pil: Image.Image, repo: str):
    """
    BiRefNet / RMBG 공통 추론
    - 출력 타입 (logits / list / tuple) 모두 대응
    """
    model = load_model(repo)

    # Optional CLAHE
    img_input = apply_clahe_rgb(img_pil) if CFG["USE_CLAHE"] else img_pil

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

    return out


def postprocess_mask_hybrid(out: torch.Tensor, size_wh):
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
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_close, k_close))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        k_dilate = int(CFG["MORPH_DILATE_KERNEL"])
        if k_dilate >= 3:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_dilate, k_dilate))
            mask = cv2.dilate(mask, kernel, iterations=int(CFG["MORPH_DILATE_ITER"]))

    # (5) mid soften
    if CFG["MID_SOFTEN_ENABLE"]:
        lo, hi = CFG["MID_RANGE"]
        mid = (mask > lo) & (mask < hi)
        mask[mid] = np.clip(
            mask[mid].astype(np.float32) * float(CFG["MID_SOFTEN_GAIN"]),
            0, 255
        ).astype(np.uint8)

    # (6) feather
    mask_pil = Image.fromarray(mask).convert("L")
    r = float(CFG["FINAL_FEATHER_RADIUS"])
    if r > 0:
        mask_pil = mask_pil.filter(ImageFilter.GaussianBlur(radius=r))

    return mask_pil


# Public API
def segment_image(img_pil: Image.Image) -> tuple[Image.Image, Image.Image]:
    """
    입력 PIL 이미지 -> (foreground_rgba, mask_pil) 반환
    """
    img = img_pil.convert("RGB")
    W, H = img.size

    try:
        out = run_inference(img, "ZhengPeng7/BiRefNet")
    except Exception:
        print(traceback.format_exc())
        out = run_inference(img, "briaai/RMBG-1.4")

    mask = postprocess_mask_hybrid(out, (W, H))

    fg = img.convert("RGBA")
    fg.putalpha(mask)

    return fg, mask


def segment_one(img_path: Path):
    img = Image.open(img_path).convert("RGB")

    fg, mask = segment_image(img)

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


def main():
    files = sorted(INPUT_DIR.glob("*.*"))
    assert files, "data/inputs 폴더에 이미지가 없습니다."

    for p in files:
        segment_one(p)

    flush_gpu()


if __name__ == "__main__":
    main()
