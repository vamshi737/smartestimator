# src/vision/geometry_from_dims.py
"""
Week 5 · Day 24.1 — Geometry mapping from OCR → metrics JSON
OCR-first + Manual Scale Override, with image-size fallback.

What this version does:
1) Estimates feet-per-pixel scale from OCR dimension annotations (median).
2) If manual scale provided via data/output/manual_scale.json (known width OR height in feet),
   it overrides ft_per_px using:
   - union bbox of detected shapes (preferred), OR
   - the preprocessed image size (when bbox not available).
3) Converts rooms (polygons in px) and walls (polylines in px) to feet.
4) Guarantees a non-zero room list. If manual scale was used but no shapes were found,
   it synthesizes a real GrossArea rectangle (from kw×kh if possible, else image rect × scale).
   Otherwise it falls back to a tiny 10×10 SyntheticArea.
5) Writes:
   - metrics_area.json  (source, scale_ft_per_px, scale_source, rooms, totals)
   - metrics_walls.json (walls, totals)

CLI:
  --ocr       Path to OCR JSON (default: data/output/ocr_dims.json)
  --out_area  Path to write metrics_area.json
  --out_walls Path to write metrics_walls.json
  --preproc   Path to preprocessed image (for image-size fallback)
"""

from __future__ import annotations
import json, math, re, argparse
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Tuple, Optional
from PIL import Image  # for image-size fallback

# ----------------------------- Parsing helpers -----------------------------
FT_PER_MM = 0.0032808399  # 1 mm in feet

DIM_FT_RX = re.compile(
    r"""(?ix)
    ^\s*
    (?:
        (?P<ft>\d+(?:\.\d+)?)\s*(?:'|ft|feet)?
        (?:\s*(?P<in>\d+(?:\.\d+)?)\s*(?:\"|in|inch(?:es)?)?)?
      |
        (?P<in_only>\d+(?:\.\d+)?)\s*(?:\"|in|inch(?:es)?)\b
      |
        (?P<mm>\d+(?:\.\d+)?)\s*mm\b
    )
    \s*$
    """
)

def _to_feet(text: str) -> Optional[float]:
    t = str(text).strip().replace("’", "'").replace("”", '"').replace("″", '"').replace("“", '"')
    m = DIM_FT_RX.match(t)
    if not m:
        return None
    if m.group("mm"):
        return float(m.group("mm")) * FT_PER_MM
    if m.group("in_only"):
        return float(m.group("in_only")) / 12.0
    ft = float(m.group("ft") or 0)
    inches = float(m.group("in") or 0)
    return ft + inches / 12.0

def _dist(p1: List[float], p2: List[float]) -> float:
    return math.hypot(float(p1[0]) - float(p2[0]), float(p1[1]) - float(p2[1]))

def _shoelace_area_and_perim(poly: List[List[float]]) -> Tuple[float, float]:
    n = len(poly)
    if n < 3:
        return 0.0, 0.0
    area = 0.0
    perim = 0.0
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        area += x1 * y2 - x2 * y1
        perim += _dist([x1, y1], [x2, y2])
    return abs(area) / 2.0, perim

def _scale_poly(poly_px: List[List[float]], ft_per_px: float) -> List[List[float]]:
    return [[float(x) * ft_per_px, float(y) * ft_per_px] for x, y in poly_px]

# ------------------------------- Core logic --------------------------------
def _estimate_scale_from_dims(dims: List[Dict[str, Any]]) -> Optional[float]:
    candidates: List[float] = []
    for d in dims:
        p1, p2 = d.get("p1"), d.get("p2")
        if not (isinstance(p1, (list, tuple)) and isinstance(p2, (list, tuple))):
            continue
        pix = _dist(p1, p2)
        if pix <= 3:
            continue
        feet_val: Optional[float] = None
        if "feet" in d and isinstance(d["feet"], (int, float)):
            feet_val = float(d["feet"])
        elif "text" in d:
            feet_val = _to_feet(d["text"])
        if feet_val and feet_val > 0:
            candidates.append(feet_val / pix)
    if not candidates:
        return None
    return median(candidates)

def _bbox_from_walls_px(walls: List[Dict[str, Any]]) -> Optional[List[List[float]]]:
    xs: List[float] = []
    ys: List[float] = []
    for w in walls:
        for x, y in (w.get("poly_px") or []):
            xs.append(float(x)); ys.append(float(y))
    if not xs or not ys:
        return None
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    return [[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy]]

def _bbox_from_rooms_px(rooms: List[Dict[str, Any]]) -> Optional[List[List[float]]]:
    xs: List[float] = []
    ys: List[float] = []
    for r in rooms:
        for x, y in (r.get("poly_px") or []):
            xs.append(float(x)); ys.append(float(y))
    if not xs or not ys:
        return None
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    return [[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy]]

def _bbox_union_px(walls: List[Dict[str, Any]], rooms: List[Dict[str, Any]]) -> Optional[List[List[float]]]:
    b_w = _bbox_from_walls_px(walls)
    b_r = _bbox_from_rooms_px(rooms)
    if not b_w and not b_r:
        return None
    if b_w and not b_r:
        return b_w
    if b_r and not b_w:
        return b_r
    xs = [b_w[0][0], b_w[1][0], b_w[2][0], b_w[3][0], b_r[0][0], b_r[1][0], b_r[2][0], b_r[3][0]]
    ys = [b_w[0][1], b_w[1][1], b_w[2][1], b_w[3][1], b_r[0][1], b_r[1][1], b_r[2][1], b_r[3][1]]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    return [[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy]]

def _synthesize_small_box_ft() -> List[List[float]]:
    return [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]

def _read_manual_scale_json(shared_dir: Path) -> Dict[str, Optional[float]]:
    p = shared_dir / "manual_scale.json"
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"known_width_ft": None, "known_height_ft": None}

def build_metrics(ocr_json_path: Path, out_area_path: Path, out_walls_path: Path,
                  preproc_path: str = "") -> Dict[str, Any]:
    data = json.loads(ocr_json_path.read_text(encoding="utf-8"))
    dims: List[Dict[str, Any]] = data.get("dims", []) or []
    rooms_px: List[Dict[str, Any]] = data.get("rooms", []) or []
    walls_px: List[Dict[str, Any]] = data.get("walls", []) or []

    scale_source = "default"
    manual_used = False  # <-- track whether a manual override actually applied

    # 1) OCR-based scale
    ft_per_px: Optional[float] = _estimate_scale_from_dims(dims)
    if ft_per_px is not None:
        scale_source = "ocr"

    # 1.5) Manual scale override
    shared_dir = Path("data/output")
    ms = _read_manual_scale_json(shared_dir)
    kw = ms.get("known_width_ft") or None
    kh = ms.get("known_height_ft") or None

    if kw is not None or kh is not None:
        bbox = _bbox_union_px(walls_px, rooms_px)
        if bbox:
            (minx, miny), (_, _), (maxx, maxy), _ = bbox
            px_w = float(maxx - minx)
            px_h = float(maxy - miny)
            if kw is not None and px_w > 0:
                ft_per_px = float(kw) / px_w
                scale_source = "manual"; manual_used = True
            elif kh is not None and px_h > 0:
                ft_per_px = float(kh) / px_h
                scale_source = "manual"; manual_used = True
        elif preproc_path:
            # Fallback to full image size if no bbox yet
            try:
                with Image.open(preproc_path) as im:
                    img_w, img_h = im.size
                if kw is not None and img_w > 0:
                    ft_per_px = float(kw) / float(img_w)
                    scale_source = "manual"; manual_used = True
                elif kh is not None and img_h > 0:
                    ft_per_px = float(kh) / float(img_h)
                    scale_source = "manual"; manual_used = True
            except Exception:
                pass

    # 2) Weak heuristic → default
    if ft_per_px is None:
        guesses: List[float] = []
        for d in dims:
            txt = str(d.get("text", "")).replace("’", "'")
            if any(s in txt for s in ["2'-8", "2' - 8", "2’-8"]):
                p1, p2 = d.get("p1"), d.get("p2")
                if isinstance(p1, (list, tuple)) and isinstance(p2, (list, tuple)):
                    pix = _dist(p1, p2)
                    if pix > 3:
                        guesses.append(2.6667 / pix)
        if guesses:
            ft_per_px = median(guesses)
            scale_source = "ocr"

    if ft_per_px is None:
        ft_per_px = 0.02
        scale_source = "default"

    # 3) Rooms → feet (from OCR)
    rooms_ft: List[Dict[str, Any]] = []
    for r in rooms_px:
        name = r.get("name") or "Room"
        poly_px = r.get("poly_px") or []
        if len(poly_px) < 3:
            continue
        poly_ft = _scale_poly(poly_px, ft_per_px)
        area, perim = _shoelace_area_and_perim(poly_ft)
        if area > 0.01:
            rooms_ft.append({
                "name": name,
                "polygon_ft": poly_ft,
                "area_ft2": round(area, 3),
                "perimeter_ft": round(perim, 3)
            })

    # 4) Guarantee some area
    if not rooms_ft:
        bbox_px = _bbox_union_px(walls_px, rooms_px)

        # If manual scale was used but no bbox/rooms exist, synthesize GrossArea from image
        if manual_used and not bbox_px and preproc_path:
            try:
                with Image.open(preproc_path) as im:
                    img_w, img_h = im.size

                # If only one of width/height was provided, infer the other using aspect ratio
                if kw is not None and kh is None and img_w > 0:
                    kh = kw * (float(img_h) / float(img_w))
                if kh is not None and kw is None and img_h > 0:
                    kw = kh * (float(img_w) / float(img_h))

                if kw is not None and kh is not None:
                    # Build rectangle directly in feet from kw × kh
                    poly_ft = [[0.0, 0.0], [kw, 0.0], [kw, kh], [0.0, kh]]
                else:
                    # Fall back to image rectangle scaled by ft_per_px
                    poly_px = [[0.0, 0.0], [img_w, 0.0], [img_w, img_h], [0.0, img_h]]
                    poly_ft = _scale_poly(poly_px, ft_per_px)

                area, perim = _shoelace_area_and_perim(poly_ft)
                rooms_ft = [{
                    "name": "GrossArea",
                    "polygon_ft": poly_ft,
                    "area_ft2": round(area, 3),
                    "perimeter_ft": round(perim, 3)
                }]
            except Exception:
                pass

    # Still nothing? use bbox if present, else tiny synthetic
    if not rooms_ft:
        if bbox_px:
            poly_ft = _scale_poly(bbox_px, ft_per_px)
            area, perim = _shoelace_area_and_perim(poly_ft)
            if area <= 0.01:
                poly_ft = _synthesize_small_box_ft()
                area, perim = _shoelace_area_and_perim(poly_ft)
            rooms_ft = [{
                "name": "GrossArea",
                "polygon_ft": poly_ft,
                "area_ft2": round(area, 3),
                "perimeter_ft": round(perim, 3)
            }]
        else:
            poly_ft = _synthesize_small_box_ft()
            area, perim = _shoelace_area_and_perim(poly_ft)
            rooms_ft = [{
                "name": "SyntheticArea",
                "polygon_ft": poly_ft,
                "area_ft2": round(area, 3),
                "perimeter_ft": round(perim, 3)
            }]

    # 5) Walls → feet lengths
    walls_ft: List[Dict[str, Any]] = []
    for w in walls_px:
        poly_px = w.get("poly_px") or []
        if len(poly_px) < 2:
            continue
        poly_ft = _scale_poly(poly_px, ft_per_px)
        length = 0.0
        for i in range(1, len(poly_ft)):
            length += _dist(poly_ft[i - 1], poly_ft[i])
        walls_ft.append({"polyline_ft": poly_ft, "length_ft": round(length, 3)})

    # 6) Totals
    total_area = round(sum(r["area_ft2"] for r in rooms_ft), 3)
    total_perim = round(sum(r["perimeter_ft"] for r in rooms_ft), 3)
    total_wall_len = round(sum(w["length_ft"] for w in walls_ft), 3)

    # 7) Write files
    out_area_path.parent.mkdir(parents=True, exist_ok=True)
    out_walls_path.parent.mkdir(parents=True, exist_ok=True)

    area_payload = {
        "source": "ocr",
        "scale_ft_per_px": ft_per_px,
        "scale_source": scale_source,  # "manual" | "ocr" | "default"
        "rooms": rooms_ft,
        "totals": {
            "total_area_ft2": total_area,
            "total_perimeter_ft": total_perim,
            "total_wall_length_ft": total_wall_len
        }
    }
    walls_payload = {
        "source": "ocr",
        "walls": walls_ft,
        "totals": {"total_wall_length_ft": total_wall_len}
    }

    out_area_path.write_text(json.dumps(area_payload, indent=2), encoding="utf-8")
    out_walls_path.write_text(json.dumps(walls_payload, indent=2), encoding="utf-8")

    return {
        "ocr_geometry_used": True,
        "scale_ft_per_px": ft_per_px,
        "scale_source": scale_source,
        "totals": {
            "total_area_ft2": total_area,
            "total_perimeter_ft": total_perim,
            "total_wall_length_ft": total_wall_len
        },
        "area_path": str(out_area_path),
        "walls_path": str(out_walls_path)
    }

# ---------------------------------- CLI -----------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Day 24.1: OCR → geometry metrics (manual scale + image fallback)"
    )
    ap.add_argument("--ocr", default="data/output/ocr_dims.json", help="Path to OCR JSON")
    ap.add_argument("--out_area", default="data/output/metrics_area.json", help="Path to write metrics_area.json")
    ap.add_argument("--out_walls", default="data/output/metrics_walls.json", help="Path to write metrics_walls.json")
    ap.add_argument("--preproc", default="", help="Path to preprocessed image (for fallback size)")
    args = ap.parse_args()

    ocr_path = Path(args.ocr)
    area_path = Path(args.out_area)
    walls_path = Path(args.out_walls)

    if not ocr_path.exists():
        raise SystemExit(f"[ERR] OCR JSON not found: {ocr_path}")

    result = build_metrics(ocr_path, area_path, walls_path, preproc_path=args.preproc)

    t = result["totals"]
    print(f"[OK] Wrote {area_path} and {walls_path}")
    print(
        f"[INFO] Scale: {result['scale_ft_per_px']:.6f} ft/px "
        f"(source={result.get('scale_source')}) | "
        f"Area: {t['total_area_ft2']} ft² | Perimeter: {t['total_perimeter_ft']} ft | "
        f"Wall length: {t['total_wall_length_ft']} ft"
    )

if __name__ == "__main__":
    main()
