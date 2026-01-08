import torch
import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
from diffusers import StableDiffusionXLControlNetInpaintPipeline, ControlNetModel

class SDXLPipeline:
    def __init__(self, device="cuda"):
        self.device = device if torch.cuda.is_available() else "cpu"
        # VRAM에 고정 로드
        self.pipe = self._load_models()
        print(f"SDXL Pipeline Loaded on {self.device}")

    def _load_models(self):
        # ControlNet (Canny) 로드
        controlnet = ControlNetModel.from_pretrained(
            "diffusers/controlnet-canny-sdxl-1.0",
            torch_dtype=torch.float16
        ).to(self.device)
        
        # Inpaint 파이프라인 로드
        pipe = StableDiffusionXLControlNetInpaintPipeline.from_pretrained(
            "diffusers/stable-diffusion-xl-1.0-inpainting-0.1",
            controlnet=controlnet,
            torch_dtype=torch.float16, 
            variant="fp16"
        ).to(self.device)

        # 메모리 최적화
        pipe.enable_xformers_memory_efficient_attention()
        pipe.enable_model_cpu_offload()
        
        return pipe

    def _get_canny_edge(self, image):
        """형태 고정을 위한 Canny 엣지 추출"""
        img_np = np.array(image.convert("RGB"))
        edges = cv2.Canny(img_np, 100, 200)
        edges = np.stack([edges] * 3, axis=-1)
        return Image.fromarray(edges)

    def _detect_object_floor(self, mask):
        """제품 하단 위치 분석 (바닥 접지점 찾기)"""
        mask_l = mask.convert("L")
        w, h = mask_l.size
        arr = mask_l.load()
        for y in range(h - 1, 0, -1):
            for x in range(w):
                if arr[x, y] > 10: return y
        return int(h * 0.9)

    def process(self, background, foreground, mask, config):
        """
        메인 실행 함수 (백엔드 routes.py에서 호출)
        config: presets.json에서 가져온 설정값 (dict)
        """
        W, H = background.size
        
        # 자동 위치 배치
        fg_resized = foreground.resize((int(W * 0.7), int(H * 0.7)), Image.LANCZOS)
        mask_resized = mask.resize(fg_resized.size, Image.LANCZOS)
        
        obj_floor_y = self._detect_object_floor(mask_resized)
        bg_floor_y = int(H * 0.93)
        pos = ((W - fg_resized.size[0]) // 2, bg_floor_y - obj_floor_y)

        # 초기 합성
        base_canvas = background.copy().convert("RGB")
        base_canvas.paste(fg_resized.convert("RGB"), pos, mask_resized)
        canny_guide = self._get_canny_edge(base_canvas)

        # 인페인팅 마스크 - 그림자 주변 흐림
        full_mask = Image.new("L", background.size, 0)
        full_mask.paste(mask_resized, pos)
        refined_mask = full_mask.filter(ImageFilter.MaxFilter(21))
        refined_mask = refined_mask.filter(ImageFilter.GaussianBlur(15))

        # AI 하모니제이션 
        ai_output = self.pipe(
            prompt=config["prompt"] + ", realistic shadows, photorealistic",
            negative_prompt=config.get("negative_prompt", "blurry, distorted"),
            image=base_canvas,
            mask_image=refined_mask,
            control_image=canny_guide,
            controlnet_conditioning_scale=config.get("controlnet_scale", 0.5),
            strength=config.get("strength", 0.28),
            num_inference_steps=30,
            guidance_scale=7.5
        ).images[0].convert("RGBA")

        # Hybrid Blending
        recovery_mask = mask_resized.filter(ImageFilter.MinFilter(11))
        recovery_mask = recovery_mask.filter(ImageFilter.GaussianBlur(5))
        
        final_result = ai_output.copy()
        final_result.paste(fg_resized, pos, recovery_mask)
        
        # 메모리 정리
        torch.cuda.empty_cache()
        
        return final_result