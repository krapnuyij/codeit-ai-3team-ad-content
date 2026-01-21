import requests
import argparse
import json

parser = argparse.ArgumentParser()

parser.add_argument("--mode", default="sd15_controlnet",
                    choices=["sd15_controlnet", "sdxl"])

args = parser.parse_args()

payload = {
    "mode": args.mode
}

res = requests.post("**test**/api/generate",
                    json=payload)

print(json.dumps(res.json(), indent=2, ensure_ascii=False))
