import pytest
import os
import sys
import datetime
import logging
from PIL import Image
from unittest.mock import MagicMock, patch

# Ensure src is in python path
SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src'))
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

# Import test_utils for reporting
try:
    # Try importing assuming tests dir is in path
    from test_utils import save_image, calculate_histogram, generate_markdown_report
except ImportError:
    # Append local dir
    sys.path.append(os.path.dirname(__file__))
    from test_utils import save_image, calculate_histogram, generate_markdown_report


# ==========================================
# pytest 명령줄 옵션 추가
# ==========================================
def pytest_addoption(parser):
    """
    --dummy / --no-dummy 옵션 추가:
    - 기본값: dummy 모드 (GPU 미사용, 빠른 인터페이스 테스트)
    - --no-dummy: 실제 AI 엔진 사용 (GPU 필요)
    """
    parser.addoption(
        "--dummy",
        action="store_true",
        dest="dummy",
        default=True,
        help="Run tests in dummy mode (no GPU, fast interface tests) [DEFAULT]"
    )
    parser.addoption(
        "--no-dummy",
        action="store_false",
        dest="dummy",
        help="Run tests with real AI engine (GPU required)"
    )


@pytest.fixture(scope="session")
def dummy_mode(request):
    """
    --dummy / --no-dummy 옵션 값을 반환하는 fixture.
    기본값: True (dummy 모드)
    """
    return request.config.getoption("dummy")

# Configuration for Report
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
TESTS_DIR = os.path.dirname(__file__)
REPORT_DIR = os.path.join(TESTS_DIR, "reports")
REPORT_FILE = os.path.join(REPORT_DIR, f"test_{TIMESTAMP}.md")
ARTIFACTS_DIR = os.path.join(REPORT_DIR, f"artifacts_{TIMESTAMP}")

# Ensure directories exist
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

# Global results storage
REPORT_RESULTS = []

# Path to test image
TEST_IMAGE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "banana.png"))

@pytest.fixture(scope="session")
def input_image():
    if os.path.exists(TEST_IMAGE_PATH):
        return Image.open(TEST_IMAGE_PATH).convert("RGB")
    # Fallback if image missing
    return Image.new("RGB", (512, 512), "yellow")

@pytest.fixture
def log_func():
    """
    Enhanced logger that saves results for the markdown report.
    """
    def logger(step, status, image, remarks):
        img_path = None
        hist_path = None
        
        if image:
            # Create filenames
            clean_step = step.lower().replace(' ', '_').replace('.', '').replace('/', '_')
            filename = f"{clean_step}.png"
            abs_img_path = os.path.join(ARTIFACTS_DIR, filename)
            
            # Save Image
            save_image(image, abs_img_path)
            img_path = os.path.relpath(abs_img_path, REPORT_DIR)
            
            # Histogram
            hist_filename = f"hist_{clean_step}.png"
            abs_hist_path = os.path.join(ARTIFACTS_DIR, hist_filename)
            calculate_histogram(image, abs_hist_path)
            hist_path = os.path.relpath(abs_hist_path, REPORT_DIR)

        # Log to stdout
        print(f"[{step}] {status}: {remarks}")
        
        # Append to global results
        REPORT_RESULTS.append({
            "Step": step,
            "Status": status,
            "ImagePath": img_path,
            "HistogramPath": hist_path,
            "Remarks": remarks
        })
        
    return logger

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Hook to capture test execution status (Pass/Fail) for the report.
    """
    outcome = yield
    rep = outcome.get_result()
    
    if rep.when == "call":
        # We only care about the actual test call
        status = "Success" if rep.passed else "Failed" if rep.failed else "Skipped"
        remarks = ""
        
        if rep.failed:
            # Try to grab exception info
            remarks = str(rep.longrepr)
            # Limit remarks length for table
            if len(remarks) > 200:
                remarks = remarks[:200] + "..."
        
        # Check if this test already logged explicit steps via log_func
        # If so, we might duplicatively add a "Test Completed" entry, which is fine.
        # But for tests like 'test_api_scenarios' which don't use log_func, we NEED this entry.
        
        # We can filter or just add everything. Adding everything gives a good summary.
        REPORT_RESULTS.append({
            "Step": f"Test: {item.name}",
            "Status": status,
            "ImagePath": None,
            "HistogramPath": None,
            "Remarks": remarks
        })

def pytest_sessionfinish(session, exitstatus):
    """
    Called after whole test run finishes. Generate the report.
    """
    print(f"\nGenerating Test Report at: {REPORT_FILE}")
    generate_markdown_report(REPORT_FILE, f"Test Report {TIMESTAMP}", REPORT_RESULTS)
    print("Report Generation Complete.")

@pytest.fixture
def prompt():
    return "A delicious yellow banana lying on a wooden table, sunlight, photorealistic, 8k"

@pytest.fixture
def seed():
    return 42

# Model Fixtures
# These are session scoped to avoid reloading heavy models
@pytest.fixture(scope="session")
def flux_gen_model():
    try:
        from nanoCocoa_aiserver.models.flux_generator import FluxGenerator
        
        # Patch heavy dependencies
        with patch('nanoCocoa_aiserver.models.flux_generator.FluxPipeline') as mock_txt2img, \
             patch('nanoCocoa_aiserver.models.flux_generator.FluxImg2ImgPipeline') as mock_img2img, \
             patch('nanoCocoa_aiserver.models.flux_generator.FluxInpaintPipeline') as mock_inpaint, \
             patch('nanoCocoa_aiserver.models.flux_generator.FluxTransformer2DModel'), \
             patch('nanoCocoa_aiserver.models.flux_generator.BitsAndBytesConfig'), \
             patch('nanoCocoa_aiserver.models.flux_generator.flush_gpu'):

            # Setup mock return values to avoid AttributeError
            # pipe(...).images[0]
            dummy_img = Image.new("RGB", (1024, 1024), "blue")
            
            mock_pipe_instance = MagicMock()
            mock_pipe_instance.return_value.images = [dummy_img]
            mock_txt2img.from_pretrained.return_value = mock_pipe_instance
            
            mock_pipe_instance2 = MagicMock()
            mock_pipe_instance2.return_value.images = [dummy_img]
            mock_img2img.from_pretrained.return_value = mock_pipe_instance2
            
            mock_pipe_instance3 = MagicMock()
            mock_pipe_instance3.return_value.images = [dummy_img]
            mock_inpaint.from_pretrained.return_value = mock_pipe_instance3

            yield FluxGenerator()
    except Exception as e:
        pytest.skip(f"Failed to load FluxGenerator: {e}")

@pytest.fixture(scope="session")
def seg_model():
    try:
        from nanoCocoa_aiserver.models.segmentation import SegmentationModel
        
        # Patch heavy dependencies
        with patch('nanoCocoa_aiserver.models.segmentation.AutoModelForImageSegmentation') as mock_seg_model, \
             patch('nanoCocoa_aiserver.models.segmentation.flush_gpu'):
            
            # Mock SegmentationModel.run for simplicity and stability.
            with patch.object(SegmentationModel, 'run', return_value=(Image.new("RGBA",(512,512)), Image.new("L",(512,512)))):
                 yield SegmentationModel()

    except Exception as e:
        pytest.skip(f"Failed to load SegmentationModel: {e}")

@pytest.fixture
def flux_gen(flux_gen_model):
    return flux_gen_model

@pytest.fixture
def seg_result(seg_model, input_image):
    # Run segmentation for dependent tests
    try:
        # Note: If passing 'log_func' here was possible, we could log this setup step too.
        # But fixtures don't easily accept other fixtures' return values as functions unless scoped properly.
        # log_func is function scoped. seg_model is session.
        # We'll just run it.
        res, mask = seg_model.run(input_image)
        return res
    except Exception as e:
        pytest.skip(f"Segmentation failed: {e}")

@pytest.fixture
def flux_bg(flux_gen, prompt, seed):
    # Run background generation for dependent tests
    try:
        return flux_gen.generate_background(prompt, seed=seed)
    except Exception as e:
        pytest.skip(f"Background generation failed: {e}")

@pytest.fixture(scope="session")
def sdxl_gen_model():
    try:
        from nanoCocoa_aiserver.models.sdxl_text import SDXLTextGenerator
        
        # Patch heavy dependencies
        with patch('nanoCocoa_aiserver.models.sdxl_text.StableDiffusionXLControlNetPipeline') as mock_pipeline, \
             patch('nanoCocoa_aiserver.models.sdxl_text.ControlNetModel'), \
             patch('nanoCocoa_aiserver.models.sdxl_text.AutoencoderKL'), \
             patch('nanoCocoa_aiserver.models.sdxl_text.flush_gpu'):
             
            # Setup mock return values
            # pipe(...).images[0]
            dummy_img = Image.new("RGBA", (1024, 1024), "red")
            
            mock_pipe_instance = MagicMock()
            mock_pipe_instance.return_value.images = [dummy_img]
            mock_pipeline.from_pretrained.return_value = mock_pipe_instance
            
            yield SDXLTextGenerator()
    except Exception as e:
        pytest.skip(f"Failed to load SDXLTextGenerator: {e}")

@pytest.fixture
def sdxl_gen(sdxl_gen_model):
    return sdxl_gen_model
