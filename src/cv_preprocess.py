import cv2
import numpy as np
from pathlib import Path

SAMPLE = Path("data/samples/plan1.png")
OUT = Path("data/samples/edges_plan1.png")

def load_grayscale(path: Path):
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {path}")
    return img

def enhance_and_edges(gray):
    blur = cv2.GaussianBlur(gray, (3,3), 0)
    norm = cv2.normalize(blur, None, 0, 255, cv2.NORM_MINMAX)
    edges = cv2.Canny(norm, 50, 150, apertureSize=3)
    return edges

if __name__ == "__main__":
    g = load_grayscale(SAMPLE)
    e = enhance_and_edges(g)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT), e)
    print(f"Saved edges to {OUT}")
