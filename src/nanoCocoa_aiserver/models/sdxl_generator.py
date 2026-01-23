"""
sdxl_composer_final.py

GCP 환경 배포용 SDXL 기반 AI 상품 배경 합성 엔진입니다.
건어물 등 상품 이미지를 입력받아 웅장한 설날/전통 배경과 합성합니다.

[주요 기능]
1. 원본 크기 유지 (Majestic Scale): 입력 이미지를 리사이즈하지 않고 사용하여 웅장함 유지.
2. 스마트 입체감 (Smart Perspective): 이미지 비율을 분석하여 서 있는 물체만 자연스럽게 눕힘.
3. 배경 색감 동기화 (Color Transfer): 사용자 배경 이미지의 색조를 추출하여 생성에 반영.
4. 후처리 줌인 (Post-Zoom): 생성 완료 후 이미지를 확대하여 피사체 강조.
5. 품질 부스터 (Quality Booster): 사용자 프롬프트에 고품질 태그 자동 추가.

[파라미터 설명]
- fg_path (str): 전경(누끼) 이미지 경로.
- user_bg_input (str, optional): 배경 참고 이미지 경로 (색감 추출용).
- user_prompt (str, optional): 사용자 추가 프롬프트.
- user_neg_prompt (str, optional): 사용자 추가 부정 프롬프트.
- comp_strength (float): 합성 강도 (기본 0.6).
- guidance_scale (float): 프롬프트 따름 강도 (기본 5.0).
- seed (int): 시드 값 (재현성 보장).
- preserve_product (bool): 원본 제품 이미지 유지 여부 (기본 True).
- zoom_factor (float): 최종 결과물 확대 배율 (기본 1.0).
- auto_perspective (bool): 스마트 입체감 자동 적용 여부 (기본 True).
"""

import sys
import os
import gc
import logging
import traceback
from pathlib import Path
from typing import Optional

import torch
import numpy as np
import cv2
from PIL import Image, ImageFilter

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("SDXL_Composer")

# 필수 라이브러리 로드 체크
try:
    from diffusers import (
        StableDiffusionXLPipeline,
        StableDiffusionXLControlNetInpaintPipeline,
        ControlNetModel
    )
    from transformers import BlipProcessor, BlipForConditionalGeneration
    AI_AVAILABLE = True
except ImportError:
    logger.error("필수 라이브러리(Diffusers, Transformers)가 설치되지 않았습니다.")
    AI_AVAILABLE = False

# 하드웨어 설정 (GCP T4 GPU 권장)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
TORCH_DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32

# 경로 설정
BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "outputs" / "fg_cut"
OUTPUT_DIR = BASE_DIR / "outputs" / "compose"
BG_DIR = BASE_DIR / "data" / "backgrounds"

# 디렉토리 자동 생성
INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
BG_DIR.mkdir(parents=True, exist_ok=True)

# 모델 ID 정의
MODEL_ID_BASE = "stabilityai/stable-diffusion-xl-base-1.0"
MODEL_ID_CONTROLNET = "diffusers/controlnet-canny-sdxl-1.0"
MODEL_ID_INPAINT = "diffusers/stable-diffusion-xl-1.0-inpainting-0.1"
MODEL_ID_BLIP = "Salesforce/blip-image-captioning-base"

# 자동 보정 설정값
SAFEGUARDS = {
    "TILT_FACTOR": 0.35,
    "PERSPECTIVE_STRENGTH": 0.25,
    "SHADOW_OPACITY": 0.4,
    "SHADOW_BLUR": 20
}

# 기본 부정 프롬프트
DEFAULT_NEG = (
    "text, watermark, low quality, distortion, ugly, bad anatomy, floating objects"
)
STRONG_NEG_FOOD = (
    "floating food, unnatural placement, bad lighting, cartoon, illustration"
)

# 기본 프롬프트 (v24)
DEFAULT_PRESET = (
    "high-quality commercial product photography for Korean Lunar New Year Seollal. "
    "Perspective: An ultra-close-up, high-angle overhead shot. "
    "The rustic wooden table is positioned excessively close to the foreground, "
    "dominating the lower view. "
    "Background: A warm, hand-drawn Korean watercolor (Sumukhwa) style Hanok village. "
    "(Clean roof eaves, NO red lanterns). "
    "Characters: Cute Korean children in Saekdong Hanbok playing Yutnori. "
    "Nature: A pair of Korean Magpies (Kkachi) on a pine tree. "
    "Foreground: A gargantuan, ultra-oversized luxurious golden-yellow Korean silk "
    "Bojagi cloth laid diagonally, completely engulfing the table surface. "
    "The cloth spills voluminously over the edges with deep folds. "
    "Texture: 8k photorealism, glistening silk texture, warm cinematic lighting."
)

# 품질 부스터 태그
QUALITY_BOOSTER = (
    ", Texture: 8k photorealism, glistening silk texture, "
    "warm cinematic lighting, highly detailed, sharp focus."
)


def get_next_version_path(base_path: Path) -> Path:
    """파일 덮어쓰기 방지를 위한 버전 관리 경로를 반환합니다."""
    if not base_path.exists():
        return base_path
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent
    counter = 1
    while True:
        new_path = parent / f"{stem}_v{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


def resolve_bg_path(filename_or_path: str) -> Optional[Path]:
    """배경 이미지 파일 경로를 찾습니다."""
    if not filename_or_path:
        return None
    
    path_obj = Path(filename_or_path)
    if path_obj.exists() and path_obj.is_file():
        return path_obj
    
    # data/backgrounds 폴더 내 검색
    direct_path = BG_DIR / filename_or_path
    if direct_path.exists():
        return direct_path
        
    for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
        candidate = BG_DIR / f"{filename_or_path}{ext}"
        if candidate.exists():
            return candidate
    return None


class DashboardComposeEngine:
    """
    대시보드 연동용 AI 합성 엔진 클래스입니다.
    """
    def __init__(self):
        self._cache = {}
        logger.info("SDXL Composer 엔진 초기화 완료")

    def unload(self):
        """GPU 메모리를 강제로 확보합니다."""
        for k in list(self._cache.keys()):
            del self._cache[k]
        if DEVICE == "cuda":
            gc.collect()
            torch.cuda.empty_cache()
        logger.info("메모리 정리 완료")

    def _load_pipeline(self, mode="base"):
        """필요한 AI 모델을 메모리에 로드합니다."""
        if not AI_AVAILABLE:
            return None
        if mode in self._cache:
            return self._cache[mode]

        if mode == "base":
            logger.info("SDXL Base 모델 로딩 중...")
            pipe = StableDiffusionXLPipeline.from_pretrained(
                MODEL_ID_BASE, torch_dtype=TORCH_DTYPE, variant="fp16"
            ).to(DEVICE)
        
        elif mode == "inpaint":
            logger.info("SDXL ControlNet Inpaint 모델 로딩 중...")
            cnet = ControlNetModel.from_pretrained(
                MODEL_ID_CONTROLNET, torch_dtype=TORCH_DTYPE
            ).to(DEVICE)
            pipe = StableDiffusionXLControlNetInpaintPipeline.from_pretrained(
                MODEL_ID_INPAINT,
                controlnet=cnet,
                torch_dtype=TORCH_DTYPE,
                variant="fp16"
            ).to(DEVICE)
            
        self._cache[mode] = pipe
        return pipe

    def extract_color_palette(self, image: Image.Image, k: int = 5) -> str:
        """이미지에서 주요 색상 테마를 추출합니다."""
        small = image.copy().resize((100, 100))
        arr = np.array(small).reshape(-1, 3).astype(np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, _, centers = cv2.kmeans(
            arr, k, None, criteria, 10, cv2.KMEANS_PP_CENTERS
        )
        hex_colors = [
            f"#{int(c[0]):02x}{int(c[1]):02x}{int(c[2]):02x}" for c in centers
        ]
        return ", ".join(hex_colors)

    def apply_perspective_transform(self, pil_img: Image.Image) -> Image.Image:
        """이미지에 3D 입체감(Perspective Tilt)을 적용합니다."""
        cv_img = np.array(pil_img)
        h, w = cv_img.shape[:2]

        tilt = SAFEGUARDS["TILT_FACTOR"]
        persp = SAFEGUARDS["PERSPECTIVE_STRENGTH"]

        src_pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        pad_x = w * persp
        new_h = h * tilt
        
        dst_pts = np.float32([
            [pad_x, 0],
            [w - pad_x, 0],
            [w, new_h],
            [0, new_h]
        ])

        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
        warped = cv2.warpPerspective(
            cv_img,
            matrix,
            (w, int(new_h)),
            flags=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0)
        )
        return Image.fromarray(warped).convert("RGBA")

    def _should_apply_tilt(self, image: Image.Image) -> bool:
        """이미지 비율을 분석하여 3D 입체감 적용 여부를 결정합니다."""
        w, h = image.size
        ratio = h / w
        # 높이가 너비보다 10% 이상 크면 서 있는 물체로 판단
        return ratio > 1.1

    def apply_post_zoom(self, image: Image.Image, scale: float) -> Image.Image:
        """최종 결과물을 중앙 기준으로 확대(Crop & Resize)합니다."""
        if scale <= 1.0:
            return image
        
        w, h = image.size
        new_w = w / scale
        new_h = h / scale
        
        left = (w - new_w) / 2
        top = (h - new_h) / 2
        right = (w + new_w) / 2
        bottom = (h + new_h) / 2
        
        zoomed_img = image.crop((left, top, right, bottom)).resize(
            (w, h), Image.LANCZOS
        )
        logger.info(f"후처리 줌인 적용 완료 (배율: {scale})")
        return zoomed_img

    def process(
        self,
        fg_path: str,
        user_bg_input: str = None,
        user_prompt: str = None,
        user_neg_prompt: str = None,
        comp_strength: float = 0.6,
        guidance_scale: float = 5.0,
        seed: int = 42,
        preserve_product: bool = True,
        zoom_factor: float = 1.0,
        auto_perspective: bool = True
    ) -> Image.Image:
        """
        AI 이미지 합성 프로세스를 실행합니다.
        """
        try:
            # 1. 이미지 로드 (원본 크기 유지)
            logger.info(f"이미지 처리 시작: {Path(fg_path).name}")
            fg_clean = Image.open(fg_path).convert("RGBA")

            # 2. 스마트 3D 입체감 적용
            fg_3d = fg_clean
            if auto_perspective:
                if self._should_apply_tilt(fg_clean):
                    logger.info("스마트 감지: 세로형 이미지 -> 3D 입체감 적용")
                    fg_3d = self.apply_perspective_transform(fg_clean)
                else:
                    logger.info("스마트 감지: 가로/정사각 이미지 -> 원본 유지")
            else:
                logger.info("강제 적용: 3D 입체감 적용")
                fg_3d = self.apply_perspective_transform(fg_clean)

            # 3. 프롬프트 및 배경 설정
            final_prompt = DEFAULT_PRESET
            real_bg_path = resolve_bg_path(user_bg_input)

            if real_bg_path:
                logger.info(f"배경 색감 추출 중: {real_bg_path.name}")
                ref_img = Image.open(real_bg_path).convert("RGB")
                colors = self.extract_color_palette(ref_img)
                final_prompt = (
                    f"{DEFAULT_PRESET}, Color Theme: {colors}, matching atmosphere"
                )
            else:
                logger.info("기본 설날 프리셋 사용")

            if user_prompt:
                # 사용자 프롬프트가 있으면 품질 부스터와 함께 추가
                final_prompt += f", {user_prompt}{QUALITY_BOOSTER}"

            final_neg = (
                f"{user_neg_prompt}, {DEFAULT_NEG}"
                if user_neg_prompt
                else DEFAULT_NEG
            )

            # 4. 배경 생성
            pipe_base = self._load_pipeline("base")
            if pipe_base:
                g = torch.Generator(DEVICE).manual_seed(int(seed))
                bg = pipe_base(
                    prompt=final_prompt,
                    negative_prompt=final_neg,
                    width=1024,
                    height=1024,
                    num_inference_steps=30,
                    guidance_scale=float(guidance_scale),
                    generator=g
                ).images[0]
            else:
                bg = Image.new("RGB", (1024, 1024), (200, 200, 200))
            self.unload()

            # 5. 배치 및 그림자 생성
            bg_w, bg_h = bg.size
            fg_w, fg_h = fg_3d.size
            pos_x = (bg_w - fg_w) // 2
            pos_y = int(bg_h * 0.90) - fg_h
            
            mask = fg_3d.split()[3]
            shadow_h = int(fg_h * 0.2)
            shadow = mask.resize((fg_w, shadow_h)).filter(
                ImageFilter.GaussianBlur(SAFEGUARDS["SHADOW_BLUR"])
            )
            shadow_layer = Image.new("RGBA", shadow.size, (0, 0, 0, 255))
            shadow_layer.putalpha(
                shadow.point(lambda p: p * SAFEGUARDS["SHADOW_OPACITY"])
            )
            
            comp_base = bg.convert("RGBA")
            comp_base.paste(shadow_layer, (pos_x, pos_y + fg_h - (shadow_h // 2) - 5), shadow_layer)
            comp_base.paste(fg_3d, (pos_x, pos_y), fg_3d)

            # 6. AI 합성 (Inpainting)
            final_output = comp_base.convert("RGB")
            if AI_AVAILABLE and comp_strength > 0.05:
                logger.info("AI 하모나이제이션 수행 중...")
                pipe_inpaint = self._load_pipeline("inpaint")
                
                mask_canvas = Image.new("L", bg.size, 0)
                mask_canvas.paste(fg_3d.split()[3], (pos_x, pos_y))
                mask_canvas = mask_canvas.filter(ImageFilter.GaussianBlur(10))
                
                canny_img = np.array(comp_base.convert("RGB"))
                canny_img = cv2.Canny(canny_img, 100, 200)
                canny_img = np.concatenate([canny_img[:, :, None]] * 3, axis=2)
                canny_image = Image.fromarray(canny_img)

                g = torch.Generator(DEVICE).manual_seed(int(seed))
                result = pipe_inpaint(
                    prompt=f"{final_prompt}, realistic lighting, shadow integration",
                    negative_prompt=f"{final_neg}, {STRONG_NEG_FOOD}",
                    image=comp_base.convert("RGB"),
                    mask_image=mask_canvas,
                    control_image=canny_image,
                    controlnet_conditioning_scale=0.8,
                    strength=float(comp_strength),
                    guidance_scale=float(guidance_scale),
                    num_inference_steps=30,
                    generator=g
                ).images[0]
                
                final_output = result
                self.unload()

                if preserve_product:
                    logger.info("원본 제품 이미지 복원 중...")
                    final_output_rgba = final_output.convert("RGBA")
                    final_output_rgba.paste(fg_3d, (pos_x, pos_y), fg_3d)
                    final_output = final_output_rgba.convert("RGB")

            # 7. 후처리 줌인
            if zoom_factor > 1.0:
                final_output = self.apply_post_zoom(final_output, zoom_factor)

            logger.info("작업 완료")
            return final_output

        except Exception as e:
            logger.error(f"처리 중 오류 발생: {e}")
            traceback.print_exc()
            self.unload()
            raise e


# -----------------------------------------------------------------------------
# 테스트용 실행 블록 (직접 실행 시)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    files = sorted(INPUT_DIR.glob("*.png"))
    if not files:
        print(f"입력 파일이 없습니다: {INPUT_DIR}")
    else:
        engine = DashboardComposeEngine()
        
        # 테스트 파라미터
        ui_params = {
            "user_prompt": None,
            "user_neg_prompt": "blurry",
            "comp_strength": 0.6,
            "guidance_scale": 5.0,
            "seed": 12345,
            "preserve_product": True,
            "zoom_factor": 1.3,
            "auto_perspective": True
        }
        
        for f in files:
            res = engine.process(str(f), **ui_params)
            save_path = get_next_version_path(OUTPUT_DIR / f"{f.stem}_final.png")
            res.save(save_path)
            print(f"저장됨: {save_path.name}")