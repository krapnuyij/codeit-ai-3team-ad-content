import torch
from diffusers import StableDiffusionXLPipeline
from app.pipelines.utils import (
    prepare_output_dir, save_candidates, save_params
)

MODEL_SDXL = "stabilityai/stable-diffusion-xl-base-1.0"


pipe = None


def run_sdxl(req):
    global pipe

    save_dir = prepare_output_dir()

    pipe = StableDiffusionXLPipeline.from_pretrained(
        MODEL_SDXL,
        torch_dtype=torch.float16
    ).to("cuda")

    generator = torch.Generator("cuda").manual_seed(req.seed)

    torch.cuda.reset_peak_memory_stats()

    result = pipe(
        prompt="korean market warm illustration poster design",
        negative_prompt="japanese text, chinese text, blur, messy layout",
        num_inference_steps=req.num_steps,
        guidance_scale=req.guidance,
        num_images_per_prompt=req.num_images,
        generator=generator
    )

    image_paths = save_candidates(result.images, save_dir)

    params = {
        "mode": "sdxl",
        "seed": req.seed,
        "steps": req.num_steps,
        "guidance": req.guidance,
        "output_dir": save_dir,
    }

    params_path = save_params(params, save_dir)

    return {
        "output_dir": save_dir,
        "images": image_paths,
        "params_path": params_path
    }
