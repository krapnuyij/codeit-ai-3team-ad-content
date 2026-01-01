
import sys
import os
import traceback
from PIL import Image

# Add src to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from nanoCocoa_aiserver.models.flux_generator import FluxGenerator

def test_flux_bg(prompt, seed, log_func, flux_gen):
    """
    Tests FluxGenerator Background Generation.
    """
    flux_bg = None
    if flux_gen is None:
        flux_gen = FluxGenerator()
    try:
        print("Testing FluxGenerator (Background)...")
        flux_bg = flux_gen.generate_background(prompt, seed=seed)
        log_func("2. Flux Background", "Success", flux_bg, f"Prompt: {prompt}")
    except Exception as e:
        log_func("2. Flux Background", "Error", None, f"{e}\n{traceback.format_exc()}")
    # return flux_gen, flux_bg

def test_flux_refine(flux_gen, seg_result, flux_bg, log_func):
    """
    Tests FluxGenerator Refinement.
    """
    flux_refined = None
    try:
        if seg_result and flux_bg:
            print("Testing FluxGenerator (Refinement)...")
            # Composite first (simple paste)
            bg_w, bg_h = flux_bg.size
            fg = seg_result.resize((int(bg_w*0.5), int(bg_h*0.5)))
            comp = flux_bg.copy().convert("RGBA")
            fg_layer = Image.new("RGBA", comp.size)
            fg_layer.paste(fg, (250, 250))
            comp = Image.alpha_composite(comp, fg_layer).convert("RGB")
            
            # Refine (progress_callback 테스트 포함)
            if not flux_gen:
                flux_gen = FluxGenerator()
            
            # progress_callback 테스트용 함수
            def test_progress_callback(step, total, sub_step_name):
                print(f"[Test Progress] {sub_step_name}: {step}/{total}")
                
            flux_refined = flux_gen.refine_image(
                draft_image=comp,
                prompt="A banana on a wooden table",
                strength=0.6,
                seed=42,
                progress_callback=test_progress_callback
            )
            log_func("3. Flux Refinement", "Success", flux_refined, "Refined composite image with progress_callback")
        else:
             log_func("3. Flux Refinement", "Skipped", None, "Missing inputs (Segmentation or Flux BG)")
    except Exception as e:
        log_func("3. Flux Refinement", "Error", None, f"{e}\n{traceback.format_exc()}")
        
    # return flux_refined

def test_flux_feature_injection(flux_gen, seg_result, flux_bg, log_func):
    """
    Tests FluxGenerator Feature Injection (inject_features_via_inpaint).
    """
    flux_injected = None
    try:
        if seg_result and flux_bg:
            print("Testing FluxGenerator (Feature Injection)...")
            
            if not flux_gen:
                flux_gen = FluxGenerator()
            
            # 상품 배치 계산
            bg_w, bg_h = flux_bg.size
            scale = 0.4
            fg_resized = seg_result.resize(
                (int(seg_result.width * scale), int(seg_result.height * scale)), 
                Image.LANCZOS
            )
            x = (bg_w - fg_resized.width) // 2
            y = int(bg_h * 0.55)
            
            # 상품 마스크 생성
            product_mask = Image.new("L", flux_bg.size, 0)
            if seg_result.mode == "RGBA":
                alpha = seg_result.split()[3]
                alpha_resized = alpha.resize(fg_resized.size, Image.LANCZOS)
                product_mask.paste(alpha_resized, (x, y))
            else:
                # 누끼 결과가 L 모드일 경우
                mask_resized = seg_result.convert("L").resize(fg_resized.size, Image.LANCZOS)
                product_mask.paste(mask_resized, (x, y))
            
            # progress_callback 테스트용 함수
            def test_progress_callback(step, total, sub_step_name):
                print(f"[Test Progress] {sub_step_name}: {step}/{total}")
            
            # Feature Injection 실행
            flux_injected = flux_gen.inject_features_via_inpaint(
                background=flux_bg,
                product_foreground=fg_resized.convert("RGBA") if fg_resized.mode != "RGBA" else fg_resized,
                product_mask=product_mask,
                position=(x, y),
                prompt="A photorealistic product lying naturally on the surface with heavy shadows",
                negative_prompt="floating, disconnected, unrealistic shadows",
                strength=0.5,
                guidance_scale=3.5,
                num_inference_steps=28,
                seed=42,
                progress_callback=test_progress_callback
            )
            log_func("3.5. Flux Feature Injection", "Success", flux_injected, "Feature injection with inpainting")
        else:
            log_func("3.5. Flux Feature Injection", "Skipped", None, "Missing inputs (Segmentation or Flux BG)")
    except Exception as e:
        log_func("3.5. Flux Feature Injection", "Error", None, f"{e}\n{traceback.format_exc()}")
