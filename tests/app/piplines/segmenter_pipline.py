import torch
import numpy as np
import cv2
from PIL import Image, ImageFilter
from transformers import AutoModelForImageSegmentation
from pathlib import Path

class SegmenterPipeline:
    def __init__(self, device="cuda"):
        self.device = device if torch.cuda.is_available() else "cpu"
        # BiRefNet 설정
        self.repo = "ZhengPeng7/BiRefNet"
        self.model = self._load_model(self.repo)
        print(f"✅ Segmenter Pipeline Loaded: {self.repo} on {self.device}")

    def _load_model(self, repo):
        return AutoModelForImageSegmentation.from_pretrained(
            repo, trust_remote_code=True
        ).to(self.device).eval()

    def _preprocess_contrast(self, img_pil):
        """흰색 용기 경계 인식을 위한 대비 강화 (CLAHE)"""
        img_cv = np.array(img_pil.convert("RGB"))
        lab = cv2.cvtColor(img_cv, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        enhanced_img = cv2.merge((cl, a, b))
        enhanced_img = cv2.cvtColor(enhanced_img, cv2.COLOR_LAB2RGB)
        return Image.fromarray(enhanced_img)

    def _post_mask_refined(self, out, size):
        """마스크 정밀화 로직 (Morphology + Blur)"""
        mask_raw = torch.sigmoid(out)[0, 0].cpu().numpy()
        mask_raw = (mask_raw * 255).astype(np.uint8)
        mask_raw = cv2.resize(mask_raw, size, interpolation=cv2.INTER_LANCZOS4)
        
        _, mask_thresh = cv2.threshold(mask_raw, 15, 255, cv2.THRESH_BINARY)
        
        kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
        
        mask_dilated = cv2.dilate(mask_thresh, kernel_dilate, iterations=1)
        mask_closed = cv2.morphologyEx(mask_dilated, cv2.MORPH_CLOSE, kernel_close)
        
        mask_soft = cv2.GaussianBlur(mask_closed, (11, 11), 0)
        
        final_mask_np = cv2.addWeighted(mask_raw, 0.4, mask_soft, 0.6, 0)
        final_mask_np = np.clip(final_mask_np * 1.25, 0, 255).astype(np.uint8)
        
        return Image.fromarray(final_mask_np)

    def process(self, img_pil):
        """메인 실행 함수"""
        W, H = img_pil.size
        
        # 1. 전처리
        img_input = self._preprocess_contrast(img_pil)
        
        # 2. 인퍼런스
        x = img_input.resize((1024, 1024))
        x = torch.from_numpy(np.array(x)).permute(2, 0, 1).float() / 255
        x = x.unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            out = self.model(x)
            logits = out.logits if hasattr(out, "logits") else out[-1]
        
        # 3. 후처리
        mask = self._post_mask_refined(logits, (W, H))
        
        # 4. 결과 생성
        fg = img_pil.convert("RGBA")
        fg.putalpha(mask)
        
        return fg, mask