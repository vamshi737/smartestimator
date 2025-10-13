# src/area_contours.py
import cv2
import json
import math
import argparse
import numpy as np
from pathlib import Path

def load_scale(scale_json: Path):
    with open(scale_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    perpx = float(data.get("per_pixel", 1.0))
    unit  = data.get("unit", "px")
    return perpx, unit

def to_unit2(area_px2: float, perpx: float, unit: str):
    # area unit is (perpx^2) in linear unit^2
    area_u2 = area_px2 * (perpx ** 2)
    if unit.lower() in ["ft","feet","foot"]:
        return area_u2, "ft^2"
    if unit.lower() in ["m","meter","metre","metres","meters"]:
        return area_u2, "m^2"
    if unit.lower() in ["in","inch","inches"]:
        return area_u2, "in^2"
    # fallback
    return area_u2, f"{unit}^2"

def find_room_area_contour(gray: np.ndarray):
    """
    Starter heuristic:
    - Threshold to binary (lines dark on light background)
    - Invert so lines become white (foreground)
    - Find external contours; sort by area (descending)
    - Return the 2nd largest contour as "room" (inner cavity),
      falling back to the largest if only one is found.
    """
    # adaptive threshold is robust on scans
    bin_im = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 35, 10
    )
    # clean small gaps
    kernel = np.ones((3,3), np.uint8)
    bin_im = cv2.morphologyEx(bin_im, cv2.MORPH_CLOSE, kernel, iterations=2)

    # external contours only
    cnts, _ = cv2.findContours(bin_im, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None, bin_im

    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)
    if len(cnts) >= 2:
        return cnts[1], bin_im  # inner region (typical walls drawn as double lines)
    else:
        return cnts[0], bin_im  # fallback

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", default="data/samples/PLAN1.png", help="source floor plan image")
    ap.add_argument("--scale", default="data/samples/lines_scaled.json", help="scale JSON (per_pixel & unit)")
    ap.add_argument("--out_json", default="data/samples/metrics_area.json")
    ap.add_argument("--out_csv",  default="data/samples/metrics_area.csv")
    ap.add_argument("--out_overlay", default="data/samples/area_contours.png")
    args = ap.parse_args()

    img = cv2.imread(args.img, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {args.img}")

    perpx, unit = load_scale(Path(args.scale))

    cnt, bin_im = find_room_area_contour(img)
    if cnt is None:
        raise RuntimeError("No contours found for area")

    area_px2 = float(cv2.contourArea(cnt))
    # perimeter in pixels (debug info)
    peri_px = float(cv2.arcLength(cnt, True))

    area_u2, unit2 = to_unit2(area_px2, perpx, unit)
    peri_u  = peri_px * perpx

    # overlay for visual check
    color = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    cv2.drawContours(color, [cnt], -1, (0,0,255), 2)
    # put text
    label = f"Area ~ {area_u2:.2f} {unit2}"
    cv2.putText(color, label, (20,40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,0,255), 2, cv2.LINE_AA)

    Path(args.out_overlay).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(args.out_overlay, color)

    # JSON
    outj = {
        "unit_linear": unit,
        "unit_area": unit2,
        "per_pixel": perpx,
        "area_px2": area_px2,
        "area_u2": area_u2,
        "perimeter_px": peri_px,
        "perimeter_u": peri_u,
        "note": "Starter contour area (inner cavity heuristic)"
    }
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(outj, f, indent=2)

    # CSV (1-row summary)
    with open(args.out_csv, "w", encoding="utf-8", newline="") as f:
        f.write("per_pixel,unit_linear,unit_area,area_px2,area_u2,perimeter_px,perimeter_u\n")
        f.write(f"{perpx},{unit},{unit2},{area_px2},{area_u2},{peri_px},{peri_u}\n")

    print(f"Estimated area: {area_u2:.2f} {unit2}")
    print(f"Perimeter by contour: {peri_u:.2f} {unit}")
    print(f"Saved overlay  -> {args.out_overlay}")
    print(f"Saved JSON     -> {args.out_json}")
    print(f"Saved CSV      -> {args.out_csv}")

if __name__ == "__main__":
    main()
