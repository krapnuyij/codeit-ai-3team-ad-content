"""
sdxl_generator.py

Compose Pipeline (v10)
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

import sys
import os
import gc
import time
import logging
import traceback
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

import torch
import numpy as np
import cv2
from PIL import Image, ImageFilter

# -----------------------------------------------------------------------------
# 1. 로깅 설정 (Logging Setup)
# -----------------------------------------------------------------------------
# print 대신 logging을 사용하여 시스템 로그를 체계적으로 관리.
logger = logging.getLogger("ComposeEngine")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# -----------------------------------------------------------------------------
# 2. 라이브러리 임포트 체크 (Dependency Check)
# -----------------------------------------------------------------------------
try:
    from diffusers import (
        StableDiffusionXLControlNetInpaintPipeline,
        ControlNetModel,
        StableDiffusionXLPipeline,
    )
    from transformers import BlipProcessor, BlipForConditionalGeneration
    AI_AVAILABLE = True
except ImportError:
    logger.warning("Diffusers/Transformers 라이브러리를 찾을 수 없습니다. AI 기능이 비활성화됩니다.")
    AI_AVAILABLE = False

# -----------------------------------------------------------------------------
# 3. 설정 및 상수 (Configuration)
# -----------------------------------------------------------------------------
# 디바이스 설정 (GPU 우선)
DEVICE: str = "cuda" if torch.cuda.is_available() else "cpu"
TORCH_DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32

# 출력 폴더 자동 생성
OUT_COMP.mkdir(parents=True, exist_ok=True)

# 모델 ID (필요시 수정)
MODEL_ID_BASE = "stabilityai/stable-diffusion-xl-base-1.0"
MODEL_ID_CONTROLNET = "diffusers/controlnet-canny-sdxl-1.0"
MODEL_ID_INPAINT = "diffusers/stable-diffusion-xl-1.0-inpainting-0.1"

# 부정 프롬프트 (Negative Prompt) - 텍스트, 음식물 환각 방지 강화
NEG_NO_TEXT_STRONG: str = (
    "text, letters, typography, words, caption, subtitle, "
    "sign, signage, signboard, shop sign, billboard, banner, poster, menu, "
    "logo, watermark, label, sticker, price tag, numbers, digits, QR code, barcode, "
    "cartoon, illustration, low quality, distorted, ugly, deformed, "
    "food, squid, fish, seafood, meat, dry fish, cooking ingredients, object on board, mess"
)

NEG_SD_DEFAULT: str = "cartoon, illustration, low quality, distorted, watermark, logo"

# 프리셋 (Presets)
PRESETS: Dict[str, str] = {
    # [설날 선물 세트 - 구도 개선 버전]
    "seollal_gift": (
        "high-quality commercial product photography composition for Korean Lunar New Year Seollal "
        "Background is a peaceful traditional Korean courtyard scene with warm watercolor ink wash painting style "
        "Traditional Hanok house with curved tiled roof and stone wall in the distance "
        "Cute children in colorful Saekdong Hanbok playing Yutnori in the yard "
        "A Korean Magpie on a pine tree, soft pastel yellow morning sky "
        "(no red lanterns, no Chinese ornaments) "
        "In the center foreground, a luxurious golden-yellow Korean silk Bojagi cloth is draped elegantly over a low wooden table "
        "empty space on top of the cloth for product placement "
        "Natural morning sunlight casting soft shadows, shallow depth of field but keeping the village visible "
        "cinematic lighting, clean composition, 8k, photorealistic, no text"
    ),

    "market_tone": (
        "traditional korean market alley background, soft daylight, authentic market mood "
        "blurred background, ambient occlusion, soft top lighting, empty space, clean composition"
    ),
    "modern_clean": (
        "empty white marble countertop, clean kitchen background "
        "soft ambient lighting, minimal style "
        "high quality, 8k, photorealistic, advertising photography"
    ),
    "traditional_dry_fish": (
        "rustic wooden tray, woven straw mats background, warm morning sunlight "
        "korean heritage mood, ambient occlusion, soft top lighting"
    ),
}


# -----------------------------------------------------------------------------
# 4. 핵심 클래스 (SDXLGenerator)
# -----------------------------------------------------------------------------
class SDXLGenerator:
    """
    SDXL 기반 배경 생성 및 합성 엔진.
    GCP T4 환경을 고려하여 적극적인 메모리 관리(Unload)를 수행합니다.
    """

    def __init__(self) -> None:
        """생성기 초기화 (모델 캐시는 비워둠)"""
        self._cache: Dict[str, Any] = {}
        logger.info("SDXLGenerator가 초기화되었습니다.")

    def unload(self) -> None:
        """
        메모리 해제: 사용된 모델을 삭제하고 GPU 캐시를 정리합니다.
        OOM(Out of Memory) 방지를 위해 필수적입니다.
        """
        keys = list(self._cache.keys())
        for key in keys:
            del self._cache[key]
        self._cache.clear()

        if DEVICE == "cuda":
            gc.collect()
            torch.cuda.empty_cache()
        logger.info("메모리 정리 완료: 모델 언로드됨.")

    # --- 유틸리티 함수 ---
    def load_image_any(self, path: Path) -> Image.Image:
        """이미지를 RGB로 안전하게 로드"""
        return Image.open(path).convert("RGB")

    def load_rgba_any(self, path: Path) -> Image.Image:
        """이미지를 RGBA로 로드 (누끼 이미지용)"""
        return Image.open(path).convert("RGBA")

    def ensure_size(self, img: Image.Image, size: Tuple[int, int] = (1024, 1024)) -> Image.Image:
        """이미지 크기를 모델 입력에 맞게 조정"""
        if img.size != size:
            return img.resize(size, Image.LANCZOS)
        return img

    # --- 모델 로딩 (Lazy Loading) ---
    def _load_captioner(self):
        """BLIP 캡셔닝 모델 로드"""
        if "captioner" in self._cache:
            return self._cache["captioner"]

        logger.info("BLIP 캡셔너 로딩 중...")
        processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        model = BlipForConditionalGeneration.from_pretrained(
            "Salesforce/blip-image-captioning-base", torch_dtype=TORCH_DTYPE
        ).to(DEVICE)

        self._cache["captioner"] = (processor, model)
        return processor, model

    def _load_pipeline(self, model_type: str = "controlnet_inpaint") -> Any:
        """SDXL 파이프라인 로드 (Base 또는 ControlNet)"""
        if not AI_AVAILABLE:
            return None
        
        if model_type in self._cache:
            return self._cache[model_type]

        if model_type == "controlnet_inpaint":
            logger.info("SDXL ControlNet Inpaint 로딩 중...")
            controlnet = ControlNetModel.from_pretrained(
                MODEL_ID_CONTROLNET, torch_dtype=TORCH_DTYPE
            ).to(DEVICE)
            pipe = StableDiffusionXLControlNetInpaintPipeline.from_pretrained(
                MODEL_ID_INPAINT,
                controlnet=controlnet,
                torch_dtype=TORCH_DTYPE,
                variant="fp16",
            ).to(DEVICE)

        elif model_type == "base":
            logger.info("SDXL Base 모델 로딩 중...")
            pipe = StableDiffusionXLPipeline.from_pretrained(
                MODEL_ID_BASE,
                torch_dtype=TORCH_DTYPE,
                variant="fp16",
            ).to(DEVICE)
        else:
            raise ValueError(f"알 수 없는 모델 타입: {model_type}")

        self._cache[model_type] = pipe
        return pipe

    # --- 이미지 분석 및 프롬프트 ---
    def analyze_image(self, image: Image.Image) -> str:
        """이미지 캡셔닝 (BLIP 사용)"""
        if not AI_AVAILABLE: return "background"
        processor, model = self._load_captioner()
        
        img_resized = image.copy()
        img_resized.thumbnail((512, 512))
        inputs = processor(img_resized, return_tensors="pt").to(DEVICE, TORCH_DTYPE)
        
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=50)
        
        return processor.decode(out[0], skip_special_tokens=True)

    def analyze_bg_stats(self, bg: Image.Image) -> dict:
        """배경 이미지의 밝기 및 채도 통계 분석"""
        gray = np.array(bg.convert("L"))
        hsv = np.array(bg.convert("HSV"))
        return {
            "mean_lum": float(gray.mean()),
            "std_lum": float(gray.std()),
            "mean_sat": float(hsv[..., 1].mean())
        }

    def extract_color_palette(self, bg: Image.Image, k: int = 5) -> List[Tuple[int, int, int]]:
        """배경의 주요 색상 팔레트 추출 (K-Means)"""
        small = bg.copy().resize((256, 256), Image.BILINEAR)
        arr = np.array(small).reshape(-1, 3).astype(np.float32)
        
        # 속도를 위해 샘플링
        if arr.shape[0] > 50000:
            idx = np.random.choice(arr.shape[0], 50000, replace=False)
            arr = arr[idx]
            
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1.0)
        _, labels, centers = cv2.kmeans(arr, k, None, criteria, 10, cv2.KMEANS_PP_CENTERS)
        
        centers = np.clip(centers, 0, 255).astype(np.uint8)
        counts = np.bincount(labels.flatten(), minlength=k)
        order = np.argsort(-counts)
        
        return [tuple(map(int, centers[i])) for i in order]

    def palette_to_prompt_text(self, palette: List[Tuple[int, int, int]]) -> str:
        """RGB 팔레트를 텍스트 프롬프트로 변환"""
        hexes = [f"#{r:02x}{g:02x}{b:02x}" for (r, g, b) in palette]
        return "color palette: " + ", ".join(hexes)

    @staticmethod
    def build_regen_prompt(caption: str, palette_text: str) -> str:
        """재생성(Regen)을 위한 최적화된 프롬프트 생성"""
        return (
            f"{caption}, {palette_text}, "
            f"empty background, no food, no objects, "
            f"same vibe and lighting as reference, photorealistic, natural perspective, "
            f"soft daylight, shallow depth of field, bokeh, high quality, 8k, "
            f"no text, no letters, no labels, no logo, no watermark"
        )

    def auto_sdxl_params_from_bg_stats(self, stats: dict) -> dict:
        """배경 통계에 따라 SDXL 생성 파라미터 자동 조절"""
        steps = 28
        guidance = 6.0
        
        if stats["mean_lum"] > 170:
            steps = 26
            guidance = 4.8
        if stats["mean_lum"] < 90:
            steps = 32
            guidance = 6.0
        if stats["std_lum"] > 75:
            guidance -= 0.2
        if stats["mean_sat"] > 120:
            steps += 2
            
        return {
            "num_inference_steps": int(np.clip(steps, 24, 40)),
            "guidance_scale": float(np.clip(guidance, 4.0, 7.0))
        }

    # --- 생성 및 합성 (Generation & Composition) ---
    def sdxl_generate_background(
        self, prompt: str, seed: int, size: Tuple[int, int], params: dict, negative_prompt: str = None
    ) -> Image.Image:
        """SDXL Base 모델을 사용하여 배경 생성"""
        pipe = self._load_pipeline("base")
        if pipe is None:
            return Image.new("RGB", size, (240, 240, 240))

        g = torch.Generator(device=DEVICE).manual_seed(seed)
        full_neg = f"{negative_prompt or ''}, {NEG_SD_DEFAULT}, {NEG_NO_TEXT_STRONG}"

        out = pipe(
            prompt=prompt,
            negative_prompt=full_neg,
            generator=g,
            **params
        ).images[0].convert("RGB")

        return out.resize(size, Image.LANCZOS)

    def get_canny_edge(self, image: Image.Image) -> Image.Image:
        """ControlNet용 Canny Edge 추출"""
        img_np = np.array(image.convert("RGB"))
        edges = cv2.Canny(img_np, 100, 200)
        edges = np.concatenate([edges[:, :, None]] * 3, axis=2)
        return Image.fromarray(edges)

    def auto_place_on_ground(
        self, fg: Image.Image, mask: Image.Image, canvas_size: Tuple[int, int]
    ) -> Tuple[Image.Image, Tuple[int, int]]:
        """물체의 바닥면을 인식하여 배경의 바닥(93% 지점)에 자동 배치"""
        W, H = canvas_size
        scale = 0.7  # 배경 대비 크기 비율
        
        fg_resized = fg.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
        mask_resized = mask.resize(fg_resized.size, Image.LANCZOS)
        
        # 마스크에서 물체의 최하단(바닥) 좌표 감지
        arr = mask_resized.convert("L").load()
        w, h = mask_resized.size
        obj_floor_y = int(h * 0.9)
        
        # 아래에서 위로 스캔
        for y in range(h - 1, 0, -1):
            is_obj = False
            for x in range(w):
                if arr[x, y] > 10:
                    obj_floor_y = y
                    is_obj = True
                    break
            if is_obj:
                break
        
        # 배치 좌표 계산
        background_floor = int(H * 0.93)
        x = (W - fg_resized.width) // 2
        y = background_floor - obj_floor_y
        
        return fg_resized, (x, y)

    def ai_harmonization_pro(
        self, bg: Image.Image, fg: Image.Image, pos: Tuple[int, int], prompt: str, strength: float = 0.12
    ) -> Image.Image:
        """ControlNet Inpaint를 이용한 자연스러운 합성 (빛/그림자 조화)"""
        pipe = self._load_pipeline("controlnet_inpaint")
        
        base_canvas = bg.copy().convert("RGB")
        base_canvas.paste(fg.convert("RGB"), pos, fg.split()[3])
        
        # Canny Edge 가이드 생성
        canny_guide = self.get_canny_edge(base_canvas)
        
        # 인페인팅 마스크 생성 (물체 영역보다 살짝 크게)
        mask_canvas = Image.new("L", bg.size, 0)
        mask_canvas.paste(fg.split()[3], pos)
        mask_canvas = mask_canvas.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(10))

        # AI 생성
        out = pipe(
            prompt=prompt + ", realistic shadows, photorealistic",
            negative_prompt=f"bad anatomy, {NEG_NO_TEXT_STRONG}",
            image=base_canvas,
            mask_image=mask_canvas,
            control_image=canny_guide,
            controlnet_conditioning_scale=0.8,
            strength=strength,
            guidance_scale=7.5,
            num_inference_steps=30
        ).images[0].convert("RGBA")

        # 원본 제품 디테일 복원 (AI 변형 방지)
        fg_orig = fg.convert("RGBA")
        recovery_mask = fg.split()[3].filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(3))
        out.paste(fg_orig, pos, recovery_mask)
        
        return out

    # -----------------------------------------------------------------------------
    # 5. 메인 워크플로우 (Process Composition)
    # -----------------------------------------------------------------------------
    def process_composition(
        self,
        fg_path: str,
        mask_path: Optional[str] = None,
        user_bg_path: Optional[str] = None,
        use_ai_gen: bool = True,
        preset_key: str = "seollal_gift",
        user_bg_mode: str = "regen",
        seed: int = 42,
        progress_callback = None,
        user_prompt: str = None  # <--- [1] 인자 추가됨
    ) -> Image.Image:
        """
        전체 합성 프로세스 실행 (사용자 프롬프트 반영)
        """
        try:
            if progress_callback:
                progress_callback(10, "이미지 로드 중...")

            # 1. 전경 로드
            fg = self.load_rgba_any(Path(fg_path))
            if mask_path and os.path.exists(mask_path):
                mask = Image.open(mask_path).convert("L")
            else:
                mask = fg.split()[3]

            bg = None
            final_prompt = ""
            ai_strength = 0.12

            # 2. 배경 생성/로드
            if user_bg_path and os.path.exists(user_bg_path):
                # [Case A] 사용자 배경 사용
                bg_user = self.ensure_size(self.load_image_any(Path(user_bg_path)))
                
                if user_bg_mode == "reuse":
                    bg = bg_user
                    if use_ai_gen:
                        cap = self.analyze_image(bg)
                        # 단순 재사용 시에도 사용자 의도를 반영하려면 여기에 추가
                        base_prompt = f"{cap}, realistic lighting, photorealistic"
                        final_prompt = f"{base_prompt}, {user_prompt}" if user_prompt else base_prompt
                        ai_strength = 0.10
                        self.unload()

                elif user_bg_mode == "regen":
                    cap = self.analyze_image(bg_user)
                    palette = self.extract_color_palette(bg_user)
                    stats = self.analyze_bg_stats(bg_user)
                    params = self.auto_sdxl_params_from_bg_stats(stats)
                    self.unload()

                    regen_prompt = self.build_regen_prompt(cap, self.palette_to_prompt_text(palette))
                    
                    # [2] 사용자 프롬프트 결합 (Regen)
                    if user_prompt:
                        regen_prompt = f"{regen_prompt}, {user_prompt}"
                    
                    if progress_callback: progress_callback(50, "고화질 배경 재생성 중...")
                    bg = self.sdxl_generate_background(regen_prompt, seed, bg_user.size, params)
                    self.unload()
                    
                    final_prompt = PRESETS.get(preset_key, PRESETS["seollal_gift"])

            else:
                # [Case B] 프리셋 기반 생성
                prompt_text = PRESETS.get(preset_key, PRESETS["seollal_gift"])
                
                # [3] 사용자 프롬프트 결합 (Preset)
                if user_prompt:
                    prompt_text = f"{prompt_text}, {user_prompt}"

                params = {"num_inference_steps": 25, "guidance_scale": 4.5}
                
                if progress_callback: progress_callback(30, f"배경 생성 중 (User Prompt 적용)...")
                bg = self.sdxl_generate_background(prompt_text, seed, (1024, 1024), params)
                self.unload()
                
                final_prompt = prompt_text
                ai_strength = 0.22

            # 3. 자동 배치
            fg_res, pos = self.auto_place_on_ground(fg, mask, bg.size)

            # 4. 최종 합성 (Shadow Pass 사용 시에도 final_prompt에 사용자 의도 반영 가능)
            if use_ai_gen and AI_AVAILABLE:
                if progress_callback: progress_callback(70, "AI 조명 및 그림자 합성 중...")
                
                # [4] 합성 단계 프롬프트에도 사용자 입력 추가 (선택사항)
                # 만약 사용자가 "어두운 분위기" 등을 요청했다면 합성에도 영향을 줘야 함
                if user_prompt:
                    final_prompt = f"{final_prompt}, {user_prompt}"

                final_image = self.ai_harmonization_pro(
                    bg, fg_res, pos, final_prompt, strength=ai_strength
                )
                self.unload()
            else:
                # (단순 합성 로직 유지)
                final_image = bg.copy().convert("RGBA")
                shadow_h = int(fg_res.height * 0.15) 
                shadow = mask.resize((fg_res.width, shadow_h)).filter(ImageFilter.GaussianBlur(20))
                shadow_layer = Image.new("RGBA", shadow.size, (0, 0, 0, 255))
                shadow_layer.putalpha(shadow.point(lambda p: p * 0.25))
                
                shadow_y = pos[1] + fg_res.height - (shadow_h // 2)
                final_image.paste(shadow_layer, (pos[0], shadow_y), shadow_layer)
                final_image.paste(fg_res, pos, fg_res.split()[3])

            if progress_callback: progress_callback(100, "완료!")
            return final_image

        except Exception as e:
            logger.error(f"합성 실패: {e}")
            traceback.print_exc()
            self.unload()
            raise e


# -----------------------------------------------------------------------------
# 6. 실행 진입점 (Main Entry Point)
# -----------------------------------------------------------------------------
import argparse # 상단 import에 추가 필요

# ... (기존 클래스 코드 유지) ...

# -----------------------------------------------------------------------------
# 6. 실행 진입점 (Main Entry Point) - CLI 지원 추가
# -----------------------------------------------------------------------------
def main():
    """
    로컬 테스트 및 배치 처리를 위한 실행 함수.
    명령어 인자(Argument)를 통해 입력/출력 경로를 동적으로 설정할 수 있습니다.
    """
    parser = argparse.ArgumentParser(description="SDXL Background Composition Engine")
    
    # 인자 설정 (기본값은 기존 로컬 경로 유지)
    parser.add_argument("--input", type=str, default="outputs/fg_cut", help="입력(누끼) 이미지 폴더 경로")
    parser.add_argument("--mask", type=str, default="outputs/fg_mask", help="마스크 이미지 폴더 경로 (선택)")
    parser.add_argument("--output", type=str, default="outputs/compose", help="결과물 저장 폴더 경로")
    parser.add_argument("--prompt", type=str, default=None, help="사용자 추가 프롬프트")
    
    args = parser.parse_args()

    # 경로 객체 생성
    input_dir = Path(args.input)
    mask_dir = Path(args.mask)
    output_dir = Path(args.output)

    # 출력 폴더 생성
    output_dir.mkdir(parents=True, exist_ok=True)

    # 입력 확인
    if not input_dir.exists():
        print(f"입력 폴더를 찾을 수 없습니다: {input_dir}")
        return

    files = sorted(input_dir.glob("*.png"))
    if not files:
        print(f"'{input_dir}' 폴더에 PNG 파일이 없습니다.")
        return

    print(f"{len(files)}개의 파일을 찾았습니다. 엔진을 초기화합니다...")
    engine = SDXLGenerator()

    def console_progress(percent: int, message: str):
        print(f" >> [{percent}%] {message}")

    for f in files:
        print(f"\n[Processing] {f.name}...")
        
        # 마스크 경로 자동 매칭 (파일명이 같다고 가정)
        mask_p = mask_dir / f.name
        start_time = time.time()

        try:
            result = engine.process_composition(
                fg_path=str(f),
                # 마스크 파일이 실제로 존재할 때만 경로 전달
                mask_path=str(mask_p) if mask_p.exists() else None,
                preset_key="seollal_gift",
                seed=42,
                progress_callback=console_progress,
                user_prompt=args.prompt # CLI에서 입력받은 프롬프트 전달
            )

            # 결과 저장
            out_name = f"{f.stem}_final.png"
            save_path = output_dir / out_name
            
            result.save(save_path)
            print(f"[Saved] {save_path} ({time.time() - start_time:.2f}s)")

        except Exception as e:
            print(f"[Skipped] {f.name} 처리 실패: {e}")
            # 에러 상세 로그가 필요하면 아래 주석 해제
            # traceback.print_exc()

    print("\n모든 작업이 완료되었습니다.")

if __name__ == "__main__":
    main()