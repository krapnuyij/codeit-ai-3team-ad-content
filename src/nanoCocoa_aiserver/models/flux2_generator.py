"""
FLUX.2 Klein 기반 AI 배경 생성 및 합성 엔진

[모델 정보]
- Model ID: black-forest-labs/FLUX.2-klein-4B
- Type: Text-to-Image with Object Composition

[주요 기능]
1. Smart Tilt: 제품의 비율(가로/세로)을 분석하여 3D 입체 기울기 자동 적용 (기준값 0.7)
2. Soft Shadow: 제품 하단에 자연스러운 그림자 생성 (Blur 15, Alpha 140)
3. Quality Guard: 사용자 프롬프트 뒤에 고품질/한국적 스타일 프롬프트 강제 주입
4. Auto Tokenizer: Qwen2 기반 토크나이저 호환성 문제 해결을 위한 수동 조립 로직 적용

[최적화 파라미터 (v26 기준)]
- Product Scale: 0.65 (배경 대비 65%)
- Inference Steps: 12 (고화질)
- Shadow: Blur 15 / Offset 10
"""

import os
import gc
import logging
import cv2
import numpy as np
import torch
from PIL import Image, ImageFilter
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

# [라이브러리 로드]
try:
    from diffusers import (
        FluxPipeline, 
        FluxInpaintPipeline,
        FlowMatchEulerDiscreteScheduler, 
        AutoencoderKL, 
        FluxTransformer2DModel
    )
    from transformers import (
        T5EncoderModel, 
        AutoTokenizer
    )
except ImportError:
    print("필수 라이브러리(diffusers, transformers)가 설치되지 않았습니다.")

# 로깅 설정
logger = logging.getLogger("Flux2Generator")

# 상수 설정
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"

# 품질 방어 프롬프트 (사용자 입력 뒤에 무조건 붙음)
FIXED_QUALITY_PROMPT = (
    ", The rustic wooden table is positioned excessively close to the foreground, with its front edge cropped out by the bottom of the frame, "
    "Texture: 8k photorealism, glistening silk texture under warm cinematic lighting, "
    "(Clean roof eaves, NO red lanterns, NO hanging ornaments, NO Chinese style decorations), "
    "Clean, elegant, distinctly Korean, no text"
)

class Flux2Generator:
    def __init__(self):
        self._cache = {}
        logger.info(f"Flux2Generator 초기화: {MODEL_ID}")

    def flush(self):
        """메모리 정리"""
        gc.collect()
        torch.cuda.empty_cache()

    # --- 컴포넌트 수동 로드 (에러 방지 핵심) ---
    def _load_components_manually(self):
        logger.info("컴포넌트 수동 로드 시작 (AutoTokenizer 적용)...")
        
        scheduler = FlowMatchEulerDiscreteScheduler.from_pretrained(MODEL_ID, subfolder="scheduler")
        vae = AutoencoderKL.from_pretrained(MODEL_ID, subfolder="vae", torch_dtype=DTYPE)
        
        transformer = FluxTransformer2DModel.from_pretrained(
            MODEL_ID, 
            subfolder="transformer", 
            torch_dtype=DTYPE,
            low_cpu_mem_usage=False 
        )
        
        text_encoder_2 = T5EncoderModel.from_pretrained(
            MODEL_ID, 
            subfolder="text_encoder", 
            torch_dtype=DTYPE,
            low_cpu_mem_usage=False 
        )
        
        tokenizer_2 = AutoTokenizer.from_pretrained(MODEL_ID, subfolder="tokenizer")
        
        return {
            "scheduler": scheduler,
            "vae": vae,
            "transformer": transformer,
            "text_encoder": None, 
            "tokenizer": None,    
            "text_encoder_2": text_encoder_2,
            "tokenizer_2": tokenizer_2,
        }

    # --- 스마트 입체감 분석 ---
    def _should_apply_tilt(self, image: Image.Image) -> bool:
        w, h = image.size
        ratio = h / w
        # 0.7보다 크면(사과, 병 등) -> Tilt 미적용
        if ratio > 0.7:
            return False
        return True

    # --- OpenCV 3D Tilt 효과 ---
    def apply_perspective_tilt(self, pil_img: Image.Image, tilt_factor=0.08, perspective_strength=0.15) -> Image.Image:
        cv_img = np.array(pil_img)
        h, w = cv_img.shape[:2]

        pad_x = w * perspective_strength
        pad_y = h * tilt_factor

        src_pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst_pts = np.float32([
            [pad_x, pad_y], [w - pad_x, pad_y],
            [w + pad_x * 0.5, h], [-pad_x * 0.5, h]
        ])

        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
        warped_cv_img = cv2.warpPerspective(cv_img, matrix, (int(w + pad_x), h))
        
        return Image.fromarray(warped_cv_img).convert("RGBA")

    # --- 부드러운 하단 그림자 (Soft Shadow) ---
    def apply_soft_shadow(self, pil_img: Image.Image, shadow_color=(0, 0, 0, 140), blur_radius=15, offset_y=10) -> Image.Image:
        mask = pil_img.split()[3]
        shadow = Image.new("RGBA", pil_img.size, (0, 0, 0, 0))
        shadow.paste(shadow_color, (0, 0), mask)
        shadow_blurred = shadow.filter(ImageFilter.GaussianBlur(blur_radius))
        
        final_shadow_layer = Image.new("RGBA", pil_img.size, (0, 0, 0, 0))
        final_shadow_layer.paste(shadow_blurred, (0, offset_y))
        
        combined = Image.alpha_composite(final_shadow_layer, pil_img)
        return combined

    # --- 위치 계산 ---
    def calculate_placement(self, bg_size, fg_size, y_offset_ratio=0.75) -> Tuple[int, int]:
        bg_w, bg_h = bg_size
        fg_w, fg_h = fg_size
        pos_x = (bg_w - fg_w) // 2
        pos_y = int(bg_h * y_offset_ratio) - (fg_h // 2)
        return (pos_x, pos_y)

    # --- [API 진입점] 생성 실행 ---
    def generate(self, 
                 image: Image.Image, 
                 prompt: str, 
                 negative_prompt: str = "", 
                 guidance_scale: float = 3.5, 
                 seed: int = -1,
                 **kwargs) -> Image.Image:
        """
        API 서버에서 호출하는 메인 함수
        """
        try:
            logger.info("Flux2 생성 프로세스 시작")
            
            # 1. 시드 설정
            if seed == -1 or seed is None:
                seed = np.random.randint(0, 2**32 - 1)
            generator = torch.Generator(device=DEVICE).manual_seed(int(seed))
            logger.info(f"Seed: {seed}")

            # 2. 프롬프트 조합 (사용자 입력 + 품질 방어)
            full_prompt = f"{prompt} {FIXED_QUALITY_PROMPT}"
            logger.info(f"Final Prompt: {full_prompt}")

            # 3. 파이프라인 로드 (수동 조립)
            components = self._load_components_manually()
            pipe = FluxPipeline(**components)
            pipe.enable_model_cpu_offload()

            # 4. 배경 생성
            bg_image = pipe(
                prompt=full_prompt,
                height=1024,
                width=1024,
                guidance_scale=guidance_scale,
                num_inference_steps=12,  # 최적값: 12
                max_sequence_length=512,
                generator=generator
            ).images[0].convert("RGBA")

            # 파이프라인 정리 (메모리 확보)
            del pipe
            self.flush()

            # 5. 전경 전처리 (리사이즈)
            base_scale = 0.65 # 최적값: 0.65
            target_w = int(bg_image.width * base_scale)
            aspect = image.height / image.width
            target_h = int(target_w * aspect)
            fg_resized = image.resize((target_w, target_h), Image.LANCZOS)

            # 6. 스마트 틸트 & 그림자
            if self._should_apply_tilt(fg_resized):
                fg_tilted = self.apply_perspective_tilt(fg_resized, tilt_factor=0.08, perspective_strength=0.15)
            else:
                fg_tilted = fg_resized
            
            # 그림자 적용 (최적값: Blur 15, Alpha 140)
            fg_with_shadow = self.apply_soft_shadow(fg_tilted, shadow_color=(0, 0, 0, 140), blur_radius=15, offset_y=10)

            # 7. 최종 합성
            pos = self.calculate_placement(bg_image.size, fg_with_shadow.size, y_offset_ratio=0.80)
            
            final_image = bg_image.copy()
            comp_layer = Image.new("RGBA", bg_image.size, (0, 0, 0, 0))
            comp_layer.paste(fg_with_shadow, pos)
            
            final_image = Image.alpha_composite(final_image, comp_layer)
            
            return final_image.convert("RGB")

        except Exception as e:
            logger.error(f"Flux 생성 실패: {str(e)}")
            import traceback
            traceback.print_exc()
            self.flush()
            raise e