"""
AIModelEngine 단위 테스트
"""
import pytest
import sys
from pathlib import Path
from PIL import Image


# Mock dependencies
try:
    import torch
except ImportError:
    from unittest.mock import MagicMock
    sys.modules["torch"] = MagicMock()

try:
    import diffusers
except ImportError:
    from unittest.mock import MagicMock
    sys.modules["diffusers"] = MagicMock()

try:
    import transformers
except ImportError:
    from unittest.mock import MagicMock
    sys.modules["transformers"] = MagicMock()

# Add src path
src_path = Path(__file__).resolve().parents[2] / "src" / "nanoCocoa_aiserver"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


class TestAIModelEngineBasic:
    """AIModelEngine 기본 기능 테스트"""

    def test_import_aimodelengine(self):
        """AIModelEngine import 테스트"""
        from core.engine import AIModelEngine
        assert AIModelEngine is not None

    def test_init_dummy_mode(self):
        """Dummy mode 초기화 테스트"""
        from core.engine import AIModelEngine
        
        engine = AIModelEngine(dummy_mode=True)
        assert engine.dummy_mode is True
        assert engine.progress_callback is None

    def test_create_dummy_image(self):
        """Dummy 이미지 생성 테스트"""
        from core.engine import AIModelEngine
        
        engine = AIModelEngine(dummy_mode=True)
        img = engine._create_dummy_image(512, 512, "red")
        
        assert isinstance(img, Image.Image)
        assert img.size == (512, 512)
        assert img.mode == "RGB"

    def test_progress_callback(self):
        """Progress callback 설정 테스트"""
        from core.engine import AIModelEngine
        
        callback_called = []
        
        def mock_callback(step, total, name):
            callback_called.append((step, total, name))
        
        engine = AIModelEngine(dummy_mode=True, progress_callback=mock_callback)
        assert engine.progress_callback is not None
        
        # Test callback invocation
        engine.progress_callback(1, 3, "test_step")
        assert len(callback_called) == 1
        assert callback_called[0] == (1, 3, "test_step")


@pytest.mark.skipif(
    "config.getoption('dummy')",
    reason="Real engine tests require GPU and --no-dummy flag"
)
class TestAIModelEngineReal:
    """AIModelEngine 실제 모델 테스트 (GPU 필요)"""

    def test_init_real_mode(self):
        """Real mode 초기화 테스트"""
        from core.engine import AIModelEngine
        
        engine = AIModelEngine(dummy_mode=False)
        assert engine.dummy_mode is False
        assert hasattr(engine, 'segmenter')
        assert hasattr(engine, 'flux_gen')
        assert hasattr(engine, 'sdxl_gen')
        assert hasattr(engine, 'compositor')
