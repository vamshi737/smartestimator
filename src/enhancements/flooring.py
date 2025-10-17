# src/enhancements/flooring.py
"""
Day 3 – Flooring Logic

Reads total floor area from:
  1) data/output/area_summary.json   (if available)
  2) data/samples/metrics_area.json  (fallback)
  3) defaults to 0.0 if missing

Creates data/inputs/flooring_input.json template if not present.

Computes flooring cost = area_m2 × (1 + wastage%) × rate_per_m2
and saves results to data/output/flooring.json.
"""

import os, json

IN_DIR   = os.path.join("data", "inputs")
OUT_DIR  = os.path.join("data", "output")
os.makedirs(IN_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

IN_FILE_AREA_1 = os.path.join(OUT_DIR, "area_summary.json")
IN_FILE_AREA_2 = os.path.join("data", "samples", "metrics_area.json")
IN_FILE_INPUT  = os.path.join(IN_DIR, "flooring_input.json")
OUT_FILE       = os.path.join(OUT_DIR, "flooring.json")
PRICES_FILE    = os.path.join("data", "prices.json")

TEMPLATE = {
    "material": "tiles",
    "wastage_pct": 7.5,
    "rate_per_m2": 0.0,
    "notes": "Edit wastage% and rate. If rate=0, it will use 'flooring' rate from prices.json if found."
}

def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_area():
    """Try multiple sources for total area (m²)."""
    for path in [IN_FILE_AREA_1, IN_FILE_AREA_2]:
        data = read_json(path)
        if isinstance(data, dict):
            # Try common keys
            for k in ["gross_area_m2", "carpet_area_m2", "builtup_area_m2", "area_m2", "total_area_m2"]:
                v = data.get(k)
                if isinstance(v, (int, float)) and v > 0:
                    return float(v)
    return 0.0

def get_price(prices):
    try:
        return float(prices.get("flooring", 0.0))
    except Exception:
        return 0.0

def main():
    print("[Enh] flooring: computing...")

    # Ensure manual input exists
    if not os.path.exists(IN_FILE_INPUT):
        write_json(IN_FILE_INPUT, TEMPLATE)
        print(f"[Enh] flooring: created template at {IN_FILE_INPUT}")

    manual = read_json(IN_FILE_INPUT) or TEMPLATE
    prices = read_json(PRICES_FILE) or {}

    material    = manual.get("material", "tiles")
    wastage_pct = float(manual.get("wastage_pct", 0))
    rate        = float(manual.get("rate_per_m2", 0.0))
    area_m2     = get_area()

    if rate <= 0:
        rate = get_price(prices)

    total_area_m2 = area_m2 * (1 + wastage_pct / 100.0)
    total_amount  = round(total_area_m2 * rate, 2)

    payload = {
        "material": material,
        "area_m2": round(area_m2, 2),
        "wastage_pct": wastage_pct,
        "rate_per_m2": round(rate, 2),
        "total_area_m2_with_wastage": round(total_area_m2, 2),
        "amount": total_amount,
        "source": {
            "area_file": IN_FILE_AREA_1 if os.path.exists(IN_FILE_AREA_1) else IN_FILE_AREA_2,
            "input_file": IN_FILE_INPUT
        }
    }

    write_json(OUT_FILE, payload)
    print(f"[Enh] flooring: wrote {OUT_FILE}")

if __name__ == "__main__":
    main()
