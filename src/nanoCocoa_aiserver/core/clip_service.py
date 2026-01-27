"""
clip_service.py
CLIP Score 계산 핵심 로직 (OpenAI CLIP + KoCLIP 지원)
"""

import base64
import io
import sys
from pathlib import Path
from typing import Literal, Tuple

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import torch
from PIL import Image

from config import logger


class ClipService:
    """
    CLIP Score 계산 서비스 (싱글톤 패턴)

    OpenAI CLIP (영문) 및 KoCLIP (한글) 모델을 지원합니다.
    첫 요청 시 모델을 로드하고 이후 요청에서 재사용합니다.
    """

    _instance = None

    # OpenAI CLIP
    _clip_model = None
    _clip_preprocess = None

    # KoCLIP
    _koclip_model = None
    _koclip_processor = None

    _device = None

    def __new__(cls):
        """싱글톤 인스턴스 보장"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """초기화 (모델은 lazy loading)"""
        if self._clip_model is None and self._koclip_model is None:
            logger.info(
                "[ClipService] Initializing (models will be loaded on first use)"
            )

    def _load_clip_model(self) -> None:
        """OpenAI CLIP 모델 로딩 (lazy loading)"""
        if self._clip_model is not None:
            return

        try:
            import clip

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(
                f"[ClipService] Loading OpenAI CLIP model (ViT-B/32) on {self._device}"
            )

            self._clip_model, self._clip_preprocess = clip.load(
                "ViT-B/32", device=self._device
            )
            logger.info("[ClipService] OpenAI CLIP model loaded successfully")

        except ImportError as e:
            logger.error(
                f"[ClipService] Failed to import CLIP library: {e}. "
                "Please install: pip install ftfy regex tqdm git+https://github.com/openai/CLIP.git"
            )
            raise
        except Exception as e:
            logger.error(f"[ClipService] Failed to load OpenAI CLIP model: {e}")
            raise

    def _load_koclip_model(self) -> None:
        """KoCLIP 모델 로딩 (lazy loading)"""
        if self._koclip_model is not None:
            return

        try:
            from transformers import AutoModel, AutoProcessor

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            model_name = "clip-vit-base-patch32-ko"

            logger.info(
                f"[ClipService] Loading KoCLIP model ({model_name}) on {self._device}"
            )

            self._koclip_model = AutoModel.from_pretrained(f"Bingsu/{model_name}").to(
                self._device
            )
            self._koclip_processor = AutoProcessor.from_pretrained(
                f"Bingsu/{model_name}"
            )

            logger.info("[ClipService] KoCLIP model loaded successfully")

        except ImportError as e:
            logger.error(
                f"[ClipService] Failed to import transformers library: {e}. "
                "Please install: pip install transformers"
            )
            raise
        except Exception as e:
            logger.error(f"[ClipService] Failed to load KoCLIP model: {e}")
            raise

    def _decode_base64_image(self, image_base64: str) -> Image.Image:
        """
        Base64 문자열을 PIL Image로 디코딩

        Args:
            image_base64 (str): Base64 인코딩된 이미지 문자열

        Returns:
            Image.Image: PIL Image 객체

        Raises:
            ValueError: 디코딩 실패 시
        """
        try:
            # data:image/png;base64, 접두사 제거
            if "," in image_base64:
                image_base64 = image_base64.split(",", 1)[1]

            image_bytes = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_bytes))

            # RGBA → RGB 변환 (CLIP은 RGB만 지원)
            if image.mode == "RGBA":
                image = image.convert("RGB")

            return image

        except Exception as e:
            logger.error(f"[ClipService] Failed to decode base64 image: {e}")
            raise ValueError(f"Invalid base64 image: {e}")

    def calculate_clip_score(
        self,
        image_base64: str,
        prompt: str,
        model_type: Literal["openai", "koclip"] = "openai",
        auto_unload: bool = True,
    ) -> float:
        """
        CLIP Score 계산 (이미지-텍스트 코사인 유사도)

        Args:
            image_base64 (str): Base64 인코딩된 이미지
            prompt (str): 텍스트 프롬프트
            model_type (str): 사용할 모델 타입
                - "openai": OpenAI CLIP (영문 프롬프트 권장)
                - "koclip": KoCLIP (한글 프롬프트 지원)
            auto_unload (bool): 계산 후 자동 언로드 여부 (기본값: True)

        Returns:
            float: CLIP Score (코사인 유사도, 범위: -1.0 ~ 1.0)

        Raises:
            ValueError: 입력이 잘못된 경우
            RuntimeError: CLIP 모델 로딩 또는 추론 실패 시
        """
        # 입력 검증
        if not image_base64:
            raise ValueError("image_base64 is required")
        if not prompt:
            raise ValueError("prompt is required")
        if model_type not in ["openai", "koclip"]:
            raise ValueError("model_type must be 'openai' or 'koclip'")

        # 이미지 디코딩
        image = self._decode_base64_image(image_base64)

        if model_type == "openai":
            return self._calculate_openai_clip_score(image, prompt, auto_unload)
        else:  # koclip
            return self._calculate_koclip_score(image, prompt, auto_unload)

    def _calculate_openai_clip_score(
        self, image: Image.Image, prompt: str, auto_unload: bool = False
    ) -> float:
        """OpenAI CLIP으로 점수 계산"""
        # 모델 로딩 (첫 호출 시에만)
        self._load_clip_model()

        try:
            import clip

            # 1. 이미지 전처리
            image_tensor = self._clip_preprocess(image).unsqueeze(0).to(self._device)

            # 2. 텍스트 토큰화
            text_tensor = clip.tokenize([prompt]).to(self._device)

            # 3. 특징 추출 및 코사인 유사도 계산
            with torch.no_grad():
                image_features = self._clip_model.encode_image(image_tensor)
                text_features = self._clip_model.encode_text(text_tensor)

                # 벡터 정규화 (L2 norm)
                image_features /= image_features.norm(dim=-1, keepdim=True)
                text_features /= text_features.norm(dim=-1, keepdim=True)

                # 코사인 유사도
                similarity = (image_features @ text_features.T).item()

            logger.debug(
                f"[ClipService] OpenAI CLIP Score: {similarity:.4f} | Prompt: {prompt[:50]}..."
            )

            result = float(similarity)

            # Auto unload
            if auto_unload:
                logger.info("[ClipService] Auto-unloading OpenAI CLIP model")
                self.unload_model(model_type="openai")

            return result

        except Exception as e:
            logger.error(f"[ClipService] Failed to calculate OpenAI CLIP Score: {e}")
            raise RuntimeError(f"OpenAI CLIP Score calculation failed: {e}")

    def _calculate_koclip_score(
        self, image: Image.Image, prompt: str, auto_unload: bool = False
    ) -> float:
        """KoCLIP으로 점수 계산 (한글 프롬프트 지원)"""
        # 모델 로딩 (첫 호출 시에만)
        self._load_koclip_model()

        try:
            # 1. 이미지와 텍스트 전처리
            inputs = self._koclip_processor(
                text=[prompt], images=image, return_tensors="pt", padding=True
            )

            # 디바이스로 이동
            inputs = {k: v.to(self._device) for k, v in inputs.items()}

            # 2. 특징 추출 및 유사도 계산
            with torch.no_grad():
                outputs = self._koclip_model(**inputs)

                # KoCLIP은 logits_per_image를 직접 반환 (0~100 스케일)
                logits_per_image = outputs.logits_per_image

                # 0~1 범위로 정규화
                similarity = logits_per_image.item() / 100.0

            logger.debug(
                f"[ClipService] KoCLIP Score: {similarity:.4f} | Prompt: {prompt[:50]}..."
            )

            result = float(similarity)

            # Auto unload
            if auto_unload:
                logger.info("[ClipService] Auto-unloading KoCLIP model")
                self.unload_model(model_type="koclip")

            return result

        except Exception as e:
            logger.error(f"[ClipService] Failed to calculate KoCLIP Score: {e}")
            raise RuntimeError(f"KoCLIP Score calculation failed: {e}")

    @staticmethod
    def interpret_score(score: float) -> str:
        """
        CLIP Score 해석

        Args:
            score (float): CLIP Score

        Returns:
            str: 점수에 대한 해석 메시지
        """
        if score >= 0.7:
            return "매우 높은 일치도 - 이미지가 텍스트 설명과 강하게 부합합니다."
        elif score >= 0.5:
            return "높은 일치도 - 이미지와 텍스트가 잘 연관되어 있습니다."
        elif score >= 0.3:
            return "중간 일치도 - 이미지와 텍스트 간 어느 정도 연관성이 있습니다."
        elif score >= 0.0:
            return "낮은 일치도 - 이미지와 텍스트 간 연관성이 약합니다."
        else:
            return "매우 낮은 일치도 - 이미지와 텍스트가 거의 무관합니다."

    def unload_model(
        self, model_type: Literal["openai", "koclip", "all"] = "all"
    ) -> None:
        """
        모델 메모리 해제 (필요 시)

        Args:
            model_type (str): 해제할 모델 타입
                - "openai": OpenAI CLIP만 해제
                - "koclip": KoCLIP만 해제
                - "all": 모든 모델 해제 (기본값)
        """
        if model_type in ["openai", "all"] and self._clip_model is not None:
            logger.info("[ClipService] Unloading OpenAI CLIP model")
            del self._clip_model
            del self._clip_preprocess
            self._clip_model = None
            self._clip_preprocess = None

        if model_type in ["koclip", "all"] and self._koclip_model is not None:
            logger.info("[ClipService] Unloading KoCLIP model")
            del self._koclip_model
            del self._koclip_processor
            self._koclip_model = None
            self._koclip_processor = None

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info(f"[ClipService] Model(s) unloaded: {model_type}")
