"""
Base Model 추상 클래스.

모든 AI 모델의 공통 패턴(GPU 메모리 관리, 로깅)을 제공합니다.
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from abc import ABC, abstractmethod
from typing import Optional

from config import logger
from services.monitor import flush_gpu


class BaseAIModel(ABC):
    """
    모든 AI 모델의 기본 클래스입니다.

    GPU 메모리 정리 및 로깅을 자동화하는 Template Method 패턴을 사용합니다.
    """

    def __init__(self, model_name: str):
        """
        Args:
            model_name (str): 모델 이름 (로깅용)
        """
        self.model_name = model_name
        logger.info(f"[{self.model_name}] Initialized")

    def _pre_load(self) -> None:
        """
        모델 로딩 전 GPU 메모리를 정리합니다.
        """
        logger.debug(f"[{self.model_name}] Pre-loading GPU flush")
        flush_gpu()

    def _post_cleanup(self) -> None:
        """
        모델 사용 후 GPU 메모리를 정리합니다.
        """
        logger.debug(f"[{self.model_name}] Post-cleanup GPU flush")
        flush_gpu()

    @abstractmethod
    def _load_model(self):
        """
        모델을 로드하는 추상 메서드입니다.
        서브클래스에서 구현해야 합니다.

        Returns:
            모델 객체 (파이프라인, 트랜스포머 등)
        """
        pass

    @abstractmethod
    def _run_inference(self, model, *args, **kwargs):
        """
        추론을 실행하는 추상 메서드입니다.
        서브클래스에서 구현해야 합니다.

        Args:
            model: 로드된 모델 객체
            *args, **kwargs: 추론에 필요한 파라미터

        Returns:
            추론 결과
        """
        pass

    def execute(self, *args, **kwargs):
        """
        모델 로딩 → 추론 → 정리를 자동화하는 Template Method입니다.

        Args:
            *args, **kwargs: 추론에 필요한 파라미터

        Returns:
            추론 결과
        """
        logger.info(f"[{self.model_name}] Execution started")

        # Step 1: Pre-load cleanup
        self._pre_load()

        try:
            # Step 2: Load model
            logger.debug(f"[{self.model_name}] Loading model...")
            model = self._load_model()

            # Step 3: Run inference
            logger.debug(f"[{self.model_name}] Running inference...")
            result = self._run_inference(model, *args, **kwargs)

            logger.info(f"[{self.model_name}] Execution completed successfully")
            return result

        except Exception as e:
            logger.error(f"[{self.model_name}] Execution failed: {e}", exc_info=True)
            raise

        finally:
            # Step 4: Post-cleanup
            self._post_cleanup()
