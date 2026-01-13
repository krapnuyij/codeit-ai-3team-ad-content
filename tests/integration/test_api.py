import sys
import os
import time
import base64
from fastapi.testclient import TestClient

# Add src to sys.path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src"))
)
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../src/nanoCocoa_aiserver")
    ),
)

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
        fonts = resp.json()["fonts"]
        assert len(fonts) > 0, "No fonts found"
        log_func("6. API /fonts", "Success", None, f"Found {len(fonts)} fonts")

        # Test font file access
        first_font = fonts[0]
        font_resp = client.get(f"/fonts/{first_font}")
        assert font_resp.status_code == 200, f"Cannot access font file: {first_font}"
        assert font_resp.headers["content-type"] in [
            "font/ttf",
            "font/otf",
            "application/octet-stream",
        ], f"Invalid font content-type: {font_resp.headers.get('content-type')}"
        log_func(
            "6.1. API Font File Access",
            "Success",
            None,
            f"Font file accessible: {first_font}",
        )

    except Exception as e:
        log_func("6. API /fonts", "Error", None, str(e))

    # 2. Generate Workflow
    job_id = None
    try:
        with open(test_image_path, "rb") as img_file:
            img_bytes = img_file.read()
            b64_img = base64.b64encode(img_bytes).decode("utf-8")

        payload = {
            "input_image": b64_img,
            "bg_prompt": "A delicious yellow banana lying on aa wooden table",
            "text_model_prompt": "Gold texture",
            "text_content": "BANANA",
            "start_step": 1,
            "seed": 42,
        }

        resp = client.post("/generate", json=payload)
        if resp.status_code == 200:
            job_id = resp.json()["job_id"]
            log_func("7. API /generate", "Started", None, f"Job ID: {job_id}")
        else:
            log_func(
                "7. API /generate",
                "Failed",
                None,
                f"Status: {resp.status_code}, {resp.text}",
            )
            return

    except Exception as e:
        log_func("7. API /generate", "Error", None, str(e))
        return

    # 3. Polling Status
    if job_id:
        final_result_b64 = None
        start_time = time.time()
        while time.time() - start_time < 300:  # Wait up to 5 mins
            try:
                resp = client.get(f"/status/{job_id}")
                data = resp.json()
                status = data["status"]
                progress = data["progress_percent"]

                if status == "completed":
                    final_result_b64 = data.get("final_result")
                    log_func(
                        "8. API Job Status", "Completed", None, f"Progress: {progress}%"
                    )
                    break
                elif status in ("failed", "stopped"):
                    log_func(
                        "8. API Job Status", "Failed/Stopped", None, f"Status: {status}"
                    )
                    break

                time.sleep(5)
            except Exception as e:
                log_func("8. API Job Status", "Polling Error", None, str(e))
                break

        if final_result_b64:
            api_img = base64_to_pil(final_result_b64)
            log_func(
                "9. API Final Result", "Success", api_img, "API generation complete"
            )
        else:
            log_func("9. API Final Result", "Missing", None, "No final result returned")


def test_fonts_endpoint():
    """Test GET /fonts endpoint"""
    client = TestClient(app)
    resp = client.get("/fonts")
    assert resp.status_code == 200
    data = resp.json()
    assert "fonts" in data
    assert len(data["fonts"]) > 0
    print(f"✓ Font list API: Found {len(data['fonts'])} fonts")


def test_font_file_access():
    """Test font file static access via /fonts/{path}"""
    client = TestClient(app)

    # Get font list first
    resp = client.get("/fonts")
    assert resp.status_code == 200
    fonts = resp.json()["fonts"]
    assert len(fonts) > 0

    # Test accessing first font file
    first_font = fonts[0]
    font_resp = client.get(f"/fonts/{first_font}")
    assert font_resp.status_code == 200, f"Cannot access font: {first_font}"
    assert len(font_resp.content) > 0, "Font file is empty"
    print(f"✓ Font file access: {first_font} ({len(font_resp.content)} bytes)")


def test_dashboard_endpoint():
    """Test GET /example_generation endpoint returns HTML or 404 if disabled"""
    client = TestClient(app)
    resp = client.get("/example_generation")

    # Dashboard may be disabled via ENABLE_DEV_DASHBOARD env var
    if resp.status_code == 404:
        print("⚠ Dashboard disabled (ENABLE_DEV_DASHBOARD=false)")
        return

    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    # Check for any dashboard-related content
    assert len(resp.text) > 0
    print("✓ Dashboard endpoint accessible")


def test_server_reset_endpoint():
    """Test POST /server-reset endpoint for development use"""
    client = TestClient(app)

    # Create a test job first
    gen_resp = client.post("/generate", json={"test_mode": True})
    assert gen_resp.status_code == 200
    job_id = gen_resp.json()["job_id"]
    print(f"✓ Created test job: {job_id}")

    # Reset server
    reset_resp = client.post("/server-reset")
    assert reset_resp.status_code == 200
    reset_data = reset_resp.json()

    # Verify response structure
    assert reset_data["status"] == "success"
    assert "statistics" in reset_data
    stats = reset_data["statistics"]
    assert "deleted_jobs" in stats
    assert "stopped_jobs" in stats
    assert "terminated_processes" in stats
    assert "elapsed_sec" in stats

    print(f"✓ Server reset completed:")
    print(f"  - Deleted jobs: {stats['deleted_jobs']}")
    print(f"  - Stopped jobs: {stats['stopped_jobs']}")
    print(f"  - Terminated processes: {stats['terminated_processes']}")
    print(f"  - Elapsed: {stats['elapsed_sec']}s")

    # Verify all jobs cleared
    jobs_resp = client.get("/jobs")
    assert jobs_resp.status_code == 200
    jobs_data = jobs_resp.json()
    assert jobs_data["total_jobs"] == 0, "Jobs not cleared after reset"
    print("✓ All jobs cleared after reset")


def test_generate_endpoint_validation():
    """Test POST /generate endpoint accepts request (validation happens in worker)"""
    client = TestClient(app)

    # Test with minimal valid payload (will fail in worker but API accepts it)
    resp = client.post("/generate", json={"test_mode": True})
    assert resp.status_code == 200  # API accepts, validation in worker
    assert "job_id" in resp.json()
    print("✓ Generate endpoint accepts requests")
