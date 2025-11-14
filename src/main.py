# src/main.py
"""
End-to-end runner for SmartEstimator — Week 5 Day 24 (OCR-first compatible)

What’s new vs your previous Day-23 script:
- Accepts optional geometry args from app.py:
    --metrics_area, --metrics_walls, --metrics_source
- Prefer OCR metrics when provided (or when data/output/metrics_*.json exist)
- Correctly reads totals from the new JSON schema:
    area:  payload["totals"]["total_area_ft2"]
    walls: payload["totals"]["total_wall_length_ft"]  (or len(segments)>0)
"""

import argparse, subprocess, sys, shutil, json
from pathlib import Path
from typing import Optional


def run(cmd, cwd=None):
    print("-> " + " ".join(map(str, cmd)))
    r = subprocess.run(cmd, cwd=cwd)
    if r.returncode != 0:
        sys.exit(r.returncode)


def file_exists(p) -> bool:
    return Path(p).exists()


def copy_if_exists(src: Path, dst_dir: Path):
    if src.exists():
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst_dir / src.name)
        print(f"[copy] {src} -> {dst_dir / src.name}")
    else:
        print(f"[warn] artifact not found: {src}")


def load_json_silent(path: Path) -> Optional[dict]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def main():
    ap = argparse.ArgumentParser(description="SmartEstimator one-shot runner (Day-24)")
    ap.add_argument("--mode", choices=["india", "usa", "both", "all"], default="all",
                    help="'all' = india + usa + exports + charts + pdf")
    ap.add_argument("--prices", default="data/prices.json")

    # Heights (required for quantity steps)
    ap.add_argument("--in_height_ft", type=float, default=10.0, help="India wall height in feet")
    ap.add_argument("--us_height_ft", type=float, default=8.0, help="USA wall height in feet")

    # Optional openings
    ap.add_argument("--in_int_openings_m2", type=float, default=0.0)
    ap.add_argument("--in_ext_openings_m2", type=float, default=0.0)
    ap.add_argument("--us_openings_ext_sqft", type=float, default=0.0)
    ap.add_argument("--us_openings_int_sqft", type=float, default=0.0)

    # API flags (input not used by pipeline, kept for backwards-compat)
    ap.add_argument("--input", dest="input_image", default=None,
                    help="Optional path to input plan image (not used by this pipeline)")
    ap.add_argument("--outdir", default="data/output",
                    help="Directory to copy final artifacts for API/download")

    # NEW — Day 24 OCR-first geometry hooks (harmless if not passed)
    ap.add_argument("--metrics_area", type=str, default=None)
    ap.add_argument("--metrics_walls", type=str, default=None)
    ap.add_argument("--metrics_source", choices=["ocr", "sample"], default="ocr")

    args = ap.parse_args()

    DATA_OUTPUT = Path("data/output")
    DATA_OUTPUT.mkdir(parents=True, exist_ok=True)

    OUTDIR = Path(args.outdir)
    OUTDIR.mkdir(parents=True, exist_ok=True)

    if args.input_image:
        print(f"[info] Received --input {args.input_image} (not used by this pipeline).")

    # -----------------------------
    # Day 24: Prefer OCR geometry
    # -----------------------------
    # Choose candidate paths
    area_candidate = Path(args.metrics_area) if args.metrics_area else DATA_OUTPUT / "metrics_area.json"
    walls_candidate = Path(args.metrics_walls) if args.metrics_walls else DATA_OUTPUT / "metrics_walls.json"

    # Load payloads (if present)
    area_payload = load_json_silent(area_candidate) or {}
    walls_payload = load_json_silent(walls_candidate) or {}

    # Detect OCR validity from new schema
    def _walls_ok(wp: dict) -> bool:
        totals = (wp.get("totals") or {})
        total_len = float(totals.get("total_wall_length_ft", 0.0))
        segs = wp.get("walls") or wp.get("segments") or []
        return total_len > 0.0 or len(segs) > 0

    def _area_info(apl: dict) -> float:
        totals = (apl.get("totals") or {})
        return float(totals.get("total_area_ft2", 0.0))

    use_ocr = False
    geometry_source = args.metrics_source

    if geometry_source == "ocr" and file_exists(walls_candidate):
        if _walls_ok(walls_payload):
            use_ocr = True
        else:
            print("[warn] OCR walls JSON present but empty/invalid; will fallback to sample.")
            geometry_source = "sample"

    default_walls_json = Path("data/samples/metrics_walls.json")
    if geometry_source == "sample":
        if not default_walls_json.exists():
            print(f"[warn] {default_walls_json} not found. Run Week-1 wall metrics step to generate samples.")
        walls_candidate = default_walls_json

    # Log what we’re using
    if use_ocr:
        print(f"[info] Using OCR geometry: {walls_candidate}")
        if area_payload:
            print(f"[info] OCR total area (ft²): {_area_info(area_payload)}")
    else:
        print(f"[info] Using SAMPLE geometry: {walls_candidate}")

    # 1) INDIA quantities
    if args.mode in ("india", "both", "all"):
        run([sys.executable, "src/qty_india.py",
             "--height", str(args.in_height_ft),
             "--unit", "ft",
             "--ext_thk_mm", "230", "--int_thk_mm", "115",
             "--walls", str(walls_candidate),
             "--out_json", str(DATA_OUTPUT / "qty_india.json"),
             "--out_csv",  str(DATA_OUTPUT / "qty_india.csv")])
        run([sys.executable, "src/qty_india_extras.py",
             "--base", str(DATA_OUTPUT / "qty_india.json"),
             "--prices", args.prices,
             "--int_openings_m2", str(args.in_int_openings_m2),
             "--ext_openings_m2", str(args.in_ext_openings_m2),
             "--out_json", str(DATA_OUTPUT / "qty_india_total.json"),
             "--out_csv",  str(DATA_OUTPUT / "qty_india_total.csv")])

    # 2) USA quantities
    if args.mode in ("usa", "both", "all"):
        run([sys.executable, "src/qty_usa.py",
             "--height_ft", str(args.us_height_ft),
             "--spacing_in", "16", "--stud_size", "2x4",
             "--openings_ext_sqft", str(args.us_openings_ext_sqft),
             "--openings_int_sqft", str(args.us_openings_int_sqft),
             "--prices", args.prices,
             "--out_json", str(DATA_OUTPUT / "qty_usa.json"),
             "--out_csv",  str(DATA_OUTPUT / "qty_usa.csv")])

    # 3) Rates + XLSX/PDF summary export
    if args.mode in ("both", "all", "india", "usa"):
        run([sys.executable, "src/rates_export.py",
             "--prices", args.prices,
             "--in_json", str(DATA_OUTPUT / "qty_india_total.json"),
             "--us_json", str(DATA_OUTPUT / "qty_usa.json"),
             "--out_xlsx", str(DATA_OUTPUT / "final_estimate.xlsx"),
             "--out_pdf",  str(DATA_OUTPUT / "final_estimate.pdf"),
             "--out_json", str(DATA_OUTPUT / "final_breakdown.json")])

    # 3.5) Enhancements
    run([sys.executable, "src/enhancements/area_summary.py"])
    run([sys.executable, "src/enhancements/doors_windows.py"])
    run([sys.executable, "src/enhancements/flooring.py"])

    # 4) Excel charts
    run([sys.executable, "src/excel_charts.py"])

    # 5) Compare dashboard
    run([sys.executable, "src/compare_dashboard.py"])

    # 6) Enhanced detailed PDF
    run([sys.executable, "src/pdf_detailed.py"])

    # 7) BOQ sheet
    run([sys.executable, "src/boq_excel.py"])

    # Copy artifacts for API
    copy_if_exists(DATA_OUTPUT / "final_estimate.xlsx", OUTDIR)
    copy_if_exists(DATA_OUTPUT / "final_estimate.pdf",  OUTDIR)
    copy_if_exists(DATA_OUTPUT / "final_breakdown.json", OUTDIR)
    copy_if_exists(DATA_OUTPUT / "final_estimate_detailed.pdf", OUTDIR)
    copy_if_exists(DATA_OUTPUT / "compare_preview.png", OUTDIR)

    print("\nOK: Pipeline completed.")
    print("Artifacts in:", OUTDIR.resolve())


if __name__ == "__main__":
    main()
