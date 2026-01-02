
import sys
import os
import shutil
import time
import datetime
import traceback
from PIL import Image, ImageDraw, ImageFont
from FastAPI.testclient import TestClient
import logging
from concurrent.futures import ThreadPoolExecutor

# Add src to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

try:
    from nanoCocoa_aiserver.main import app, JOBS
    from nanoCocoa_aiserver.AIModelEngine import AIModelEngine
    from nanoCocoa_aiserver.models.segmentation import SegmentationModel
    from nanoCocoa_aiserver.models.flux_generator import FluxGenerator
    from nanoCocoa_aiserver.models.sdxl_text import SDXLTextGenerator
    from nanoCocoa_aiserver.utils import pil_to_base64, base64_to_pil, pil_canny_edge
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

# Import local utils
try:
    from test_utils import save_image, calculate_histogram, generate_markdown_report
except ImportError:
    # If running from root
    sys.path.append(os.path.join(os.path.dirname(__file__)))
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
        filename = f"{step.lower().replace(' ','_')}.png"
        img_path = os.path.join(ARTIFACTS_DIR, filename)
        save_image(image, img_path)
        
        hist_filename = f"hist_{step.lower().replace(' ','_')}.png"
        hist_path = os.path.join(ARTIFACTS_DIR, hist_filename)
        calculate_histogram(image, hist_path)
        
        # Make relative for report
        img_path = os.path.relpath(img_path, REPORT_DIR)
        hist_path = os.path.relpath(hist_path, REPORT_DIR)

    RESULTS.append({
        "Step": step,
        "Status": status,
        "ImagePath": img_path,
        "HistogramPath": hist_path,
        "Remarks": remarks
    })
    logger.info(f"[{step}] {status} - {remarks}")

def run_unit_tests():
    logger.info("Starting Unit Tests...")
    
    # 0. Load Input Image
    try:
        if not os.path.exists(TEST_IMAGE_PATH):
            logger.error(f"Test image not found at {TEST_IMAGE_PATH}")
            return
        
        input_image = Image.open(TEST_IMAGE_PATH).convert("RGB")
        log_result("0. Input Image", "Success", input_image, "Loaded banana.png")
    except Exception as e:
        log_result("0. Input Image", "Error", None, str(e))
        return

    # 1. Test SegmentationModel
    seg_result = None
    seg_mask = None
    try:
        logger.info("Testing SegmentationModel...")
        seg_model = SegmentationModel()
        seg_result, seg_mask = seg_model.run(input_image)
        log_result("1. Segmentation Result", "Success", seg_result, "Background removed")
        log_result("1. Segmentation Mask", "Success", seg_mask, "Mask generated")
    except Exception as e:
        log_result("1. SegmentationModel", "Error", None, f"{e}\n{traceback.format_exc()}")

    # 2. Test FluxGenerator (Background)
    flux_bg = None
    flux_gen = FluxGenerator()
    try:
        logger.info("Testing FluxGenerator (Background)...")
        prompt = "A delicious yellow banana lying on a wooden table, sunlight, photorealistic, 8k"
        flux_bg = flux_gen.generate_background(prompt, seed=42)
        log_result("2. Flux Background", "Success", flux_bg, f"Prompt: {prompt}")
    except Exception as e:
        log_result("2. Flux Background", "Error", None, f"{e}\n{traceback.format_exc()}")

    # 3. Test FluxGenerator (Refine)
    flux_refined = None
    try:
        if seg_result and flux_bg:
            logger.info("Testing FluxGenerator (Refinement)...")
            # Composite first (simple paste)
            bg_w, bg_h = flux_bg.size
            fg = seg_result.resize((int(bg_w*0.5), int(bg_h*0.5)))
            comp = flux_bg.copy().convert("RGBA")
            fg_layer = Image.new("RGBA", comp.size)
            fg_layer.paste(fg, (250, 250))
            comp = Image.alpha_composite(comp, fg_layer).convert("RGB")
            
            # Refine (progress_callback 포함)
            def test_progress_callback(step, total, sub_step_name):
                logger.info(f"[Test Progress] {sub_step_name}: {step}/{total}")
                
            flux_refined = flux_gen.refine_image(
                draft_image=comp,
                prompt="A banana on a wooden table",
                strength=0.6,
                seed=42,
                progress_callback=test_progress_callback
            )
            log_result("3. Flux Refinement", "Success", flux_refined, "Refined composite image with progress_callback")
        else:
             log_result("3. Flux Refinement", "Skipped", None, "Missing inputs (Segmentation or Flux BG)")
    except Exception as e:
        log_result("3. Flux Refinement", "Error", None, f"{e}\n{traceback.format_exc()}")
        
    # 4. Test SDXLTextGenerator
    sdxl_text = None
    try:
        logger.info("Testing SDXLTextGenerator...")
        # Create Dummy Canny
        W, H = 1024, 1024
        text_guide = Image.new("RGB", (W, H), "black")
        draw = ImageDraw.Draw(text_guide)
        try:
             font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 150)
        except:
             font = ImageFont.load_default()
        
        draw.text((100, 400), "BANANA", font=font, fill="white")
        canny_map = pil_canny_edge(text_guide)
        log_result("4. Text Canny Map", "Success", canny_map, "Generated Canny Map")

        sdxl_gen = SDXLTextGenerator()
        sdxl_text = sdxl_gen.generate_text_effect(canny_map, "Made of gold, shiny, metallic", "low quality")
        log_result("4. SDXL Text Effect", "Success", sdxl_text, "3D Text Generated")
    except Exception as e:
        log_result("4. SDXLTextGenerator", "Error", None, f"{e}\n{traceback.format_exc()}")

    # 5. Test AIModelEngine (Integration)
    try:
        logger.info("Testing AIModelEngine Integration...")
        engine = AIModelEngine()
        # Just run segmentation again to prove it works via wrapper
        eng_seg, _ = engine.run_segmentation(input_image)
        log_result("5. Engine Integration", "Success", eng_seg, "Engine.run_segmentation executed")
    except Exception as e:
        log_result("5. Engine Integration", "Error", None, f"{e}\n{traceback.format_exc()}")

    return flux_refined # Return refined image for comparison if needed

def run_fastapi_tests(reference_image=None):
    logger.info("Testing FastAPI... (Mocking GPU tasks usually, but here we run real inference if possible or mocked)")
    
    # Note: Running real inference via FastAPI in this script might be heavy and cause OOM if we don't clear GPU carefully.
    # The 'utils.flush_gpu' handles it, but concurrent usage is risky.
    # Since we are running sequentially, it should be fine.
    
    client = TestClient(app)
    
    # 1. Font List
    try:
        resp = client.get("/fonts")
        assert resp.status_code == 200
        fonts = resp.json()['fonts']
        log_result("6. API /fonts", "Success", None, f"Found {len(fonts)} fonts")
    except Exception as e:
        log_result("6. API /fonts", "Error", None, str(e))

    # 2. Generate Workflow
    job_id = None
    try:
        with open(TEST_IMAGE_PATH, "rb") as img_file:
            img_bytes = img_file.read()
            b64_img = base64.b64encode(img_bytes).decode('utf-8')

        payload = {
            "input_image": b64_img,
            "bg_prompt": "A delicious yellow banana lying on aa wooden table",
            "text_model_prompt": "Gold texture",
            "text_content": "BANANA",
            "start_step": 1,
            "seed": 42
        }
        
        resp = client.post("/generate", json=payload)
        if resp.status_code == 200:
            job_id = resp.json()['job_id']
            log_result("7. API /generate", "Started", None, f"Job ID: {job_id}")
        else:
            log_result("7. API /generate", "Failed", None, f"Status: {resp.status_code}, {resp.text}")
            return
            
    except Exception as e:
        log_result("7. API /generate", "Error", None, str(e))
        return

    # 3. Polling Status
    if job_id:
        final_result_b64 = None
        start_time = time.time()
        while time.time() - start_time < 300: # Wait up to 5 mins
            try:
                resp = client.get(f"/status/{job_id}")
                data = resp.json()
                status = data['status']
                progress = data['progress_percent']
                
                if status == 'completed':
                    final_result_b64 = data.get('final_result')
                    log_result("8. API Job Status", "Completed", None, f"Progress: {progress}%")
                    break
                elif status in ('failed', 'stopped'):
                    log_result("8. API Job Status", "Failed/Stopped", None, f"Status: {status}")
                    break
                
                time.sleep(5)
            except Exception as e:
                log_result("8. API Job Status", "Polling Error", None, str(e))
                break
        
        if final_result_b64:
            api_img = base64_to_pil(final_result_b64)
            log_result("9. API Final Result", "Success", api_img, "API generation complete")
            # Histogram comparison
            # TODO: Compare with reference_image if available (e.g. flux_refined)
            # Not strictly comparable because API integration logic might differ slightly (e.g. positioning),
            # but we can check if it looks like an image.
        else:
             log_result("9. API Final Result", "Missing", None, "No final result returned")

def main():
    logger.info("Initializing Test Run...")
    
    # Run Unit Tests
    ref_image = run_unit_tests()
    
    # Run API Tests
    # We might need to restart app or ensure clean state? 
    # PROCESSES dict in main.py might persist if imported.
    # But since we use TestClient, it shares the module state.
    run_fastapi_tests(ref_image)
    
    # Generate Report
    generate_markdown_report(REPORT_FILE, f"Test Report {TIMESTAMP}", RESULTS)
    logger.info(f"Report generated at {REPORT_FILE}")
    print(f"REPORT_GENERATED: {REPORT_FILE}")

if __name__ == "__main__":
    main()
