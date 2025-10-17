# src/enhancements/doors_windows.py
import os
import json

OUTPUT_DIR = os.path.join("data", "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUT_FILE = os.path.join(OUTPUT_DIR, "doors_windows.json")

def main():
    # Day 1 placeholder: no logic yet—just a safe file write.
    print("[Enh] doors_windows: placeholder running...")
    payload = {
        "doors": [
            {"type": "D1", "width_mm": 900, "height_mm": 2100, "count": 0, "amount": 0.0}
        ],
        "windows": [
            {"type": "W1", "width_mm": 1200, "height_mm": 1200, "count": 0, "amount": 0.0}
        ],
        "total_amount": 0.0
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"[Enh] doors_windows: wrote {OUT_FILE}")

if __name__ == "__main__":
    main()
