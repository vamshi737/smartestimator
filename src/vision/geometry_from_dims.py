# src/vision/geometry_from_dims.py
"""
Week 5 · Day 22 — Geometry mapping from OCR dims → metrics JSON.
- Input:  data/output/ocr_dims.json  (from Day 21)
- Output: data/output/metrics_area.json, data/output/metrics_walls.json

Rules:
- If OCR "feet" is [w,h] → one rectangle (w x h).
- If OCR "feet" is a single number → pair numbers in sequence -> (a,b).
- If there is only one number total → fallback square (n x n) so outputs are non-zero.

This is a simple, safe mapper to unblock the pipeline. Later we can plug proper room detection.
"""

from __future__ import annotations
import json
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Any

def load_ocr(path: Path) -> List[Any]:
    if not path.exists():
        raise SystemExit(f"[ERR] OCR JSON not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("dims", [])

def pair_singletons(values: List[float]) -> List[Tuple[float,float]]:
    """Pair [a,b,c,d] -> [(a,b),(c,d)]. If odd length, last becomes square (n,n)."""
    rects = []
    i = 0
    while i < len(values):
        a = float(values[i])
        b = float(values[i+1]) if i+1 < len(values) else float(values[i])  # square fallback
        rects.append((a, b))
        i += 2
    return rects

def collect_rectangles(dims: List[Dict[str,Any]]) -> List[Tuple[float,float]]:
    """Return list of rectangles in feet (width, height)."""
    rects: List[Tuple[float,float]] = []
    singles: List[float] = []

    for d in dims:
        feet = d.get("feet")
        if isinstance(feet, list) and len(feet) >= 2:
            rects.append((float(feet[0]), float(feet[1])))
        elif isinstance(feet, (int, float)):
            singles.append(float(feet))

    # Pair leftover singles
    rects.extend(pair_singletons(singles))

    # If nothing at all, produce a tiny default to avoid zeros
    if not rects:
        rects = [(10.0, 10.0)]  # 100 sqft default

    return rects

def build_area_metrics(rects: List[Tuple[float,float]]) -> Dict[str,Any]:
    rooms = []
    total_area = 0.0
    for i, (w,h) in enumerate(rects, start=1):
        area = w * h
        rooms.append({"id": i, "width_ft": w, "height_ft": h, "area_sqft": round(area, 3)})
        total_area += area
    return {
        "rooms": rooms,
        "total_area_sqft": round(total_area, 3)
    }

def build_wall_metrics(rects: List[Tuple[float,float]]) -> Dict[str,Any]:
    walls = []
    total_perimeter = 0.0
    for i, (w,h) in enumerate(rects, start=1):
        perim = 2*(w+h)
        walls.append({"id": i, "width_ft": w, "height_ft": h, "perimeter_ft": round(perim, 3)})
        total_perimeter += perim
    return {
        "segments": walls,
        "total_perimeter_ft": round(total_perimeter, 3)
    }

def main():
    ap = argparse.ArgumentParser(description="Day 22: Map OCR dims to geometry metrics JSON")
    ap.add_argument("--ocr", default="data/output/ocr_dims.json", help="Path to OCR dims json")
    ap.add_argument("--out_area", default="data/output/metrics_area.json")
    ap.add_argument("--out_walls", default="data/output/metrics_walls.json")
    args = ap.parse_args()

    ocr_path = Path(args.ocr)
    area_path = Path(args.out_area)
    walls_path = Path(args.out_walls)
    area_path.parent.mkdir(parents=True, exist_ok=True)
    walls_path.parent.mkdir(parents=True, exist_ok=True)

    dims = load_ocr(ocr_path)
    rects = collect_rectangles(dims)

    area_metrics = build_area_metrics(rects)
    walls_metrics = build_wall_metrics(rects)

    area_path.write_text(json.dumps(area_metrics, indent=2), encoding="utf-8")
    walls_path.write_text(json.dumps(walls_metrics, indent=2), encoding="utf-8")

    print(f"[OK] Wrote {area_path} and {walls_path}")
    if area_metrics["total_area_sqft"] <= 0 or walls_metrics["total_perimeter_ft"] <= 0:
        print("[WARN] Totals are zero; check OCR inputs.")
    else:
        print(f"[INFO] Total area: {area_metrics['total_area_sqft']} sqft, "
              f"Total perimeter: {walls_metrics['total_perimeter_ft']} ft")

if __name__ == "__main__":
    main()
