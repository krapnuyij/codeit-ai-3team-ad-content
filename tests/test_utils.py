
import os

import os
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import io
import base64

def save_image(image: Image.Image, path: str):
    image.save(path)

def calculate_histogram(image: Image.Image, output_path: str = None):
    # Use PIL histogram
    # Returns [r0, ..., r255, g0, ..., g255, b0, ..., b255] for RGB
    hist_values = image.histogram()
    colors = ['r', 'g', 'b']
    
    plt.figure()
    plt.title('Color Histogram')
    plt.xlabel('Bins')
    plt.ylabel('# of Pixels')
    
    if image.mode == 'RGB':
        for i, color in enumerate(colors):
            # Extract the 256 values for this channel
            channel_hist = hist_values[i*256 : (i+1)*256]
            plt.plot(channel_hist, color=color, alpha=0.7)
            plt.xlim([0, 256])
    elif image.mode == 'L':
         plt.plot(hist_values, color='k')
         plt.xlim([0, 256])
         
    if output_path:
        plt.savefig(output_path)
        plt.close()
    
    return hist_values

def compare_histograms(hist1, hist2):
   pass


def generate_markdown_report(report_path, title, results):
    """
    results: list of dicts with keys: Step, Status, ImagePath, HistogramPath, Remarks
    """
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# {title}\n\n")
        f.write("| Step | Status | Result Image | Histogram | Remarks |\n")
        f.write("|---|---|---|---|---|\n")
        for r in results:
            img_md = f"![img]({r.get('ImagePath', '')})" if r.get('ImagePath') else "-"
            hist_md = f"![hist]({r.get('HistogramPath', '')})" if r.get('HistogramPath') else "-"
            f.write(f"| {r['Step']} | {r['Status']} | {img_md} | {hist_md} | {r.get('Remarks', '')} |\n")

