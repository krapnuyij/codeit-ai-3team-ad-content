"""
Flux.2 Klein 기반 배경 생성 및 3D 합성 엔진.

이 모듈은 다음 기능을 수행:
1. 전경(누끼) 이미지 로드.
2. Flux.2 Klein 모델을 사용한 배경 생성.
3. OpenCV를 활용한 3D 원근감(Tilt) 효과 적용.
4. 최종 이미지 합성 및 저장.
"""

import gc
import logging
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Tuple

import cv2
import numpy as np
import torch
from PIL import Image

# -----------------------------------------------------------------------------
# 1. 설정 및 상수 (Configuration and Constants)
# -----------------------------------------------------------------------------

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("FluxEngine")

# 하드웨어 설정
DEVICE: str = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16

# 경로 설정
# 입력: 배경이 제거된 제품 이미지 경로
# 출력: 합성 완료된 이미지 저장 경로
INPUT_FG = Path("outputs/fg_cut")
OUT_COMP = Path("outputs/compose")
OUT_COMP.mkdir(parents=True, exist_ok=True)

# 모델 ID 설정 (Hugging Face Hub 경로)
MODEL_ID: str = "black-forest-labs/FLUX.2-klein-4B"

# 프롬프트 프리셋 (Prompt Presets)
PRESETS: Dict[str, str] = {
    "seollal_gift": (
        "high-quality commercial product photography composition for Korean "
        "Lunar New Year Seollal "
        # [구도] 극도로 가까운 하이앵글 샷
        "Perspective: An ultra-close-up, high-angle overhead shot. "
        "The rustic wooden table is positioned excessively close to the "
        "foreground, with its front edge cropped out by the bottom of the "
        "frame. "
        # [배경] 따뜻한 수묵화 스타일의 한옥 마을 풍경 (홍등/중국풍 장식 제거)
        "Background: Visible just beyond is a warm, hand-drawn Korean "
        "watercolor and ink wash painting (Sumukhwa) style scene. "
        "Scene: A traditional Hanok village with curved tiled roofs. "
        "(Clean roof eaves, NO red lanterns, NO hanging ornaments, "
        "NO Chinese style decorations) "
        # [캐릭터 & 자연물] 윷놀이하는 아이들과 소나무 위의 까치
        "Characters: A lively group of cute Korean children in colorful "
        "Saekdong Hanbok playing Yutnori. "
        "Nature: A pair of Korean Magpies (Kkachi) sitting on a twisted "
        "pine tree branch. "
        # [전경 소품] 왼쪽으로 흘러내리는 거대한 황금색 비단 보자기
        "Foreground: A gargantuan, ultra-oversized luxurious golden-yellow "
        "Korean silk Bojagi cloth is laid diagonally. "
        "The cloth is incredibly massive, biased massively towards the left "
        "side, cascading heavily off the left edge. "
        "Deep, heavy, natural folds create an overwhelming, asymmetrical "
        "textured landscape. "
        # [질감 및 분위기] 8k 포토리얼리즘, 시네마틱 라이팅, 한국적인 우아함
        "Texture: 8k photorealism, glistening silk texture under warm "
        "cinematic lighting "
        "Atmosphere: Soft morning sunlight, shallow depth of field. "
        "Clean, elegant, distinctly Korean."
    ),
}


# -----------------------------------------------------------------------------
# 2. 이미지 처리 유틸리티 (Image Processing Utilities)
# -----------------------------------------------------------------------------
class ImageProcessor:
    """OpenCV와 PIL을 사용한 이미지 전처리 및 후처리를 담당하는 클래스."""

    @staticmethod
    def load_rgba(path: Path) -> Image.Image:
        """이미지 파일을 로드하고 RGBA(투명도 포함) 모드로 변환."""
        return Image.open(path).convert("RGBA")

    @staticmethod
    def apply_perspective_tilt(
        pil_img: Image.Image,
        tilt_factor: float = 0.08,
        perspective_strength: float = 0.15
    ) -> Image.Image:
        """
        OpenCV를 사용하여 이미지에 3D 원근감(Tilt) 효과를 적용.
        
        Args:
            pil_img: 입력 PIL 이미지
            tilt_factor: 상하 기울기 강도 (y축 변형)
            perspective_strength: 원근감 강도
        """
        cv_img = np.array(pil_img)
        h, w = cv_img.shape[:2]

        # 변형될 좌표의 여백 계산
        pad_x = w * perspective_strength
        pad_y = h * tilt_factor

        # 변환 전 좌표 (직사각형 네 모서리)
        src_pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        
        # 변환 후 좌표 (사다리꼴 형태)
        # 상단은 안쪽으로 모으고, 하단은 바깥쪽으로 펼침
        dst_pts = np.float32(
            [
                [pad_x, pad_y],          # 좌상 (안쪽으로 이동)
                [w - pad_x, pad_y],      # 우상 (안쪽으로 이동)
                [w + pad_x * 0.5, h],    # 우하 (약간 바깥으로)
                [-pad_x * 0.5, h],       # 좌하 (약간 바깥으로)
            ]
        )

        # 투영 변환 행렬 계산 및 적용
        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
        warped_cv_img = cv2.warpPerspective(
            cv_img, matrix, (int(w + pad_x), h)
        )

        return Image.fromarray(warped_cv_img).convert("RGBA")

    @staticmethod
    def calculate_centered_position(
        bg_size: Tuple[int, int],
        fg_size: Tuple[int, int],
        y_ratio: float = 0.80
    ) -> Tuple[int, int]:
        """
        배경 이미지 내에서 객체가 중앙 하단에 위치하도록 좌표를 계산.
        
        Args:
            y_ratio: 세로 위치 비율 (0.80은 아래에서 20% 지점에 중심 배치)
        """
        bg_w, bg_h = bg_size
        fg_w, fg_h = fg_size
        pos_x = (bg_w - fg_w) // 2
        pos_y = int(bg_h * y_ratio) - (fg_h // 2)
        return (pos_x, pos_y)

    @staticmethod
    def get_unique_filepath(
        directory: Path, stem: str, ext: str = ".png"
    ) -> Path:
        """
        파일 덮어쓰기를 방지하기 위해 중복 시 _v1, _v2 접미사를 자동으로 추가.
        """
        target = directory / f"{stem}{ext}"
        if not target.exists():
            return target

        counter = 1
        while True:
            new_path = directory / f"{stem}_v{counter}{ext}"
            if not new_path.exists():
                return new_path
            counter += 1


# -----------------------------------------------------------------------------
# 3. AI 생성 엔진 (AI Generation Engine)
# -----------------------------------------------------------------------------
class FluxGenerator:
    """Flux 모델의 수명 주기(로드/언로드)와 이미지 생성 로직을 관리."""

    def __init__(self) -> None:
        self._pipe: Any = None
        self._pipeline_cls: Any = None
        self._check_library()

    def _check_library(self) -> None:
        """필수 라이브러리인 diffusers가 설치되어 있는지 확인."""
        try:
            from diffusers import FluxPipeline
            self._pipeline_cls = FluxPipeline
        except ImportError:
            logger.error("Diffusers 라이브러리가 설치되지 않았습니다.")
            sys.exit(1)

    def load_model(self) -> None:
        """
        모델을 메모리에 로드합니다. (Lazy Loading 방식)
        이미 로드되어 있다면 건너뜁니다.
        """
        if self._pipe is not None:
            return

        logger.info(f"모델 로드 중: {MODEL_ID}")
        self._pipe = self._pipeline_cls.from_pretrained(
            MODEL_ID,
            torch_dtype=DTYPE
        )
        # GPU VRAM 절약을 위해 모델을 CPU로 오프로드.
        self._pipe.enable_model_cpu_offload()
        logger.info("모델 로드 완료.")

    def unload_model(self) -> None:
        """모델을 메모리에서 해제하고 CUDA 캐시를 정리합니다."""
        if self._pipe:
            del self._pipe
            self._pipe = None

        if DEVICE == "cuda":
            torch.cuda.empty_cache()
            gc.collect()
        logger.info("메모리 정리 완료.")

    def generate_background(
        self, prompt: str, seed: int = 42
    ) -> Image.Image:
        """Flux 모델을 사용하여 배경 이미지를 생성합니다."""
        self.load_model()

        # 재현성을 위해 시드(Seed)를 고정.
        generator = torch.Generator(device=DEVICE).manual_seed(seed)
        logger.info(f"배경 생성 시작 (Seed: {seed})...")

        # 추론 실행
        result = self._pipe(
            prompt=prompt,
            height=1024,
            width=1024,
            guidance_scale=4.5,
            num_inference_steps=4,  # 스텝 수 4회 (속도 최적화)
            max_sequence_length=512,
            generator=generator,
        ).images[0]

        return result.convert("RGBA")

    def process_pipeline(
        self, fg_path: Path, preset_key: str = "seollal_gift"
    ) -> Image.Image:
        """
        전체 파이프라인 실행: 로드 -> 생성 -> 변형 -> 합성
        """
        # 1. 전경(제품) 이미지 로드
        fg_img = ImageProcessor.load_rgba(fg_path)

        # 2. 프롬프트 가져오기 및 배경 생성
        prompt = PRESETS.get(preset_key, "")
        if not prompt:
            raise ValueError(f"프리셋 '{preset_key}'를 찾을 수 없습니다.")

        bg_img = self.generate_background(prompt)

        # 3. 전경 전처리 (리사이즈 및 3D Tilt 효과)
        # 배경 크기의 약 65%로 리사이즈
        scale_ratio = 0.65
        target_w = int(bg_img.width * scale_ratio)
        target_h = int(target_w * (fg_img.height / fg_img.width))

        fg_resized = fg_img.resize((target_w, target_h), Image.LANCZOS)
        fg_tilted = ImageProcessor.apply_perspective_tilt(fg_resized)

        # 4. 최종 합성 (위치 계산 및 레이어 병합)
        pos = ImageProcessor.calculate_centered_position(
            bg_img.size, fg_tilted.size, y_ratio=0.80
        )

        final_comp = bg_img.copy()
        # 투명 레이어 생성 후 제품 붙여넣기
        comp_layer = Image.new("RGBA", bg_img.size, (0, 0, 0, 0))
        comp_layer.paste(fg_tilted, pos)

        # 알파 컴포지팅으로 최종 병합
        return Image.alpha_composite(final_comp, comp_layer)


# -----------------------------------------------------------------------------
# 4. 메인 실행 진입점 (Main Entry Point)
# -----------------------------------------------------------------------------
def main():
    # 입력 디렉토리 확인
    if not INPUT_FG.exists():
        logger.error(f"입력 디렉토리를 찾을 수 없습니다: {INPUT_FG}")
        return

    # PNG 파일 목록 가져오기
    files = sorted(INPUT_FG.glob("*.png"))
    if not files:
        logger.warning("처리할 PNG 파일이 없습니다.")
        return

    logger.info(f"총 {len(files)}개의 파일 처리를 시작합니다.")
    engine = FluxGenerator()

    for file_path in files:
        logger.info(f"처리 중: {file_path.name}")
        try:
            # 파이프라인 실행
            final_image = engine.process_pipeline(
                file_path, preset_key="seollal_gift"
            )

            # 결과 저장 (파일명 중복 방지 적용)
            save_name = f"{file_path.stem}_flux_final"
            save_path = ImageProcessor.get_unique_filepath(OUT_COMP, save_name)

            final_image.save(save_path)
            logger.info(f"저장 완료: {save_path}")

        except Exception as e:
            logger.error(f"{file_path.name} 처리 실패: {e}")
            logger.debug(traceback.format_exc())

    # 작업 완료 후 리소스 정리
    engine.unload_model()
    logger.info("모든 작업이 완료되었습니다.")


if __name__ == "__main__":
    main()