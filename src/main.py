# src/main.py
"""
End-to-end runner for SmartEstimator.

Pipeline:
- (Assumes metrics_walls.json already exists from Week 1 steps)
- India quantities (optional)
- USA quantities (optional)
- Rates export (xlsx/pdf/json)
- Excel charts (Charts sheet)
- Comparative dashboard (Compare sheet + PNG)
- Enhanced PDF (detailed)

Examples:
  python src/main.py --mode all --prices data/prices.json --in_height_ft 10 --us_height_ft 9
"""

import argparse, subprocess, sys
from pathlib import Path

def run(cmd, cwd=None):
    print("-> " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd)
    if r.returncode != 0:
        sys.exit(r.returncode)

def file_exists(p):
    return Path(p).exists()

def main():
    ap = argparse.ArgumentParser(description="SmartEstimator one-shot runner")
    ap.add_argument("--mode", choices=["india","usa","both","all"], default="all",
                    help="'all' = india + usa + exports + charts + pdf")
    ap.add_argument("--prices", default="data/prices.json")
    # Heights (required for quantity steps)
    ap.add_argument("--in_height_ft", type=float, default=10.0, help="India wall height in feet (original project used ft)")
    ap.add_argument("--us_height_ft", type=float, default=8.0, help="USA wall height in feet")
    # Optional openings (affects paint & drywall/sheathing)
    ap.add_argument("--in_int_openings_m2", type=float, default=0.0)
    ap.add_argument("--in_ext_openings_m2", type=float, default=0.0)
    ap.add_argument("--us_openings_ext_sqft", type=float, default=0.0)
    ap.add_argument("--us_openings_int_sqft", type=float, default=0.0)
    args = ap.parse_args()

    walls_json = "data/samples/metrics_walls.json"
    if not file_exists(walls_json):
        print("[Warn] %s not found. Run your Week-1 wall metrics step first." % walls_json)

    # 1) INDIA quantities (base + extras)
    if args.mode in ("india","both","all"):
        run([
            sys.executable, "src/qty_india.py",
            "--height", str(args.in_height_ft),
            "--unit", "ft",
            "--ext_thk_mm", "230", "--int_thk_mm", "115",
            "--walls", walls_json,
            "--out_json", "data/output/qty_india.json",
            "--out_csv",  "data/output/qty_india.csv",
        ])
        run([
            sys.executable, "src/qty_india_extras.py",
            "--base", "data/output/qty_india.json",
            "--prices", args.prices,
            "--int_openings_m2", str(args.in_int_openings_m2),
            "--ext_openings_m2", str(args.in_ext_openings_m2),
            "--out_json", "data/output/qty_india_total.json",
            "--out_csv",  "data/output/qty_india_total.csv",
        ])

    # 2) USA quantities
    if args.mode in ("usa","both","all"):
        run([
            sys.executable, "src/qty_usa.py",
            "--height_ft", str(args.us_height_ft),
            "--spacing_in", "16", "--stud_size", "2x4",
            "--openings_ext_sqft", str(args.us_openings_ext_sqft),
            "--openings_int_sqft", str(args.us_openings_int_sqft),
            "--prices", args.prices,
            "--out_json", "data/output/qty_usa.json",
            "--out_csv",  "data/output/qty_usa.csv",
        ])

    # 3) Rates + XLSX/PDF summary export
    if args.mode in ("both","all","india","usa"):
        run([
            sys.executable, "src/rates_export.py",
            "--prices", args.prices,
            "--in_json", "data/output/qty_india_total.json",
            "--us_json", "data/output/qty_usa.json",
            "--out_xlsx", "data/output/final_estimate.xlsx",
            "--out_pdf",  "data/output/final_estimate.pdf",
            "--out_json", "data/output/final_breakdown.json",
        ])

    # 4) Excel charts (Charts sheet)
    run([sys.executable, "src/excel_charts.py"])

    # 5) Compare dashboard (Compare sheet + PNG)
    run([sys.executable, "src/compare_dashboard.py"])

    # 6) Enhanced detailed PDF
    run([sys.executable, "src/pdf_detailed.py"])

    print("")
    print("OK: Pipeline completed.")
    print("Outputs:")
    print(" - data/output/final_estimate.xlsx (Summary, Rates, Details, Charts, Compare)")
    print(" - data/output/final_estimate.pdf")
    print(" - data/output/final_estimate_detailed.pdf")
    print(" - data/output/final_breakdown.json")
    print(" - data/output/compare_preview.png")

if __name__ == "__main__":
    main()
