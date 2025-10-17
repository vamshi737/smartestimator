# src/enhancements/area_summary.py
"""
Day 4 – Area Summary Logic

Collects total areas from:
  - data/samples/metrics_walls.json (wall area)
  - data/output/doors_windows.json  (openings)
  - data/output/flooring.json       (floor)
and produces a combined summary at data/output/area_summary.json.
"""

import os, json

DATA = {
    "walls_file": "data/samples/metrics_walls.json",
    "doors_file": "data/output/doors_windows.json",
    "floor_file": "data/output/flooring.json",
    "out_file":  "data/output/area_summary.json"
}

def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def extract_wall_area(data):
    if not isinstance(data, dict):
        return 0.0
    # Accept either 'metrics' or simple area values
    for k in ["gross_area_m2", "wall_area_m2", "surface_area_m2", "area_m2"]:
        v = data.get(k)
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
    # sometimes nested under 'metrics'
    if "metrics" in data and isinstance(data["metrics"], dict):
        for k, v in data["metrics"].items():
            if "area" in k and isinstance(v, (int, float)):
                return float(v)
    return 0.0

def extract_openings_area(data):
    """Sum door/window areas (each × count)."""
    total = 0.0
    for cat in ["doors", "windows"]:
        for item in data.get(cat, []):
            a = item.get("area_m2_each", 0) * item.get("count", 0)
            total += float(a)
    return round(total, 2)

def extract_floor_area(data):
    if not isinstance(data, dict):
        return 0.0
    for k in ["total_area_m2_with_wastage", "area_m2", "total_area_m2"]:
        v = data.get(k)
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
    return 0.0

def main():
    print("[Enh] area_summary: computing...")

    walls = read_json(DATA["walls_file"]) or {}
    openings = read_json(DATA["doors_file"]) or {}
    floor = read_json(DATA["floor_file"]) or {}

    wall_area = extract_wall_area(walls)
    openings_area = extract_openings_area(openings)
    floor_area = extract_floor_area(floor)

    net_wall_area = max(0.0, wall_area - openings_area)

    result = {
        "wall_area_m2": round(wall_area, 2),
        "openings_area_m2": round(openings_area, 2),
        "net_wall_area_m2": round(net_wall_area, 2),
        "floor_area_m2": round(floor_area, 2),
        "gross_area_m2": round(wall_area + floor_area, 2),
        "source_files": {
            "walls": DATA["walls_file"],
            "doors_windows": DATA["doors_file"],
            "flooring": DATA["floor_file"]
        }
    }

    write_json(DATA["out_file"], result)
    print(f"[Enh] area_summary: wrote {DATA['out_file']}")

if __name__ == "__main__":
    main()
