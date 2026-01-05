import time
from fastapi import APIRouter
from app.models.request import GenerateRequest
from app.pipelines.sd15_controlnet_pipeline import run_sd15_controlnet
from app.pipelines.sdxl_pipeline import run_sdxl

router = APIRouter(prefix="/api")


@router.post("/generate")
def generate(req: GenerateRequest):
    start = time.time()

    if req.mode == "sd15_controlnet":
        result = run_sd15_controlnet(req)
    else:
        result = run_sdxl(req)

    latency_ms = int((time.time() - start) * 1000)

    return {
        "mode": req.mode,
        "latency_ms": latency_ms,
        "output_dir": result["output_dir"],
        "images": result["images"],
        "params_path": result["params_path"]
    }
