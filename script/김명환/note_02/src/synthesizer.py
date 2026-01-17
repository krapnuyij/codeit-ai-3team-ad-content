"""
객체 합성 모듈: FLUX.1-Fill + IP-Adapter를 사용한 자연스러운 객체 배치
Object Synthesis Module: Natural object placement using FLUX.1-Fill + IP-Adapter
"""

import torch
from PIL import Image
from diffusers import FluxFillPipeline
from diffusers.models import FluxTransformer2DModel
from transformers import BitsAndBytesConfig
from typing import Optional, Union
from pathlib import Path
import logging

# Try to import helper_dev_utils, fallback to standard logging if not available
try:
    from helper_dev_utils import get_auto_logger
    logger = get_auto_logger()
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

from .utils import flush_gpu


class ObjectSynthesizer:
    """
    FLUX.1-Fill-dev를 사용하여 자연스러운 조명과 그림자로
    객체를 배경에 합성하는 클래스

    이 클래스는 인페인팅을 수행하여 마스크된 영역에 새로운 객체를 생성하며,
    주변 조명 및 원근감과의 일관성을 유지합니다.

    Note:
        - 현재 IP-Adapter는 비활성화되어 있습니다 (diffusers 미통합)
        - 객체 특징은 프롬프트에 상세히 기술해야 합니다

    Attributes:
        base_model (str): FLUX.1-Fill-dev 모델 이름
        ip_adapter_model (str): IP-Adapter 모델 이름 (예약됨, 현재 미사용)
        device (str): 모델 실행 디바이스
        torch_dtype: 모델 가중치 데이터 타입
        pipe: FLUX Fill 파이프라인 인스턴스
    """

    def __init__(
        self,
        base_model: str = "black-forest-labs/FLUX.1-Fill-dev",
        ip_adapter_model: str = "XLabs-AI/flux-ip-adapter-v2",
        device: str = None,
        torch_dtype: torch.dtype = torch.bfloat16,
        enable_ip_adapter: bool = True,
    ):
        """
        ObjectSynthesizer 초기화

        Args:
            base_model: FLUX.1-Fill-dev 모델 식별자
            ip_adapter_model: IP-Adapter 모델 식별자
            device: 모델 실행 디바이스 ('cuda' 또는 'cpu', 기본값: 자동 감지)
            torch_dtype: 모델 가중치 데이터 타입 (bfloat16 권장)
            enable_ip_adapter: IP-Adapter 활성화 여부 (기본값: True)
        """
        self.base_model = base_model
        self.ip_adapter_model = ip_adapter_model
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.torch_dtype = torch_dtype
        self.enable_ip_adapter = enable_ip_adapter
        self.ip_adapter_scale = 0.8  # 기본 IP-Adapter 스케일
        self.pipe = None  # 지연 로딩 (FluxFillPipeline)
        self.flux_pipe = None  # 지연 로딩 (FluxPipeline for IP-Adapter)

        print(f"🔧 ObjectSynthesizer 초기화")
        print(f"   베이스 모델: {base_model}")
        print(f"   IP-Adapter 모델: {ip_adapter_model}")
        print(f"   IP-Adapter 활성화: {'✓ 예' if enable_ip_adapter else '✗ 아니오'}")

    def _print_gpu_memory(self, stage: str = ""):
        """GPU 메모리 사용량을 출력하는 헬퍼 함수"""
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            stage_msg = f" [{stage}]" if stage else ""
            print(f"    GPU 메모리{stage_msg}: {allocated:.2f}GB 할당 / {reserved:.2f}GB 예약")

    def _load_model(self, with_ip_adapter: bool = False):
        """
        FLUX.1-Fill 파이프라인을 로드합니다.

        Args:
            with_ip_adapter: IP-Adapter를 함께 로드할지 여부
        """
        if self.pipe is None:
            print(f"  FLUX.1-Fill 파이프라인을 {self.device}에 로드 중...")

            # L4 GPU를 위한 8bit 양자화 설정
            quantization_config = BitsAndBytesConfig(
                load_in_8bit=True,
                bnb_8bit_compute_dtype=torch.bfloat16,
            )

            # 1단계: 베이스 트랜스포머를 8bit 양자화로 로드
            print(f"  트랜스포머 로드 중 (8bit 양자화)...")
            base_transformer = FluxTransformer2DModel.from_pretrained(
                self.base_model,
                subfolder="transformer",
                torch_dtype=self.torch_dtype,
                quantization_config=quantization_config,  # 8bit 양자화
            )
            self._print_gpu_memory("트랜스포머 로드 후")

            # 2단계: 양자화된 트랜스포머로 파이프라인 생성
            print(f"  파이프라인 생성 중...")
            self.pipe = FluxFillPipeline.from_pretrained(
                self.base_model,
                transformer=base_transformer,  # 양자화된 트랜스포머 사용
                torch_dtype=self.torch_dtype,
            )
            self._print_gpu_memory("파이프라인 생성 후")

            # 메모리 최적화 옵션 활성화
            if self.device == "cuda":
                # CPU 오프로딩: 사용하지 않는 컴포넌트를 자동으로 CPU로 이동
                self.pipe.enable_model_cpu_offload()
                # 어텐션 슬라이싱으로 VRAM 추가 절약 (1-2GB 절약)
                self.pipe.enable_attention_slicing()
                print(f"  ✓ Attention Slicing 활성화 (메모리 절약 모드)")
                self._print_gpu_memory("최적화 적용 후")

            # IP-Adapter 로드 (요청 시)
            # NOTE: FluxFillPipeline은 load_ip_adapter를 지원하지 않으므로
            # IP-Adapter는 2단계 파이프라인에서만 사용 가능
            if with_ip_adapter and self.enable_ip_adapter:
                print(f"  ⚠️  FluxFillPipeline은 IP-Adapter를 지원하지 않습니다.")
                print(f"  IP-Adapter를 사용하려면 use_two_stage=True로 설정하세요.")

            print(f"  ✓ FLUX.1-Fill 파이프라인 로드 완료 (8bit 양자화)")
            if not with_ip_adapter:
                print(f"  ⚠️  참고: IP-Adapter는 현재 비활성화 상태입니다.")

    def _unload_model(self):
        """VRAM 확보를 위해 파이프라인을 언로드합니다."""
        if self.pipe is not None:
            print("  FLUX.1-Fill 파이프라인 언로드 중...")
            if hasattr(self.pipe, "to"):
                self.pipe.to("cpu")
            del self.pipe
            self.pipe = None
            flush_gpu()  # GPU 캐시 정리

    def _prepare_reference_image(self, reference: Image.Image) -> Image.Image:
        """
        참조 이미지를 RGB로 변환합니다.

        IP-Adapter는 RGB 이미지를 입력으로 받으므로,
        RGBA나 다른 모드의 이미지를 RGB로 변환합니다.

        Args:
            reference: 참조 이미지 (PIL.Image)

        Returns:
            RGB 모드의 PIL.Image
        """
        if reference.mode == "RGBA":
            # 흰색 배경에 알파 채널을 사용하여 합성
            rgb_ref = Image.new("RGB", reference.size, (255, 255, 255))
            rgb_ref.paste(reference, mask=reference.split()[3])
            return rgb_ref
        elif reference.mode != "RGB":
            return reference.convert("RGB")
        return reference

    def _unload_flux_pipeline(self):
        """FluxPipeline을 언로드하여 VRAM을 확보합니다."""
        if hasattr(self, 'flux_pipe') and self.flux_pipe is not None:
            print("  FluxPipeline 언로드 중...")
            if hasattr(self.flux_pipe, "to"):
                self.flux_pipe.to("cpu")
            del self.flux_pipe
            self.flux_pipe = None
            flush_gpu()
            print("  ✓ FluxPipeline 언로드 완료")

    def _load_flux_pipeline(self):
        """
        1단계용 FluxPipeline + IP-Adapter를 로드합니다.

        이 파이프라인은 참조 이미지의 시각적 특징을 반영하여
        초기 합성 이미지를 생성합니다.
        """
        if self.flux_pipe is None:
            print(f"  FluxPipeline + IP-Adapter를 {self.device}에 로드 중...")

            from diffusers import FluxPipeline

            # FLUX.1-dev (text-to-image) 로드
            print(f"  FLUX.1-dev 파이프라인 생성 중...")
            self.flux_pipe = FluxPipeline.from_pretrained(
                "black-forest-labs/FLUX.1-dev",
                torch_dtype=self.torch_dtype,
            )
            self._print_gpu_memory("FluxPipeline 로드 후")

            # 메모리 최적화 활성화
            if self.device == "cuda":
                self.flux_pipe.enable_model_cpu_offload()
                self.flux_pipe.enable_attention_slicing()
                print(f"  ✓ 메모리 최적화 활성화")
                self._print_gpu_memory("최적화 적용 후")

            # IP-Adapter 로드
            print(f"  IP-Adapter 로드 중: {self.ip_adapter_model}")
            self.flux_pipe.load_ip_adapter(
                self.ip_adapter_model,
                weight_name="ip_adapter.safetensors",
                image_encoder_pretrained_model_name_or_path="openai/clip-vit-large-patch14"
            )
            self._print_gpu_memory("IP-Adapter 로드 후")

            # IMPORTANT: IP-Adapter의 이미지 인코더를 명시적으로 GPU로 이동
            # CPU offloading과 함께 사용할 때 device mismatch를 방지하기 위함
            if self.device == "cuda" and hasattr(self.flux_pipe, 'image_encoder'):
                print(f"  이미지 인코더를 GPU로 이동 중...")
                self.flux_pipe.image_encoder.to(self.device, dtype=self.torch_dtype)
                print(f"  ✓ 이미지 인코더 GPU 이동 완료")

            # IP-Adapter 스케일 설정
            self.flux_pipe.set_ip_adapter_scale(self.ip_adapter_scale)

            print(f"  ✓ FluxPipeline + IP-Adapter 로드 완료")
            print(f"  ✓ IP-Adapter 스케일: {self.ip_adapter_scale}")

    def _stage1_ip_adapter_generation(
        self,
        background: Image.Image,
        mask: Image.Image,
        reference: Image.Image,
        prompt: str,
        ip_adapter_scale: float,
        seed: Optional[int],
    ) -> Image.Image:
        """
        1단계: IP-Adapter를 사용하여 참조 이미지 특징을 반영한 초기 합성 생성

        Args:
            background: 배경 이미지
            mask: 마스크 이미지 (현재는 정보용으로만 사용)
            reference: 참조 이미지 (제품의 깨끗한 이미지)
            prompt: 장면 설명 프롬프트
            ip_adapter_scale: IP-Adapter 강도 (0.0-1.0)
            seed: 랜덤 시드

        Returns:
            참조 이미지 특징이 반영된 초기 합성 이미지
        """
        print(f"\n  [1단계] IP-Adapter로 참조 이미지 특징 반영 중...")

        # FluxPipeline + IP-Adapter 로드
        self._load_flux_pipeline()

        # 참조 이미지를 RGB로 변환
        reference_rgb = self._prepare_reference_image(reference)
        print(f"  참조 이미지 크기: {reference_rgb.size}, 모드: {reference_rgb.mode}")

        # 시드 설정
        generator = torch.Generator(device=self.device).manual_seed(seed) if seed else None

        # IP-Adapter로 생성
        print(f"  IP-Adapter로 이미지 생성 중...")
        print(f"  프롬프트: {prompt[:80]}...")
        output = self.flux_pipe(
            prompt=prompt,
            ip_adapter_image=reference_rgb,
            height=background.size[1],
            width=background.size[0],
            num_inference_steps=28,
            guidance_scale=3.5,
            generator=generator,
        )

        stage1_image = output.images[0]
        print(f"  ✓ 1단계 완료: 참조 이미지 특징이 반영된 이미지 생성됨")

        # 메모리 확보
        self._unload_flux_pipeline()

        return stage1_image

    def _stage2_fill_refinement(
        self,
        stage1_image: Image.Image,
        mask: Image.Image,
        prompt: str,
        num_inference_steps: int,
        guidance_scale: float,
        seed: Optional[int],
    ) -> Image.Image:
        """
        2단계: FluxFillPipeline으로 마스크 경계를 자연스럽게 다듬기

        Args:
            stage1_image: 1단계에서 생성된 이미지
            mask: 마스크 이미지
            prompt: 장면 설명 프롬프트
            num_inference_steps: 디노이징 스텝 수
            guidance_scale: CFG 스케일
            seed: 랜덤 시드

        Returns:
            마스크 경계가 자연스럽게 다듬어진 최종 이미지
        """
        print(f"\n  [2단계] FluxFill로 마스크 경계 자연스럽게 다듬기...")

        # FluxFillPipeline 로드
        self._load_model()

        # 시드 설정
        generator = torch.Generator(device=self.device).manual_seed(seed) if seed else None

        # 인페인팅으로 다듬기
        print(f"  인페인팅 실행 중...")
        output = self.pipe(
            prompt=prompt,
            image=stage1_image,  # 1단계 결과를 배경으로 사용
            mask_image=mask,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            generator=generator,
            height=stage1_image.size[1],
            width=stage1_image.size[0],
        )

        final_image = output.images[0]
        print(f"  ✓ 2단계 완료: 자연스러운 경계 블렌딩 완료")

        # 메모리 확보
        self._unload_model()

        return final_image

    def fill_in_object(
        self,
        background: Union[Image.Image, str, Path],
        mask: Union[Image.Image, str, Path],
        reference: Union[Image.Image, str, Path],
        prompt: str,
        num_inference_steps: int = 28,
        guidance_scale: float = 3.5,
        ip_adapter_scale: float = 0.8,
        seed: Optional[int] = None,
        use_two_stage: bool = True,
    ) -> Image.Image:
        """
        마스크된 위치에 참조 객체를 배경에 합성합니다.

        Args:
            background: 배경 이미지 (PIL.Image 또는 경로)
            mask: 객체를 배치할 위치를 나타내는 이진 마스크 (PIL.Image 또는 경로)
            reference: 객체의 깨끗한 참조 이미지 (IP-Adapter로 특징 반영)
            prompt: 최종 장면의 텍스트 설명
            num_inference_steps: 디노이징 스텝 수 (기본값: 28)
            guidance_scale: CFG 스케일 (기본값: 3.5)
            ip_adapter_scale: IP-Adapter 강도 (0.0-1.0, 기본값: 0.8)
            seed: 재현 가능성을 위한 랜덤 시드
            use_two_stage: 2단계 파이프라인 사용 여부 (기본값: True)

        Returns:
            최종 합성된 이미지 (PIL.Image)

        실행 방식:
            1. 2단계 파이프라인 (IP-Adapter 사용, 메모리 많이 필요):
               - use_two_stage=True, enable_ip_adapter=True
               - FluxPipeline(IP-Adapter) → FluxFillPipeline 순차 실행
               - 참조 이미지의 시각적 특징을 반영하여 자연스럽게 합성
               - 메모리: ~22GB+ (모델 2개, 순차 로드/언로드)

            2. 단일 파이프라인 (텍스트만, 메모리 효율적):
               - use_two_stage=False (IP-Adapter 무시)
               - FluxFillPipeline만 사용
               - 참조 이미지 무시, 텍스트 프롬프트만 사용
               - 메모리: ~11GB (모델 1개)
               - ⚠️ FluxFillPipeline은 IP-Adapter를 지원하지 않음

        Note:
            - FluxFillPipeline은 load_ip_adapter 메서드를 지원하지 않습니다
            - IP-Adapter를 사용하려면 반드시 use_two_stage=True로 설정해야 합니다
            - 단일 파이프라인(use_two_stage=False)은 텍스트 프롬프트만 사용합니다

        Example:
            >>> # 2단계 파이프라인 (IP-Adapter 사용, 메모리 많이 필요)
            >>> synthesizer = ObjectSynthesizer(enable_ip_adapter=True)
            >>> result = synthesizer.fill_in_object(
            ...     background=bg_image,
            ...     mask=mask_image,
            ...     reference=clean_product,
            ...     prompt="갈색 유리병의 맥주, 따뜻한 바 조명의 나무 테이블 위",
            ...     use_two_stage=True,  # IP-Adapter 사용
            ...     seed=42
            ... )
            >>>
            >>> # 단일 파이프라인 (텍스트만, 메모리 효율적)
            >>> result = synthesizer.fill_in_object(
            ...     background=bg_image,
            ...     mask=mask_image,
            ...     reference=clean_product,  # 무시됨
            ...     prompt="갈색 유리병의 맥주, 따뜻한 바 조명의 나무 테이블 위",
            ...     use_two_stage=False,  # 텍스트만 사용
            ...     seed=42
            ... )
        """
        try:
            # 경로가 제공된 경우 이미지 로드
            background = self._load_image_if_path(background)
            mask = self._load_image_if_path(mask)
            reference = self._load_image_if_path(reference)

            # 마스크를 'L' 모드(그레이스케일)로 변환
            if mask.mode != "L":
                mask = mask.convert("L")

            # 참조 이미지를 RGB로 변환
            reference = self._prepare_reference_image(reference)

            print(f"\n{'='*60}")
            print(f"  객체 합성 시작")
            print(f"  배경 크기: {background.size}")
            print(f"  참조 이미지 크기: {reference.size}")
            print(f"  프롬프트: {prompt[:80]}...")
            print(f"  IP-Adapter 활성화: {self.enable_ip_adapter}")
            print(f"  2단계 파이프라인: {use_two_stage}")
            print(f"  IP-Adapter 스케일: {ip_adapter_scale}")
            print(f"{'='*60}\n")

            # IP-Adapter 사용 여부에 따른 실행 방식 결정
            if use_two_stage and self.enable_ip_adapter:
                # ===== 2단계 하이브리드 파이프라인 (메모리 많이 필요) =====
                print(f"  ⚠️  2단계 파이프라인 실행 (메모리 사용량 높음)")

                # 1단계: IP-Adapter로 참조 이미지 특징 반영
                stage1_result = self._stage1_ip_adapter_generation(
                    background=background,
                    mask=mask,
                    reference=reference,
                    prompt=prompt,
                    ip_adapter_scale=ip_adapter_scale,
                    seed=seed,
                )

                # 2단계: FluxFill로 마스크 경계 다듬기
                final_result = self._stage2_fill_refinement(
                    stage1_image=stage1_result,
                    mask=mask,
                    prompt=prompt,
                    num_inference_steps=num_inference_steps,
                    guidance_scale=guidance_scale,
                    seed=seed,
                )

                print(f"\n{'='*60}")
                print(f"  ✓ 2단계 파이프라인 완료!")
                print(f"  참조 이미지의 특징이 최종 결과에 반영되었습니다.")
                print(f"{'='*60}\n")

                return final_result

            else:
                # ===== 기존 방식: 텍스트 프롬프트만 사용 =====
                print(f"  ⚠️  기존 방식 실행 (IP-Adapter 미사용)")
                print(f"  참조 이미지는 무시됩니다.")

                # 모델 로드
                self._load_model(with_ip_adapter=False)

                # 재현성을 위한 시드 설정
                if seed is not None:
                    generator = torch.Generator(device=self.device).manual_seed(seed)
                else:
                    generator = None

                # 인페인팅 실행 (텍스트만 사용)
                output = self.pipe(
                    prompt=prompt,
                    image=background,
                    mask_image=mask,
                    num_inference_steps=num_inference_steps,
                    guidance_scale=guidance_scale,
                    generator=generator,
                    height=background.size[1],
                    width=background.size[0],
                )

                result = output.images[0]
                print(f"  ✓ 기존 방식 합성 완료")

                return result

        finally:
            # VRAM 확보를 위해 항상 모델 언로드
            self._unload_model()
            self._unload_flux_pipeline()

    def _load_image_if_path(self, image: Union[Image.Image, str, Path]) -> Image.Image:
        """경로가 제공된 경우 이미지를 로드하는 헬퍼 함수"""
        if isinstance(image, (str, Path)):
            from .utils import load_image

            return load_image(image)
        return image

    def __del__(self):
        """객체 소멸 시 정리 작업"""
        self._unload_model()
        self._unload_flux_pipeline()
