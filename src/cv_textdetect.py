# src/cv_textdetect.py
from pathlib import Path
import cv2
import numpy as np
import pytesseract
import shutil
import re
import json

# --- pick whichever case matches your file name ---
CANDIDATES = [Path("data/samples/plan1.png"), Path("data/samples/PLAN1.png")]
for p in CANDIDATES:
    if p.exists():
        SAMPLE = p
        break
else:
    raise FileNotFoundError("Put plan1.png (or PLAN1.png) in data/samples/")

OUT_IMG  = Path("data/samples/labels_plan1.png")
OUT_JSON = Path("data/samples/labels_plan1.json")

# --- make sure tesseract is reachable on Windows ---
if shutil.which("tesseract") is None:
    # common default install path
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def load_color(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {path}")
    return img

def preprocess_for_ocr(img_bgr: np.ndarray) -> np.ndarray:
    """Return a high-contrast black-text-on-white image for OCR."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3,3), 0)
    # Otsu binarization
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # If mostly dark (black background), invert so text becomes black on white
    if np.mean(th) < 127:
        th = cv2.bitwise_not(th)

    # Slight dilation to connect thin strokes
    th = cv2.dilate(th, cv2.getStructuringElement(cv2.MORPH_RECT, (2,2)), 1)
    return th

def run_ocr(bin_img: np.ndarray):
    # PSM 11 = sparse text, good for drawings
    config = r"--oem 3 --psm 11"
    data = pytesseract.image_to_data(
        bin_img, lang="eng",
        output_type=pytesseract.Output.DICT,
        config=config
    )
    return data

LABEL_PAT = re.compile(r"(door|window|kitchen|bed|bedroom|toilet|bath|hall|living)", re.I)
# simple dimension patterns like 10', 3'6", 13', 3", 100
DIM_PAT   = re.compile(r"^\s*\d+\s*(\'\s*\d+\s*\")?$|^\s*\d+\s*\'$|^\s*\d+\s*\"$")

def annotate(img_bgr: np.ndarray, ocr_data: dict):
    overlay = img_bgr.copy()
    results = {"labels": [], "dimensions": [], "other": []}

    n = len(ocr_data["text"])
    for i in range(n):
        text = (ocr_data["text"][i] or "").strip()
        try:
            conf = float(ocr_data["conf"][i])
        except:
            conf = -1.0
        if not text or conf < 60:  # keep only confident detections
            continue

        x = int(ocr_data["left"][i])
        y = int(ocr_data["top"][i])
        w = int(ocr_data["width"][i])
        h = int(ocr_data["height"][i])

        # classify
        if LABEL_PAT.search(text):
            cat, color = "labels", (0, 200, 0)     # green
        elif DIM_PAT.search(text.replace("″", '"').replace("′", "'")) or any(c in text for c in ["'", '"']):
            cat, color = "dimensions", (200, 200, 0)  # yellow-ish
        else:
            cat, color = "other", (0, 140, 255)   # orange

        cv2.rectangle(overlay, (x, y), (x+w, y+h), color, 2)
        cv2.putText(overlay, text, (x, max(0, y-4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)

        results[cat].append({"text": text, "conf": conf, "box": [x, y, w, h]})

    return overlay, results

if __name__ == "__main__":
    img = load_color(SAMPLE)
    bin_img = preprocess_for_ocr(img)
    ocr_data = run_ocr(bin_img)
    annotated, results = annotate(img.copy(), ocr_data)

    OUT_IMG.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT_IMG), annotated)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Saved OCR overlay to {OUT_IMG}")
    print(f"Saved OCR JSON to   {OUT_JSON}")
