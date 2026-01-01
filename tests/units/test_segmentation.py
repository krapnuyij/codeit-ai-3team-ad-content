
import sys
import os
import traceback
from PIL import Image

# Add src to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from nanoCocoa_aiserver.models.segmentation import SegmentationModel

def test_segmentation(input_image, log_func):
    """
    Tests the SegmentationModel.
    Args:
        input_image: PIL Image
        log_func: Function to log results (step, status, image, remarks)
    Returns:
        (result_image, mask_image) or (None, None)
    """
    seg_result = None
    seg_mask = None
    try:
        print("Testing SegmentationModel...")
        seg_model = SegmentationModel()
        seg_result, seg_mask = seg_model.run(input_image)
        log_func("1. Segmentation Result", "Success", seg_result, "Background removed")
        log_func("1. Segmentation Mask", "Success", seg_mask, "Mask generated")
    except Exception as e:
        log_func("1. SegmentationModel", "Error", None, f"{e}\n{traceback.format_exc()}")
    
    # return seg_result, seg_mask
