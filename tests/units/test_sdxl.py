
import sys
import os
import traceback
from PIL import Image, ImageDraw, ImageFont

# Add src to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from nanoCocoa_aiserver.models.sdxl_text import SDXLTextGenerator
from nanoCocoa_aiserver.utils import pil_canny_edge, get_font_path

def test_sdxl_text(log_func, sdxl_gen):
    """
    Tests SDXLTextGenerator.
    """
    sdxl_text = None
    try:
        print("Testing SDXLTextGenerator...")
        # Create Dummy Canny
        W, H = 1024, 1024
        text_guide = Image.new("RGB", (W, H), "black")
        draw = ImageDraw.Draw(text_guide)
        try:
             # Use the utility function to get the font path
             font_path = get_font_path("NanumMyeongjo-YetHangul.ttf")
             font = ImageFont.truetype(font_path, 150)
        except:
             font = ImageFont.load_default()
        
        draw.text((100, 400), "바나나", font=font, fill="white")
        canny_map = pil_canny_edge(text_guide)
        log_func("4. Text Canny Map", "Success", canny_map, "Generated Canny Map")

        # Use fixture instead of new instance
        # sdxl_gen = SDXLTextGenerator() 
        sdxl_text = sdxl_gen.generate_text_effect(canny_map, "Made of gold, shiny, metallic", "low quality")
        log_func("4. SDXL Text Effect", "Success", sdxl_text, "3D Text Generated")
    except Exception as e:
        log_func("4. SDXLTextGenerator", "Error", None, f"{e}\n{traceback.format_exc()}")
    

