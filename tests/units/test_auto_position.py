
import unittest
from unittest.mock import MagicMock
import sys
from PIL import Image, ImageDraw
import numpy as np
from pathlib import Path

# Mock torch and config to avoid import errors
sys.modules['torch'] = MagicMock()
sys.modules['config'] = MagicMock()
sys.modules['config'].logger = MagicMock()

# Add src to path
project_root = Path(__file__).resolve().parent.parent.parent / "src" / "nanoCocoa_aiserver"
sys.path.insert(0, str(project_root))

from utils.MaskGenerator import MaskGenerator
from utils.images import reposition_text_asset

class TestAutoPosition(unittest.TestCase):
    def test_recommend_position_top_empty(self):
        # Create image with empty (dark) top
        img = Image.new("L", (100, 300), 255) # White (occupied)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 100, 100], fill=0) # Black (empty) at top
        
        pos = MaskGenerator.recommend_position(img)
        print(f"Top empty -> Recommended: {pos}")
        self.assertEqual(pos, "top")

    def test_recommend_position_bottom_empty(self):
        # Create image with empty (dark) bottom
        img = Image.new("L", (100, 300), 255) # White
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 200, 100, 300], fill=0) # Black at bottom
        
        pos = MaskGenerator.recommend_position(img)
        print(f"Bottom empty -> Recommended: {pos}")
        self.assertEqual(pos, "bottom")

    def test_reposition_text_asset(self):
        # Create a text asset (transparent bg, small rect content)
        asset = Image.new("RGBA", (100, 300), (0,0,0,0))
        draw = ImageDraw.Draw(asset)
        # Content at top initially
        draw.rectangle([40, 0, 60, 20], fill=(255,0,0,255)) 
        
        # Move to bottom
        repositioned = reposition_text_asset(asset, "bottom", margin=10)
        
        # Check if content moved
        bbox = repositioned.getbbox()
        # image height 300. content height 21 (0-20 inclusive). margin 10.
        # expected y: 300 - 21 - 10 = 269
        expected_y = 269
        print(f"Repositioned bbox: {bbox}")
        self.assertTrue(bbox[1] == expected_y, f"Expected y={expected_y}, got {bbox[1]}")

if __name__ == '__main__':
    unittest.main()
