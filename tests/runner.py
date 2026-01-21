import sys
import os
import datetime
import traceback
import logging
from PIL import Image

# Add src to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

# Import Test Modules
from units.test_segmentation import test_segmentation
from units.test_flux import test_flux_bg, test_flux_refine
from units.test_sdxl import test_sdxl_text
from integration.test_api import run_api_tests

# Import Utils
try:
    from test_utils import save_image, calculate_histogram, generate_markdown_report
except ImportError:
    sys.path.append(os.path.dirname(__file__))
    from test_utils import save_image, calculate_histogram, generate_markdown_report


# Configuration
TEST_IMAGE_PATH = os.path.abspath("tests/banana.png")
REPORT_DIR = os.path.abspath(f"tests/reports")
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
REPORT_FILE = os.path.join(REPORT_DIR, f"test_{TIMESTAMP}.md")
ARTIFACTS_DIR = os.path.join(REPORT_DIR, f"artifacts_{TIMESTAMP}")

os.makedirs(ARTIFACTS_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestRunner")

RESULTS = []


def log_result(step, status, image=None, remarks=""):
    img_path = None
    hist_path = None

    if image:
        filename = f"{step.lower().replace(' ','_').replace('.','')}.png"
        img_path = os.path.join(ARTIFACTS_DIR, filename)
        save_image(image, img_path)

        hist_filename = f"hist_{step.lower().replace(' ','_').replace('.','')}.png"
        hist_path = os.path.join(ARTIFACTS_DIR, hist_filename)
        calculate_histogram(image, hist_path)

        # Make relative for report
        img_path = os.path.relpath(img_path, REPORT_DIR)
        hist_path = os.path.relpath(hist_path, REPORT_DIR)

    RESULTS.append(
        {
            "Step": step,
            "Status": status,
            "ImagePath": img_path,
            "HistogramPath": hist_path,
            "Remarks": remarks,
        }
    )
    logger.info(f"[{step}] {status} - {remarks}")


def main():
    logger.info("Initializing Test Run...")

    # 0. Load Input Image
    product_image = None
    try:
        if not os.path.exists(TEST_IMAGE_PATH):
            logger.error(f"Test image not found at {TEST_IMAGE_PATH}")
            return

        product_image = Image.open(TEST_IMAGE_PATH).convert("RGB")
        log_result("0. Input Image", "Success", product_image, "Loaded banana.png")
    except Exception as e:
        log_result("0. Input Image", "Error", None, str(e))
        return

    # 1. Run Unit Tests Sequentially

    # Segmentation
    seg_result, seg_mask = test_segmentation(product_image, log_result)

    # Flux Background and Refine
    flux_gen, flux_bg = test_flux_bg(
        "A delicious yellow banana lying on a wooden table, sunlight, photorealistic, 8k",
        42,
        log_result,
    )

    test_flux_refine(flux_gen, seg_result, flux_bg, log_result)

    # SDXL Text
    test_sdxl_text(log_result)

    # 2. Run API Tests
    run_api_tests(TEST_IMAGE_PATH, log_result)

    # 3. Generate Report
    generate_markdown_report(REPORT_FILE, f"Test Report {TIMESTAMP}", RESULTS)
    logger.info(f"Report generated at {REPORT_FILE}")
    print(f"REPORT_GENERATED: {REPORT_FILE}")


if __name__ == "__main__":
    main()
