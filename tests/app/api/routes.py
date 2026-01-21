import time
import json
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from PIL import Image
import io

from app.models.request import GenerateRequest
from app.pipelines.sdxl_pipeline import SDXLPipeline
from app.pipelines.segmenter_pipeline import SegmenterPipeline

router = APIRouter(prefix="/api/v1")

segmenter = SegmenterPipeline()
composer = SDXLPipeline()

def get_presets():
    preset_path = Path("configs/presets.json")
    if not preset_path.exists():
        return {}
    with open(preset_path, "r", encoding="utf-8") as f:
        return json.load(f)

@router.post("/generate-all")
async def generate_all(
    file: UploadFile = File(...),
    req: GenerateRequest = Depends()
):
    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]
    
    try:
        presets = get_presets()
        if req.preset_name not in presets:
            raise HTTPException(status_code=400, detail="Invalid preset name")
        
        config = presets[req.preset_name]
        config['strength'] = req.strength if req.strength else config.get('strength', 0.28)
        config['controlnet_scale'] = req.control_scale if req.control_scale else config.get('controlnet_scale', 0.5)

        input_data = await file.read()
        input_img = Image.open(io.BytesIO(input_data)).convert("RGB")

        fg, mask = segmenter.process(input_img)

        bg_path = Path(f"data/backgrounds/{req.preset_name}.png")
        if bg_path.exists():
            bg_img = Image.open(bg_path).convert("RGB")
        else:
            bg_img = Image.new("RGB", fg.size, (255, 255, 255))

        if req.mode == "sdxl":
            final_result = composer.process(
                background=bg_img,
                foreground=fg,
                mask=mask,
                config=config
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported mode for full pipeline")

        output_dir = Path("outputs/compose")
        output_dir.mkdir(parents=True, exist_ok=True)
        save_path = output_dir / f"result_{request_id}.png"
        final_result.save(save_path, quality=95)

        latency_ms = int((time.time() - start_time) * 1000)
        
        return {
            "status": "success",
            "request_id": request_id,
            "mode": req.mode,
            "latency_ms": latency_ms,
            "image_url": f"/static/{save_path.name}",
            "config_used": config
        }

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))