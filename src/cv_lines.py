# src/cv_lines.py
from pathlib import Path
import cv2
import numpy as np
import json

# Try both names so your CAD export works either way
CANDIDATES = [Path("data/samples/plan1.png"), Path("data/samples/PLAN1.png")]
for p in CANDIDATES:
    if p.exists():
        SAMPLE = p
        break
else:
    raise FileNotFoundError("Put plan1.png (or PLAN1.png) in data/samples/")

OUT_IMG = Path("data/samples/lines_plan1.png")
OUT_JSON = Path("data/samples/lines_plan1.json")

def auto_canny(gray: np.ndarray, sigma: float = 0.33):
    # automatic Canny thresholds based on image median
    v = np.median(gray)
    lower = int(max(0, (1.0 - sigma) * v))
    upper = int(min(255, (1.0 + sigma) * v))
    edges = cv2.Canny(gray, lower, upper, apertureSize=3, L2gradient=True)
    return edges, (lower, upper)

def detect_lines(edges: np.ndarray):
    """
    Run Probabilistic Hough Transform.
    Tune the params if needed:
    - threshold: how many votes to accept a line (higher = fewer lines)
    - minLineLength: minimum length of a detected line (in pixels)
    - maxLineGap: merge broken segments if the gap is less than this
    """
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=80,        # try 50–150
        minLineLength=60,    # try 40–120 depending on scale
        maxLineGap=10        # try 5–20
    )
    return [] if lines is None else lines.reshape(-1, 4).tolist()

def main():
    # 1) load original
    img_color = cv2.imread(str(SAMPLE), cv2.IMREAD_COLOR)
    if img_color is None:
        raise FileNotFoundError(f"Cannot read image: {SAMPLE}")

    # 2) grayscale + slight blur
    gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3,3), 0)

    # 3) edges (auto thresholds)
    edges, (lo, hi) = auto_canny(gray)

    # 4) HoughLinesP
    lines = detect_lines(edges)

    # 5) draw lines overlay
    overlay = img_color.copy()
    for (x1,y1,x2,y2) in lines:
        cv2.line(overlay, (x1,y1), (x2,y2), (0,0,255), 2)  # red lines

    # 6) save image + json (with lengths in pixels for now)
    OUT_IMG.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT_IMG), overlay)

    lines_info = []
    for (x1,y1,x2,y2) in lines:
        length_px = float(np.hypot(x2-x1, y2-y1))
        lines_info.append({"p1":[x1,y1], "p2":[x2,y2], "length_px": length_px})

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"canny_thresholds":[lo,hi], "lines": lines_info}, f, indent=2)

    print(f"Detected {len(lines_info)} lines")
    print(f"Saved line overlay to {OUT_IMG}")
    print(f"Saved lines JSON to   {OUT_JSON}")

if __name__ == "__main__":
    main()
