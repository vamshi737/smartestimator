# src/enhancements/doors_windows.py
"""
Day 2 – Doors & Windows Logic

Reads door/window dimensions & counts from:
1) data/inputs/doors_windows_input.json  (authoritative manual input)
   - if missing, a template is created for you to edit.
2) Optionally merges counts/sizes from data/samples/metrics_walls.json
   - Only if a compatible structure exists and the manual input has count=0.

Rates (per m²) priority:
- rate_per_m2 set in data/inputs/doors_windows_input.json (if > 0)
- else lookup in data/prices.json under:
    { "doors": { "D1": 120.0 }, "windows": { "W1": 80.0 } }
"""

import os
import json

IN_DIR   = os.path.join("data", "inputs")
OUT_DIR  = os.path.join("data", "output")
os.makedirs(IN_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

IN_FILE      = os.path.join(IN_DIR, "doors_windows_input.json")
OUT_FILE     = os.path.join(OUT_DIR, "doors_windows.json")
PRICES_FILE  = os.path.join("data", "prices.json")
METRICS_FILE = os.path.join("data", "samples", "metrics_walls.json")  # optional

TEMPLATE = {
    "doors": [
        {"type": "D1", "width_mm": 900,  "height_mm": 2100, "count": 0, "rate_per_m2": 0.0},
        {"type": "D2", "width_mm": 750,  "height_mm": 2100, "count": 0, "rate_per_m2": 0.0}
    ],
    "windows": [
        {"type": "W1", "width_mm": 1200, "height_mm": 1200, "count": 0, "rate_per_m2": 0.0},
        {"type": "W2", "width_mm": 900,  "height_mm":  900, "count": 0, "rate_per_m2": 0.0}
    ],
    "notes": "Edit counts/sizes/rates. If rates are 0, prices.json may override."
}

def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

def mm_to_m(v):
    return float(v) / 1000.0

def mm2_to_m2(w_mm, h_mm):
    return mm_to_m(w_mm) * mm_to_m(h_mm)

def get_price(prices, category, typ, default=0.0):
    try:
        return float(prices.get(category, {}).get(str(typ), default))
    except Exception:
        return default

def merge_from_metrics(manual_items, metrics, category_key):
    """
    If metrics_walls.json provides something like:
      {"doors": [{"type":"D1","width_mm":900,"height_mm":2100,"count":3}, ...],
       "windows":[...]}
    we fill missing (count==0) entries in the manual list.
    """
    if not isinstance(metrics, dict):
        return manual_items

    src = metrics.get(category_key)
    if not isinstance(src, list) or not src:
        return manual_items

    # Build a lookup by type from metrics
    metrics_by_type = {}
    for it in src:
        t = str(it.get("type", "")).strip()
        if not t:
            continue
        metrics_by_type[t] = it

    merged = []
    for item in manual_items:
        t = str(item.get("type", "")).strip()
        merged_item = dict(item)
        if t and merged_item.get("count", 0) == 0 and t in metrics_by_type:
            m = metrics_by_type[t]
            # copy count and dimensions only if present
            if "count" in m:
                merged_item["count"] = int(m.get("count", 0))
            if "width_mm" in m:
                merged_item["width_mm"] = float(m.get("width_mm", merged_item.get("width_mm", 0)))
            if "height_mm" in m:
                merged_item["height_mm"] = float(m.get("height_mm", merged_item.get("height_mm", 0)))
        merged.append(merged_item)
    return merged

def compute(items, prices, category):
    total = 0.0
    out_items = []
    for it in items:
        t = str(it.get("type", "UNK"))
        w = float(it.get("width_mm", 0))
        h = float(it.get("height_mm", 0))
        c = int(it.get("count", 0))

        area_each = mm2_to_m2(w, h)
        in_rate   = float(it.get("rate_per_m2", 0.0))
        rate      = in_rate if in_rate > 0 else get_price(prices, category, t, 0.0)
        amount    = round(area_each * c * rate, 2)

        total += amount
        out_items.append({
            "type": t,
            "width_mm": w,
            "height_mm": h,
            "count": c,
            "area_m2_each": round(area_each, 3),
            "rate_per_m2": round(rate, 2),
            "amount": amount
        })
    return out_items, round(total, 2)

def main():
    print("[Enh] doors_windows: computing...")

    # Ensure manual input exists
    if not os.path.exists(IN_FILE):
        write_json(IN_FILE, TEMPLATE)
        print(f"[Enh] doors_windows: created template at {IN_FILE} — please edit counts/rates if needed.")

    manual = read_json(IN_FILE) or TEMPLATE
    prices = read_json(PRICES_FILE) or {}

    # Optionally merge counts/sizes from metrics_walls.json (non-blocking)
    metrics = read_json(METRICS_FILE) or {}
    manual["doors"]   = merge_from_metrics(manual.get("doors", []),   metrics, "doors")
    manual["windows"] = merge_from_metrics(manual.get("windows", []), metrics, "windows")

    # Compute amounts
    doors_out, total_doors     = compute(manual.get("doors", []),   prices, "doors")
    windows_out, total_windows = compute(manual.get("windows", []), prices, "windows")
    grand_total = round(total_doors + total_windows, 2)

    result = {
        "doors": doors_out,
        "windows": windows_out,
        "totals": {
            "doors_amount": total_doors,
            "windows_amount": total_windows,
            "total_amount": grand_total
        },
        "source": {
            "manual_input": IN_FILE,
            "metrics_used": os.path.exists(METRICS_FILE)
        }
    }

    write_json(OUT_FILE, result)
    print(f"[Enh] doors_windows: wrote {OUT_FILE}")

if __name__ == "__main__":
    main()
