# src/vision/ocr_dims.py
"""
Week 5 · Day 21 — OCR + Feet/Inch Dimension Parsing
Reads preprocessed image and extracts dimension strings, then normalizes to feet.
"""

import re
import json
import argparse
from pathlib import Path
import cv2
import pytesseract

# Parse regex:
# supports: 12'-6", 10' 4", 12x16', 12'6", 8’ (curly)
DIM_PATTERN = re.compile(
    r"(\d+)\s*['’]\s*(\d+)?\s*(?:\"|”)?|(\d+)\s*[xX]\s*(\d+)\s*['’]?"
)

def parse_dimension(text: str):
    text = text.strip()
    
    # Case: 12'-6" or 10' 4"
    m = re.match(r"(\d+)\s*['’]\s*(\d+)", text)
    if m:
        ft = float(m.group(1)) + float(m.group(2)) / 12
        return ft
    
    # Case: 10'
    m = re.match(r"(\d+)\s*['’]$", text)
    if m:
        return float(m.group(1))
    
    # Case: 12x16'
    m = re.match(r"(\d+)\s*[xX]\s*(\d+)", text)
    if m:
        return [ float(m.group(1)), float(m.group(2)) ]
    
    return None


def extract_text(image_path: Path) -> str:
    img = cv2.imread(str(image_path))
    if img is None:
        raise SystemExit(f"[ERR] Cannot read: {image_path}")
    
    config = "--psm 6 -c tessedit_char_whitelist=0123456789xX'\"’"
    raw = pytesseract.image_to_string(img, config=config)
    return raw


def process(input_path: Path, out_json: Path):
    print("[run] OCR on:", input_path)
    raw = extract_text(input_path)
    
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    
    dims = []
    for line in lines:
        val = parse_dimension(line)
        if val:
            dims.append({"text": line, "feet": val})
    
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps({"dims": dims}, indent=2))
    
    print(f"[OK] OCR dims saved: {out_json}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default="data/output/ocr_dims.json")
    args = ap.parse_args()
    process(Path(args.input), Path(args.out))


if __name__ == "__main__":
    main()
