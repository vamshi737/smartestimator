# src/main.py
"""
End-to-end runner for SmartEstimator (Week 4 build).
Copies final artifacts to --outdir for the API to serve.
"""

import argparse, subprocess, sys, shutil
from pathlib import Path

def run(cmd, cwd=None):
    print("-> " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd)
    if r.returncode != 0:
        sys.exit(r.returncode)

def file_exists(p):
    return Path(p).exists()

def copy_if_exists(src: Path, dst_dir: Path):
    if src.exists():
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst_dir / src.name)
        print(f"[copy] {src} -> {dst_dir / src.name}")
    else:
        print(f"[warn] artifact not found: {src}")

def main():
    ap = argparse.ArgumentParser(description="SmartEstimator one-shot runner")
    ap.add_argument("--mode", choices=["india","usa","both","all"], default="all",
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

    # API flags
    ap.add_argument("--input", dest="input_image", default=None,
                    help="Optional path to input plan image (not used by current pipeline)")
    ap.add_argument("--outdir", default="data/output",
                    help="Directory to copy final artifacts for API/download")

    args = ap.parse_args()

    DATA_OUTPUT = Path("data/output")
    DATA_OUTPUT.mkdir(parents=True, exist_ok=True)

    OUTDIR = Path(args.outdir)
    OUTDIR.mkdir(parents=True, exist_ok=True)

    if args.input_image:
        print(f"[info] Received --input {args.input_image} (not used by this pipeline).")

    walls_json = "data/samples/metrics_walls.json"
    if not file_exists(walls_json):
        print(f"[Warn] {walls_json} not found. Run your Week-1 wall metrics step first.")

    # 1) INDIA quantities
    if args.mode in ("india","both","all"):
        run([sys.executable, "src/qty_india.py",
             "--height", str(args.in_height_ft),
             "--unit", "ft",
             "--ext_thk_mm", "230", "--int_thk_mm", "115",
             "--walls", walls_json,
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
    if args.mode in ("usa","both","all"):
        run([sys.executable, "src/qty_usa.py",
             "--height_ft", str(args.us_height_ft),
             "--spacing_in", "16", "--stud_size", "2x4",
             "--openings_ext_sqft", str(args.us_openings_ext_sqft),
             "--openings_int_sqft", str(args.us_openings_int_sqft),
             "--prices", args.prices,
             "--out_json", str(DATA_OUTPUT / "qty_usa.json"),
             "--out_csv",  str(DATA_OUTPUT / "qty_usa.csv")])

    # 3) Rates + XLSX/PDF summary export
    if args.mode in ("both","all","india","usa"):
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
