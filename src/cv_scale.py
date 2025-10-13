# src/cv_scale.py
# Convert pixel lengths (from lines_plan1.json) to real units using a manual scale.
from pathlib import Path
import argparse, json

LINES_JSON = Path("data/samples/lines_plan1.json")
OUT_JSON   = Path("data/samples/lines_scaled.json")
OUT_CSV    = Path("data/samples/lines_scaled.csv")

UNITS = {"mm":1.0, "cm":10.0, "m":1000.0, "in":25.4, "ft":304.8}

def main():
    ap = argparse.ArgumentParser(description="Apply manual scale: 1 px = X units")
    ap.add_argument("--unit", required=True, choices=list(UNITS.keys()),
                    help="Target unit for output (mm, cm, m, in, ft)")
    ap.add_argument("--perpx", required=True, type=float,
                    help="How many target units does 1 pixel represent? Example: if 10 ft equals 500 px, perpx = 10/500 = 0.02 (ft/px)")
    args = ap.parse_args()

    if not LINES_JSON.exists():
        raise FileNotFoundError(f"Missing {LINES_JSON}. Run cv_lines.py first.")

    data = json.loads(LINES_JSON.read_text(encoding="utf-8"))
    lines = data.get("lines", [])
    unit = args.unit
    perpx = args.perpx  # e.g., 0.02 ft/px

    scaled = []
    for i, ln in enumerate(lines):
        length_px = float(ln["length_px"])
        length_unit = length_px * perpx
        scaled.append({
            "index": i,
            "p1": ln["p1"],
            "p2": ln["p2"],
            "length_px": length_px,
            "length_" + unit: length_unit
        })

    # write JSON
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    json.dump({
        "unit": unit,
        "per_pixel": perpx,
        "count": len(scaled),
        "lines": scaled
    }, open(OUT_JSON, "w", encoding="utf-8"), indent=2)

    # write CSV
    with open(OUT_CSV, "w", encoding="utf-8") as f:
        f.write(f"index,p1,p2,length_px,length_{unit}\n")
        for row in scaled:
            f.write(f'{row["index"]},"{row["p1"]}","{row["p2"]}",{row["length_px"]:.2f},{row["length_"+unit]:.4f}\n')

    print(f"Applied scale: 1 px = {perpx} {unit}")
    print(f"Scaled {len(scaled)} line(s)")
    print(f"Saved: {OUT_JSON}")
    print(f"Saved: {OUT_CSV}")
    print("Tip: perpx = (real_length_in_unit) / (pixel_length)")
    print("      Example: a 10 ft wall measures ~500 px → perpx = 10/500 = 0.02 ft/px")

if __name__ == "__main__":
    main()
