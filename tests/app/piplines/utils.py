import os
import json
import time
from pathlib import Path
import torch
import cv2
from PIL import Image


OUTPUT_DIR = "outputs"
INPUT_DIR = Path("data/inputs")


def prepare_output_dir():
    run_name = f"run_{time.strftime('%Y%m%d_%H%M%S')}"
    save_dir = os.path.join(OUTPUT_DIR, "runs", run_name)
    os.makedirs(os.path.join(save_dir, "candidates"), exist_ok=True)
    return save_dir


def get_canny_or_none():
    image_files = sorted([
        *INPUT_DIR.glob("*.png"),
        *INPUT_DIR.glob("*.jpg"),
        *INPUT_DIR.glob("*.jpeg"),
        *INPUT_DIR.glob("*.webp"),
    ])

    if len(image_files) == 0:
        return None, False, None

    path = image_files[0]
    img = cv2.imread(str(path))

    if img is None:
        return None, False, None

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (512, 512))

    edges = cv2.Canny(img, 100, 200)

    return Image.fromarray(edges), True, str(path)


def save_candidates(images, save_dir):
    paths = []

    for i, img in enumerate(images, 1):
        path = os.path.join(save_dir, "candidates", f"candidate_v{i}.png")
        img.save(path)
        paths.append(path)

    return paths


def save_params(params, save_dir):
    params_path = os.path.join(save_dir, "params.json")
    with open(params_path, "w") as f:
        json.dump(params, f, indent=2)
    return params_path
