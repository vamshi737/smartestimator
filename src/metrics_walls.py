# src/metrics_walls.py
import json, math, argparse
from pathlib import Path

import cv2
import numpy as np

# ---------- helpers ----------
def line_length_px(p1, p2):
    (x1, y1), (x2, y2) = p1, p2
    return float(math.hypot(x2 - x1, y2 - y1))

def classify_exterior(p1, p2, w, h, margin_px=30):
    # A line is "exterior" if any endpoint is close to the image border
    near_left   = (p1[0] <= margin_px) or (p2[0] <= margin_px)
    near_right  = (p1[0] >= w - margin_px) or (p2[0] >= w - margin_px)
    near_top    = (p1[1] <= margin_px) or (p2[1] <= margin_px)
    near_bottom = (p1[1] >= h - margin_px) or (p2[1] >= h - margin_px)
    return any([near_left, near_right, near_top, near_bottom])

def angle_deg(p1, p2):
    (x1, y1), (x2, y2) = p1, p2
    a = math.degrees(math.atan2((y2 - y1), (x2 - x1)))
    return (a + 180.0) % 180.0  # normalize to [0,180)

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", default="data/samples/PLAN1.png", help="original plan image (to know W,H)")
    ap.add_argument("--lines", default="data/samples/lines_scaled.json", help="scaled lines json")
    ap.add_argument("--margin", type=int, default=30, help="px margin for exterior classification")
    ap.add_argument("--out_json", default="data/samples/metrics_walls.json")
    ap.add_argument("--out_csv",  default="data/samples/metrics_walls.csv")
    ap.add_argument("--out_overlay", default="data/samples/lines_classified.png")
    args = ap.parse_args()

    # read size from plan image
    img = cv2.imread(args.img)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {args.img}")
    h, w = img.shape[:2]

    # read scaled lines
    with open(args.lines, "r", encoding="utf-8") as f:
        data = json.load(f)

    perpx = float(data.get("per_pixel", 1.0))
    unit  = data.get("unit", "px")
    lines = data.get("lines", [])

    # accumulators
    exterior = []
    interior = []
    total_len_real = 0.0
    total_ext_real = 0.0
    total_int_real = 0.0

    # build overlay
    overlay = img.copy()

    for i, L in enumerate(lines):
        p1 = tuple(L["p1"])
        p2 = tuple(L["p2"])
        length_px  = line_length_px(p1, p2)
        length_real = length_px * perpx

        # classify
        is_ext = classify_exterior(p1, p2, w, h, margin_px=args.margin)

        rec = {
            "index": i,
            "p1": list(p1),
            "p2": list(p2),
            "angle_deg": round(angle_deg(p1, p2), 2),
            "length_px": round(length_px, 2),
            f"length_{unit}": round(length_real, 3),
            "class": "exterior" if is_ext else "interior",
        }

        if is_ext:
            exterior.append(rec)
            total_ext_real += length_real
            cv2.line(overlay, p1, p2, (0, 0, 255), 2)  # red
        else:
            interior.append(rec)
            total_int_real += length_real
            cv2.line(overlay, p1, p2, (0, 165, 255), 2)  # orange

        total_len_real += length_real

    # perimeter (simple starter): use bounding box of all lines
    xs = [xy for L in lines for xy in (L["p1"][0], L["p2"][0])]
    ys = [xy for L in lines for xy in (L["p1"][1], L["p2"][1])]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    width_px  = maxx - minx
    height_px = maxy - miny
    perim_real = (2.0 * (width_px + height_px)) * perpx

    # outputs
    out = {
        "unit": unit,
        "per_pixel": perpx,
        "image_size": {"w": w, "h": h},
        "margin_px": args.margin,
        "counts": {"total": len(lines), "exterior": len(exterior), "interior": len(interior)},
        "totals": {
            f"sum_all_{unit}": round(total_len_real, 3),
            f"sum_exterior_{unit}": round(total_ext_real, 3),
            f"sum_interior_{unit}": round(total_int_real, 3),
            f"bbox_perimeter_{unit}": round(perim_real, 3)
        },
        "exterior": exterior,
        "interior": interior,
        "bbox_px": {"minx": int(minx), "maxx": int(maxx), "miny": int(miny), "maxy": int(maxy)}
    }

    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    # CSV
    import csv
    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        wcsv = csv.writer(f)
        wcsv.writerow(["index", "class", "angle_deg", "p1", "p2", "length_px", f"length_{unit}"])
        for L in exterior + interior:
            wcsv.writerow([L["index"], L["class"], L["angle_deg"], L["p1"], L["p2"], L["length_px"], L[f"length_{unit}"]])

    # overlay
    cv2.rectangle(overlay, (int(minx), int(miny)), (int(maxx), int(maxy)), (50, 200, 50), 2)
    cv2.imwrite(args.out_overlay, overlay)

    # stdout summary
    print(f"Unit: {unit} (per pixel = {perpx})")
    print(f"Lines: total={len(lines)}  exterior={len(exterior)}  interior={len(interior)}")
    print(f"Sum(all): {total_len_real:.2f} {unit}")
    print(f"Sum(exterior): {total_ext_real:.2f} {unit}")
    print(f"Sum(interior): {total_int_real:.2f} {unit}")
    print(f"BBox perimeter (starter): {perim_real:.2f} {unit}")
    print(f"Saved overlay   -> {args.out_overlay}")
    print(f"Saved metrics   -> {args.out_json}")
    print(f"Saved table     -> {args.out_csv}")

if __name__ == "__main__":
    main()
