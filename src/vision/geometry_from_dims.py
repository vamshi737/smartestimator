# src/vision/geometry_from_dims.py
"""
Week 5 · Day 22 — Geometry mapping from OCR dims → metrics JSON.

What this version does:
1) Collects all feet values from OCR (both single numbers and [w,h] pairs).
2) If at least two reasonable feet numbers exist, it assumes the two LARGEST
   are the overall site/plan rectangle (e.g., 65' and 35').
3) Otherwise, it falls back to pairing singles (old behavior) or a 10x10 demo.
"""

from __future__ import annotations
import json
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Any

MIN_REASONABLE_FT = 8.0     # ignore tiny noise like 1', 2', etc.
MAX_REASONABLE_FT = 300.0   # ignore absurd OCR explosions

def load_ocr(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"[ERR] OCR JSON not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("dims", [])

def clamp_ft(v: float) -> float | None:
    try:
        v = float(v)
        if MIN_REASONABLE_FT <= v <= MAX_REASONABLE_FT:
            return v
    except Exception:
        pass
    return None

def pair_singletons(values: List[float]) -> List[Tuple[float, float]]:
    """Pair [a,b,c,d] -> [(a,b),(c,d)]. If odd, last becomes square (n,n)."""
    rects: List[Tuple[float, float]] = []
    i = 0
    while i < len(values):
        a = float(values[i])
        b = float(values[i+1]) if i+1 < len(values) else float(values[i])  # square fallback
        rects.append((a, b))
        i += 2
    return rects

def collect_numbers_and_pairs(dims: List[Dict[str, Any]]) -> tuple[list[float], list[tuple[float,float]]]:
    singles: List[float] = []
    pairs: List[Tuple[float, float]] = []

    for d in dims:
        feet = d.get("feet")
        # explicit pair like [w,h]
        if isinstance(feet, list) and len(feet) >= 2:
            w = clamp_ft(feet[0])
            h = clamp_ft(feet[1])
            if w is not None and h is not None:
                pairs.append((w, h))
        # single number
        elif isinstance(feet, (int, float)):
            v = clamp_ft(feet)
            if v is not None:
                singles.append(v)
    return singles, pairs

def pick_overall_from_largest(singles: List[float], pairs: List[Tuple[float,float]]) -> list[tuple[float,float]]:
    """
    Heuristic:
    - If we have 2+ singles, take the two largest as the overall rectangle.
    - If that rectangle area < 300 sqft (likely noise) then ignore this heuristic.
    - Otherwise return [(W,H)]. Keep any explicit [w,h] pairs that are also large.
    """
    rects: List[Tuple[float, float]] = []

    if len(singles) >= 2:
        singles_sorted = sorted(singles, reverse=True)
        W, H = singles_sorted[0], singles_sorted[1]
        area = W * H
        if area >= 300.0:  # sanity check to avoid tiny/garbage rectangles
            rects.append((W, H))

    # If any explicit pairs look large (e.g., 20x15 rooms), you could add them too.
    # For now we keep only the overall rectangle to avoid double counting.
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
    ap = argparse.ArgumentParser(description="Day 22: Map OCR dims to geometry metrics JSON (largest-two heuristic)")
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
    singles, pairs = collect_numbers_and_pairs(dims)

    # 1) Try the largest-two heuristic
    rects = pick_overall_from_largest(singles, pairs)

    # 2) If nothing sensible, fall back to old behavior
    if not rects:
        # use explicit pairs that passed sanity checks, then pair leftover singles
        rects = pairs[:]
        rects.extend(pair_singletons(singles))
        if not rects:
            rects = [(10.0, 10.0)]  # demo fallback

    area_metrics = build_area_metrics(rects)
    walls_metrics = build_wall_metrics(rects)

    area_path.write_text(json.dumps(area_metrics, indent=2), encoding="utf-8")
    walls_path.write_text(json.dumps(walls_metrics, indent=2), encoding="utf-8")

    print(f"[OK] Wrote {area_path} and {walls_path}")
    print(f"[INFO] Total area: {area_metrics['total_area_sqft']} sqft, "
          f"Total perimeter: {walls_metrics['total_perimeter_ft']} ft")

if __name__ == "__main__":
    main()
