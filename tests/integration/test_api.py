
import sys
import os
import time
import base64
from fastapi.testclient import TestClient

# Add src to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from nanoCocoa_aiserver.main import app
from nanoCocoa_aiserver.utils import base64_to_pil

def run_api_tests(test_image_path, log_func):
    """
    Tests FastAPI endpoints integration.
    """
    print("Testing FastAPI... ")
    
    client = TestClient(app)
    
    # 1. Font List
    try:
        resp = client.get("/fonts")
        assert resp.status_code == 200
        fonts = resp.json()['fonts']
        log_func("6. API /fonts", "Success", None, f"Found {len(fonts)} fonts")
    except Exception as e:
        log_func("6. API /fonts", "Error", None, str(e))

    # 2. Generate Workflow
    job_id = None
    try:
        with open(test_image_path, "rb") as img_file:
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
            log_func("7. API /generate", "Started", None, f"Job ID: {job_id}")
        else:
            log_func("7. API /generate", "Failed", None, f"Status: {resp.status_code}, {resp.text}")
            return
            
    except Exception as e:
        log_func("7. API /generate", "Error", None, str(e))
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
                    log_func("8. API Job Status", "Completed", None, f"Progress: {progress}%")
                    break
                elif status in ('failed', 'stopped'):
                    log_func("8. API Job Status", "Failed/Stopped", None, f"Status: {status}")
                    break
                
                time.sleep(5)
            except Exception as e:
                log_func("8. API Job Status", "Polling Error", None, str(e))
                break
        
        if final_result_b64:
            api_img = base64_to_pil(final_result_b64)
            log_func("9. API Final Result", "Success", api_img, "API generation complete")
        else:
             log_func("9. API Final Result", "Missing", None, "No final result returned")
