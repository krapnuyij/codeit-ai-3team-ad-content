import torch
from diffusers import (
    StableDiffusionPipeline,
    ControlNetModel,
    StableDiffusionControlNetPipeline,
)

from app.pipelines.utils import (
    prepare_output_dir, save_candidates, save_params, get_canny_or_none
)


MODEL_SD15 = "runwayml/stable-diffusion-v1-5"
MODEL_CONTROLNET = "lllyasviel/control_v11p_sd15_canny"


pipe = None
controlnet = None


def unload():
    global pipe, controlnet
    pipe = None
    controlnet = None
    torch.cuda.empty_cache()
    torch.cuda.ipc_collect()


def run_sd15_controlnet(req):
    global pipe, controlnet

    save_dir = prepare_output_dir()

    canny_img, ok, ref_img = get_canny_or_none()
    use_cnet = ok

    unload()

    if use_cnet:
        controlnet = ControlNetModel.from_pretrained(
            MODEL_CONTROLNET,
            torch_dtype=torch.float16
        ).to("cuda")

        pipe = StableDiffusionControlNetPipeline.from_pretrained(
            MODEL_SD15,
            controlnet=controlnet,
            torch_dtype=torch.float16
        ).to("cuda")

    else:
        pipe = StableDiffusionPipeline.from_pretrained(
            MODEL_SD15,
            torch_dtype=torch.float16
        ).to("cuda")

    generator = torch.Generator("cuda").manual_seed(req.seed)
    torch.cuda.reset_peak_memory_stats()

    if use_cnet:
        result = pipe(
            prompt="korean market dried seafood poster illustration",
            negative_prompt="japanese text, chinese text, logo, blur",
            image=canny_img,
            controlnet_conditioning_scale=req.control_scale,
            num_inference_steps=req.num_steps,
            guidance_scale=req.guidance,
            num_images_per_prompt=req.num_images,
            generator=generator,
        )
    else:
        result = pipe(
            prompt="korean market dried seafood poster illustration",
            negative_prompt="japanese text, chinese text, logo, blur",
            num_inference_steps=req.num_steps,
            guidance_scale=req.guidance,
            num_images_per_prompt=req.num_images,
            generator=generator,
        )

    image_paths = save_candidates(result.images, save_dir)

    params = {
            "mode": "sd15_controlnet" if use_cnet else "sd15",
            "seed": req.seed,
            "steps": req.num_steps,
            "guidance": req.guidance,
            "controlnet_scale": req.control_scale if use_cnet else None,
            "input_image": ref_img if use_cnet else None,
            "output_dir": save_dir,
        }

    params_path = save_params(params, save_dir)

    return {
        "output_dir": save_dir,
        "images": image_paths,
        "params_path": params_path
    }
