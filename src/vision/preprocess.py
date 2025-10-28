# src/vision/preprocess.py
"""
Week 5 · Day 20 — Image Preprocessing for OCR
- grayscale
- denoise (median)
- adaptive threshold (binarize)
- optional deskew (Hough-lines based)
Saves an intermediate image ready for OCR.

Usage:
  python src/vision/preprocess.py --input data/samples/plan1.jpg --out runs/test/preproc.png --deskew
"""

import argparse
from pathlib import Path
import cv2
import numpy as np


def ensure_dir(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)


def load_image(path: Path) -> np.ndarray:
    img = cv2.imread(str(path))
    if img is None:
        raise SystemExit(f"[ERR] Could not read input image: {path}")
    # If image is very large, downscale to keep processing snappy (max 3000 px longest side)
    h, w = img.shape[:2]
    longest = max(h, w)
    if longest > 3000:
        scale = 3000.0 / longest
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        print(f"[info] Downscaled to {img.shape[1]}x{img.shape[0]} for processing.")
    return img


def to_grayscale(img: np.ndarray) -> np.ndarray:
    if len(img.shape) == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def denoise(gray: np.ndarray, ksize: int = 3) -> np.ndarray:
    # Median blur preserves edges (dimension text, thin lines)
    return cv2.medianBlur(gray, ksize)


def binarize(gray: np.ndarray) -> np.ndarray:
    # Adaptive threshold works well on uneven lighting / scanned plans
    th = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 7
    )
    return th


def find_skew_angle(bin_img: np.ndarray) -> float:
    """
    Estimate page skew using Hough line angles.
    Returns angle in degrees (positive = rotate CCW to correct).
    """
    # Work on edges
    edges = cv2.Canny(bin_img, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=140)
    if lines is None or len(lines) == 0:
        return 0.0

    # Collect angles near horizontal text/lines (around 0 or 180 deg)
    angles = []
    for rho_theta in lines[:200]:  # limit to speed up
        rho, theta = rho_theta[0]
        angle_deg = (theta * 180 / np.pi) - 90  # convert to [-90, +90] w.r.t horizontal
        # Accept near-horizontal families (text, dimension lines)
        if -45 <= angle_deg <= 45:
            angles.append(angle_deg)

    if not angles:
        return 0.0

    # Use median for robustness
    median_angle = float(np.median(angles))
    # We want to rotate the image by negative of this to deskew
    return -median_angle


def rotate_image(img: np.ndarray, angle_deg: float) -> np.ndarray:
    (h, w) = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return rotated


def preprocess(input_path: Path, output_path: Path, deskew: bool = False) -> None:
    print(f"[run] Preprocess: {input_path}  {output_path} (deskew={deskew})")
    ensure_dir(output_path)

    # 1) load
    img = load_image(input_path)

    # 2) grayscale
    gray = to_grayscale(img)

    # 3) denoise (mild)
    gray = denoise(gray, ksize=3)

    # 4) adaptive threshold (binary: text/lines dark → black, background → white)
    bw = binarize(gray)

    # 5) optional deskew on binary, then re-threshold (crisper after rotate)
    if deskew:
        angle = find_skew_angle(bw)
        if abs(angle) > 0.2:
            print(f"[info] Deskewing by {angle:.2f}°")
            bw = rotate_image(bw, angle)
        else:
            print("[info] Deskew angle small; skipping rotate.")

    # 6) Save
    ok = cv2.imwrite(str(output_path), bw)
    if not ok:
        raise SystemExit(f"[ERR] Failed to write output: {output_path}")
    print(f"[OK] Preprocessed image saved → {output_path}")


def main():
    ap = argparse.ArgumentParser(description="Week 5 Day 20: Image preprocessing")
    ap.add_argument("--input", required=True, help="Path to the input plan image (jpg/png)")
    ap.add_argument("--out", required=True, help="Where to save the preprocessed image (png recommended)")
    ap.add_argument("--deskew", action="store_true", help="Try to auto-deskew using Hough lines")
    args = ap.parse_args()

    preprocess(Path(args.input), Path(args.out), deskew=args.deskew)


if __name__ == "__main__":
    main()
