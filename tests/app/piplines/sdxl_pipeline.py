"""
compose_engine.py

Compose Pipeline (v8)
- user_bg_mode: reuse / regen
- regen:
  - BLIP caption -> palette -> regen prompt (일관화)
  - stats 기반 steps/guidance 안정화
  - SDXL base 생성
- harmonization:
  - SDXL ControlNet Inpaint (Canny)
  - strength 낮춰 배경 보호 + control_scale 높여 구조 유지
  - recovery mask로 제품 원본 질감 복구

Usage:
- 다른 API 라우트에서 호출하도록 함수화
- 로컬 배치 실행도 main 포함
"""

import os
import time
from pathlib import Path

import torch
import numpy as np
import cv2
from PIL import Image, ImageFilter

# Optional imports
try:
    from diffusers import (
        StableDiffusionXLControlNetInpaintPipeline,
        ControlNetModel,
        StableDiffusionXLPipeline,
    )
    from transformers import BlipProcessor, BlipForConditionalGeneration
    AI_AVAILABLE = True
except ImportError:
    print("Warning: diffusers/transformers not found. AI disabled.")
    AI_AVAILABLE = False

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
_cache = {}

# Paths (로컬 실행용)
INPUT_FG = Path("outputs/fg_cut")
INPUT_MASK = Path("outputs/fg_mask")
USER_BG_DIR = Path("data/backgrounds")
OUT_COMP = Path("outputs/compose")
OUT_COMP.mkdir(parents=True, exist_ok=True)


# Prompt / Negative Prompt
NEG_NO_TEXT_STRONG = (
    "text, letters, typography, words, caption, subtitle, "
    "sign, signage, signboard, shop sign, billboard, banner, poster, menu, "
    "logo, watermark, label, sticker, price tag, numbers, digits, QR code, barcode, "
    "cartoon, illustration, low quality, distorted, ugly, deformed"
)

NEG_SD_DEFAULT = (
    "cartoon, illustration, low quality, distorted, watermark, logo"
)


# Basic utils
def load_image_any(path: Path) -> Image.Image:
    img = Image.open(path)
    return img.convert("RGB")


def load_rgba_any(path: Path) -> Image.Image:
    img = Image.open(path)
    return img.convert("RGBA")


def find_any_background_image(bg_dir: Path) -> Path | None:
    exts = ["*.jpg", "*.jpeg", "*.png", "*.webp"]
    files = []
    for e in exts:
        files.extend(bg_dir.glob(e))
    files = sorted(files)
    return files[0] if files else None


def ensure_size(img: Image.Image, size=(1024, 1024)) -> Image.Image:
    if img.size != size:
        img = img.resize(size, Image.LANCZOS)
    return img


# Background stats + palette
def analyze_bg_stats(bg: Image.Image) -> dict:
    gray = np.array(bg.convert("L"))
    mean_lum = float(gray.mean())
    std_lum = float(gray.std())

    hsv = np.array(bg.convert("HSV"))
    mean_sat = float(hsv[..., 1].mean())

    return {"mean_lum": mean_lum, "std_lum": std_lum, "mean_sat": mean_sat}


def extract_color_palette(bg: Image.Image, k=5) -> list[tuple[int, int, int]]:
    small = bg.copy().resize((256, 256), Image.BILINEAR)
    arr = np.array(small).reshape(-1, 3).astype(np.float32)

    if arr.shape[0] > 50000:
        idx = np.random.choice(arr.shape[0], 50000, replace=False)
        arr = arr[idx]

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1.0)
    flags = cv2.KMEANS_PP_CENTERS

    _, labels, centers = cv2.kmeans(arr, k, None, criteria, 10, flags)
    centers = np.clip(centers, 0, 255).astype(np.uint8)

    counts = np.bincount(labels.flatten(), minlength=k)
    order = np.argsort(-counts)

    return [tuple(map(int, centers[i])) for i in order]


def palette_to_prompt_text(palette: list[tuple[int, int, int]]) -> str:
    hexes = [f"#{r:02x}{g:02x}{b:02x}" for (r, g, b) in palette]
    return "color palette: " + ", ".join(hexes)


# BLIP captioner
def load_captioner():
    if "captioner" in _cache:
        return _cache["captioner"]

    print("Loading BLIP captioner...")
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained(
        "Salesforce/blip-image-captioning-base",
        torch_dtype=torch.float16
    ).to(DEVICE)

    _cache["captioner"] = (processor, model)
    return processor, model


def analyze_image(image: Image.Image) -> str:
    if not AI_AVAILABLE:
        return "market background"

    processor, model = load_captioner()

    img = image.copy()
    img.thumbnail((512, 512))

    inputs = processor(img, return_tensors="pt").to(DEVICE, torch.float16)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=50)

    caption = processor.decode(out[0], skip_special_tokens=True)
    print("Caption:", caption)
    return caption


# Model loader
def load_model(model_type="controlnet_inpaint"):
    if not AI_AVAILABLE:
        return None

    if model_type in _cache:
        return _cache[model_type]

    if model_type == "controlnet_inpaint":
        print("Loading SDXL ControlNet Inpaint...")
        controlnet = ControlNetModel.from_pretrained(
            "diffusers/controlnet-canny-sdxl-1.0",
            torch_dtype=torch.float16
        ).to(DEVICE)

        pipe = StableDiffusionXLControlNetInpaintPipeline.from_pretrained(
            "diffusers/stable-diffusion-xl-1.0-inpainting-0.1",
            controlnet=controlnet,
            torch_dtype=torch.float16,
            variant="fp16"
        ).to(DEVICE)

    elif model_type == "base":
        print("Loading SDXL Base...")
        pipe = StableDiffusionXLPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            torch_dtype=torch.float16,
            variant="fp16"
        ).to(DEVICE)

    else:
        raise ValueError("model_type must be 'controlnet_inpaint' or 'base'")

    _cache[model_type] = pipe
    return pipe


# ControlNet guide
def get_canny_edge(image: Image.Image) -> Image.Image:
    curr_img = np.array(image.convert("RGB"))
    edges = cv2.Canny(curr_img, 100, 200)
    edges = edges[:, :, None]
    edges = np.concatenate([edges, edges, edges], axis=2)
    return Image.fromarray(edges)


# Presets
PRESETS = {
    "market_tone": (
        "traditional korean market alley background, soft daylight, authentic market mood, "
        "blurred background, ambient occlusion, soft top lighting"
    ),
    "traditional_dry_fish": (
        "rustic wooden tray, woven straw mats background, warm morning sunlight, "
        "korean heritage mood, ambient occlusion, soft top lighting"
    ),
    "clean_market_interior": (
        "modern korean seafood shop, clean white counter top, natural bright lighting, "
        "8k resolution, ambient occlusion, soft top lighting"
    ),
}


# regen prompt builder
def build_regen_prompt(caption: str, palette_text: str) -> str:
    """
    regen prompt 일관화 (텍스트 생성 억제 포함)
    """
    return (
        f"{caption}, "
        f"{palette_text}, "
        f"same vibe and composition as reference photo, "
        f"keep similar lighting and atmosphere, "
        f"photorealistic background, natural perspective, "
        f"soft daylight, shallow depth of field, bokeh, "
        f"clean product advertising background, "
        f"empty space for overlay text later, "
        f"high quality, 8k, "
        f"no text, no letters, no labels, no logo, no watermark"
    )


# SDXL params (regen에서만 사용)
def auto_sdxl_params_from_bg_stats(stats: dict) -> dict:
    mean_lum = stats["mean_lum"]
    std_lum = stats["std_lum"]
    mean_sat = stats["mean_sat"]

    steps = 28
    guidance = 6.0

    if mean_lum > 170:
        steps = 26
        guidance = 4.8

    if mean_lum < 90:
        steps = 32
        guidance = 6.0

    if std_lum > 75:
        guidance -= 0.2

    if mean_sat > 120:
        steps += 2

    steps = int(np.clip(steps, 24, 40))
    guidance = float(np.clip(guidance, 4.0, 7.0))

    return {"num_inference_steps": steps, "guidance_scale": guidance}


# SDXL base generation
def sdxl_generate_background(prompt: str, seed: int, size: tuple[int, int], params: dict) -> Image.Image:
    pipe = load_model("base")
    if pipe is None:
        return Image.new("RGB", size, (240, 240, 240))

    g = torch.Generator(device=DEVICE).manual_seed(seed)

    out = pipe(
        prompt=prompt,
        negative_prompt=f"{NEG_SD_DEFAULT}, {NEG_NO_TEXT_STRONG}",
        generator=g,
        **params
    ).images[0].convert("RGB")

    return out.resize(size, Image.LANCZOS)


def generate_background_from_user_bg(user_bg: Image.Image, seed=42) -> Image.Image:
    caption = analyze_image(user_bg)
    palette = extract_color_palette(user_bg, k=5)
    palette_text = palette_to_prompt_text(palette)

    regen_prompt = build_regen_prompt(caption, palette_text)

    stats = analyze_bg_stats(user_bg)
    params = auto_sdxl_params_from_bg_stats(stats)

    print("Regen prompt:", regen_prompt)
    print("Auto SDXL params:", params)

    bg_gen = sdxl_generate_background(
        prompt=regen_prompt,
        seed=seed,
        size=user_bg.size,
        params=params
    )
    return bg_gen


# Harmonization (ControlNet Inpaint)
def ai_harmonization_pro(background, foreground, pos, prompt, strength=0.12, control_scale=0.8):
    pipe = load_model("controlnet_inpaint")
    if pipe is None:
        out = background.copy().convert("RGBA")
        out.paste(foreground, pos, foreground.split()[3])
        return out

    base_canvas = background.copy().convert("RGB")

    fg_rgb = foreground.convert("RGB")
    fg_mask = foreground.split()[3]
    base_canvas.paste(fg_rgb, pos, fg_mask)

    canny_guide = get_canny_edge(base_canvas)

    full_mask = Image.new("L", background.size, 0)
    full_mask.paste(fg_mask, pos)

    refined_mask = full_mask.filter(ImageFilter.MaxFilter(15))
    refined_mask = refined_mask.filter(ImageFilter.GaussianBlur(10))

    ai_output = pipe(
        prompt=prompt + ", realistic shadows, photorealistic, high quality",
        negative_prompt=f"bad anatomy, {NEG_NO_TEXT_STRONG}",
        image=base_canvas,
        mask_image=refined_mask,
        control_image=canny_guide,
        controlnet_conditioning_scale=control_scale,
        strength=strength,
        guidance_scale=7.5,
        num_inference_steps=30
    ).images[0].convert("RGBA")

    # 제품 원본 복구
    original_fg_rgba = foreground.convert("RGBA")
    recovery_mask = fg_mask.filter(ImageFilter.MinFilter(5))
    recovery_mask = recovery_mask.filter(ImageFilter.GaussianBlur(3))

    final_comp = ai_output.copy()
    final_comp.paste(original_fg_rgba, pos, recovery_mask)
    return final_comp


# Placement
def detect_object_floor(mask_img):
    mask = mask_img.convert("L")
    w, h = mask.size
    arr = mask.load()
    for y in range(h - 1, 0, -1):
        for x in range(w):
            if arr[x, y] > 10:
                return y
    return int(h * 0.9)


def auto_place_on_ground(fg, mask, canvas_size, scale=0.7):
    W, H = canvas_size

    fg_resized = fg.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    mask_resized = mask.resize(fg_resized.size, Image.LANCZOS)

    fw, fh = fg_resized.size
    obj_floor_y = detect_object_floor(mask_resized)

    background_floor = int(H * 0.93)
    x = (W - fw) // 2
    y = background_floor - obj_floor_y
    return fg_resized, (x, y)


# Simple shadow (AI OFF)
def create_simple_shadow(fg_mask, pos, canvas_size):
    shadow_canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))

    shadow = fg_mask.resize((fg_mask.width, int(fg_mask.height * 0.3)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))

    empty_black = Image.new("RGBA", shadow.size, (0, 0, 0, 255))
    empty_black.putalpha(shadow.point(lambda p: p * 0.4))

    sx = pos[0] + 10
    sy = pos[1] + int(fg_mask.height * 0.85)

    shadow_canvas.paste(empty_black, (sx, sy), empty_black)
    return shadow_canvas


# Main compose function
def process_composition(
    fg_path,
    mask_path=None,
    user_bg_path=None,
    use_ai_gen=True,
    preset_key="market_tone",
    user_bg_mode="reuse",   # reuse | regen
    seed=42
):
    fg = load_rgba_any(Path(fg_path))

    if mask_path and os.path.exists(mask_path):
        mask = Image.open(mask_path).convert("L")
    else:
        mask = fg.split()[3]

    final_prompt = ""
    ai_strength = 0.12

    # Case 1) user background exists
    if user_bg_path and os.path.exists(user_bg_path):
        bg_user = ensure_size(load_image_any(Path(user_bg_path)))

        if user_bg_mode == "reuse":
            bg = bg_user
            if use_ai_gen:
                cap = analyze_image(bg)
                final_prompt = f"{cap}, realistic lighting, photorealistic, high quality"
                ai_strength = 0.10

        elif user_bg_mode == "regen":
            bg = generate_background_from_user_bg(bg_user, seed=seed)
            final_prompt = PRESETS.get(preset_key, PRESETS["market_tone"])
            ai_strength = 0.15

        else:
            raise ValueError("user_bg_mode must be 'reuse' or 'regen'")

    # Case 2) no background -> preset
    else:
        prompt_text = PRESETS.get(preset_key, PRESETS["market_tone"])
        params = {"num_inference_steps": 25, "guidance_scale": 4.5}

        bg = sdxl_generate_background(
            prompt=prompt_text,
            seed=seed,
            size=(1024, 1024),
            params=params
        )

        final_prompt = prompt_text
        ai_strength = 0.22

    # placement
    fg_res, pos = auto_place_on_ground(fg, mask, bg.size)

    # compose
    if use_ai_gen:
        final_image = ai_harmonization_pro(
            bg, fg_res, pos,
            final_prompt,
            strength=ai_strength,
            control_scale=0.8
        )
    else:
        final_image = bg.copy().convert("RGBA")
        shadow_layer = create_simple_shadow(fg_res.split()[3], pos, bg.size)
        final_image = Image.alpha_composite(final_image, shadow_layer)
        final_image.paste(fg_res, pos, fg_res.split()[3])

    return final_image


# Local batch runner
def main():
    fg_files = sorted(INPUT_FG.glob("*.png"))
    if not fg_files:
        print("No foreground files found.")
        return

    bg_path = find_any_background_image(USER_BG_DIR)

    USE_AI = True
    PRESET = "market_tone"
    BG_MODE = "regen"  # reuse | regen
    SEED = 42

    for fg_p in fg_files:
        mask_p = INPUT_MASK / fg_p.name

        start = time.time()
        res = process_composition(
            fg_p,
            mask_p if mask_p.exists() else None,
            user_bg_path=str(bg_path) if bg_path else None,
            use_ai_gen=USE_AI,
            preset_key=PRESET,
            user_bg_mode=BG_MODE,
            seed=SEED
        )

        tag = "USERBG" if bg_path else "PRESET"
        out_name = f"{fg_p.stem}_{tag}_{BG_MODE}_{PRESET}_v8FINAL.png"
        out_path = OUT_COMP / out_name
        res.save(out_path)

        print(f"Saved: {out_path} ({time.time()-start:.2f}s)")


if __name__ == "__main__":
    main()
