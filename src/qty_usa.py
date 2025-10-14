# src/qty_usa.py
"""
USA-mode framing & finishes from wall totals.

Reads wall lengths from data/samples/metrics_walls.json (same file used earlier).
Produces framing counts (studs @ 16" or 24" o.c.), plates LF, sheathing and drywall
sheet counts, insulation packs, fasteners, optional labor/material costs, and totals.

Outputs:
- data/output/qty_usa.json
- data/output/qty_usa.csv
"""

from pathlib import Path
import json, argparse, math, csv, sys

FT_PER_M = 3.280839895

def load_json(p: Path):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def try_load(p: Path):
    return load_json(p) if p.exists() else None

def ceil(x): return math.ceil(x)

def main():
    ap = argparse.ArgumentParser(description="USA-mode framing and finishes")
    ap.add_argument("--walls", default="data/samples/metrics_walls.json",
                    help="metrics_walls.json with totals.sum_exterior_{unit} and totals.sum_interior_{unit}")
    ap.add_argument("--prices", default="data/prices.json",
                    help="optional prices.json with a US section for rates")

    # Geometry
    ap.add_argument("--height_ft", type=float, required=True, help="Wall height (feet)")

    # Studs
    ap.add_argument("--spacing_in", type=int, choices=[16,24], default=16)
    ap.add_argument("--stud_size", choices=["2x4","2x6"], default="2x4")
    ap.add_argument("--stud_wastage_pct", type=float, default=10.0,
                    help="waste/adders to cover corners, ends, tees, culls (percent)")

    # Plates (bottom + double top)
    ap.add_argument("--plate_stock_ft", type=int, choices=[8,10,12,14,16], default=12)
    ap.add_argument("--plate_wastage_pct", type=float, default=10.0)

    # Sheathing and Drywall
    ap.add_argument("--sheath_sheet", choices=["4x8","4x12"], default="4x8")
    ap.add_argument("--drywall_sheet", choices=["4x8","4x12"], default="4x12")
    ap.add_argument("--sheath_wastage_pct", type=float, default=10.0)
    ap.add_argument("--drywall_wastage_pct", type=float, default=10.0)

    # Openings (deducted from areas)
    ap.add_argument("--openings_ext_sqft", type=float, default=0.0,
                    help="total exterior openings area in sqft (windows, doors)")
    ap.add_argument("--openings_int_sqft", type=float, default=0.0,
                    help="optional deduction for interior drywall (doors etc.)")

    # Insulation
    ap.add_argument("--insul_coverage_sqft_per_pack", type=float, default=40.0,
                    help="coverage per pack for chosen R-value (sqft/pack)")
    ap.add_argument("--insul_wastage_pct", type=float, default=5.0)

    # Fasteners (simple rules of thumb)
    ap.add_argument("--stud_nails_per_stud", type=int, default=8,
                    help="approx nails to attach plates/blocks per stud")
    ap.add_argument("--sheath_fasteners_per_sheet", type=int, default=40)
    ap.add_argument("--drywall_screws_per_sheet", type=int, default=32)

    # Labor overrides (if 0, will try to take from prices.json)
    ap.add_argument("--labor_frame_per_stud", type=float, default=0.0)
    ap.add_argument("--labor_sheath_per_sheet", type=float, default=0.0)
    ap.add_argument("--labor_drywall_per_sheet", type=float, default=0.0)
    ap.add_argument("--labor_insul_per_pack", type=float, default=0.0)

    ap.add_argument("--out_json", default="data/output/qty_usa.json")
    ap.add_argument("--out_csv",  default="data/output/qty_usa.csv")
    args = ap.parse_args()

    walls_path = Path(args.walls)
    if not walls_path.exists():
        sys.exit(f"[Error] walls file not found: {args.walls}")

    walls = load_json(walls_path)
    prices = try_load(Path(args.prices))
    rates = prices.get("US", {}) if prices and "US" in prices else {}

    unit = walls.get("unit", "ft")
    totals = walls.get("totals", {})
    sum_ext = float(totals.get(f"sum_exterior_{unit}", 0.0))
    sum_int = float(totals.get(f"sum_interior_{unit}", 0.0))

    # Convert to feet
    if unit == "m":
        sum_ext_ft = sum_ext * FT_PER_M
        sum_int_ft = sum_int * FT_PER_M
    else:
        sum_ext_ft = sum_ext
        sum_int_ft = sum_int

    height_ft = float(args.height_ft)

    # -------------------------
    # 1) STUDS @ spacing
    # total wall length to frame = exterior + interior
    total_len_ft = sum_ext_ft + sum_int_ft
    total_len_in = total_len_ft * 12.0
    base_studs = math.floor(total_len_in / float(args.spacing_in)) + 1  # line studs
    # adders to roughly capture corners/tees/end studs/waste
    studs_total = math.ceil(base_studs * (1.0 + args.stud_wastage_pct / 100.0))

    # -------------------------
    # 2) PLATES LF and PIECES
    plates_lf = total_len_ft * 3.0  # bottom + double top
    plates_lf_waste = plates_lf * (1.0 + args.plate_wastage_pct / 100.0)
    plate_stock = float(args.plate_stock_ft)
    plate_pieces = math.ceil(plates_lf_waste / plate_stock)

    # -------------------------
    # 3) SHEATHING (exterior only)
    # area = exterior length * height - exterior openings
    A_sheath = max(0.0, sum_ext_ft * height_ft - float(args.openings_ext_sqft))
    if args.sheath_sheet == "4x8":
        sheet_area = 4.0 * 8.0
    else:
        sheet_area = 4.0 * 12.0
    sheath_sheets = math.ceil((A_sheath * (1.0 + args.sheath_wastage_pct / 100.0)) / sheet_area)

    # -------------------------
    # 4) DRYWALL (interior both sides)
    A_drywall = max(0.0, sum_int_ft * height_ft * 2.0 - float(args.openings_int_sqft))
    if args.drywall_sheet == "4x8":
        dw_sheet_area = 4.0 * 8.0
    else:
        dw_sheet_area = 4.0 * 12.0
    drywall_sheets = math.ceil((A_drywall * (1.0 + args.drywall_wastage_pct / 100.0)) / dw_sheet_area)

    # -------------------------
    # 5) INSULATION (exterior walls)
    # common practice: insulate exterior walls; coverage per pack
    insul_area = max(0.0, sum_ext_ft * height_ft)  # openings ignored for simplicity
    insul_packs = math.ceil((insul_area * (1.0 + args.insul_wastage_pct / 100.0)) / float(args.insul_coverage_sqft_per_pack))

    # -------------------------
    # 6) FASTENERS (simple thumb rules)
    stud_nails = studs_total * int(args.stud_nails_per_stud)
    sheath_fasteners = sheath_sheets * int(args.sheath_fasteners_per_sheet)
    drywall_screws = drywall_sheets * int(args.drywall_screws_per_sheet)

    # -------------------------
    # 7) COSTS (optional)
    cost = {}

    # lumber studs and plates
    # Allow separate pricing by size; fallback to generic if missing
    key_stud = f"{args.stud_size}_stud_per_piece"
    stud_price = float(rates.get(key_stud, rates.get("stud_per_piece", 0.0)))
    cost["studs_material"] = studs_total * stud_price

    key_plate = f"{args.stud_size}_plate_per_piece"
    plate_price = float(rates.get(key_plate, rates.get("plate_per_piece", 0.0)))
    cost["plates_material"] = plate_pieces * plate_price

    # sheathing and drywall
    key_sheath = f"sheathing_{args.sheath_sheet}_per_sheet"
    cost["sheathing_material"] = sheath_sheets * float(rates.get(key_sheath, rates.get("sheathing_per_sheet", 0.0)))

    key_dw = f"drywall_{args.drywall_sheet}_per_sheet"
    cost["drywall_material"] = drywall_sheets * float(rates.get(key_dw, rates.get("drywall_per_sheet", 0.0)))

    # insulation packs
    cost["insulation_material"] = insul_packs * float(rates.get("insulation_pack", 0.0))

    # fasteners
    cost["nails_material"] = stud_nails * float(rates.get("nail_each", 0.0)) \
                             + sheath_fasteners * float(rates.get("sheath_fastener_each", 0.0))
    cost["screws_material"] = drywall_screws * float(rates.get("drywall_screw_each", 0.0))

    # labor; use CLI overrides first; if zero, try file rates
    labor = {}
    labor["frame"] = studs_total * ( args.labor_frame_per_stud if args.labor_frame_per_stud > 0
                                     else float(rates.get("labor_frame_per_stud", 0.0)) )
    labor["sheathing"] = sheath_sheets * ( args.labor_sheath_per_sheet if args.labor_sheath_per_sheet > 0
                                           else float(rates.get("labor_sheath_per_sheet", 0.0)) )
    labor["drywall"] = drywall_sheets * ( args.labor_drywall_per_sheet if args.labor_drywall_per_sheet > 0
                                          else float(rates.get("labor_drywall_per_sheet", 0.0)) )
    labor["insulation"] = insul_packs * ( args.labor_insul_per_pack if args.labor_insul_per_pack > 0
                                          else float(rates.get("labor_insul_per_pack", 0.0)) )

    materials_subtotal = sum(v for v in cost.values() if isinstance(v, (int,float)))
    labor_subtotal = sum(v for v in labor.values() if isinstance(v, (int,float)))
    grand_total = materials_subtotal + labor_subtotal

    # Pack JSON
    out = {
        "inputs": {
            "unit_source": unit,
            "sum_exterior_ft": sum_ext_ft,
            "sum_interior_ft": sum_int_ft,
            "height_ft": height_ft,
            "spacing_in": args.spacing_in,
            "stud_size": args.stud_size,
            "stud_wastage_pct": args.stud_wastage_pct,
            "plate_stock_ft": args.plate_stock_ft,
            "plate_wastage_pct": args.plate_wastage_pct,
            "sheath_sheet": args.sheath_sheet,
            "drywall_sheet": args.drywall_sheet,
            "sheath_wastage_pct": args.sheath_wastage_pct,
            "drywall_wastage_pct": args.drywall_wastage_pct,
            "openings_ext_sqft": args.openings_ext_sqft,
            "openings_int_sqft": args.openings_int_sqft,
            "insul_coverage_sqft_per_pack": args.insul_coverage_sqft_per_pack,
            "insul_wastage_pct": args.insul_wastage_pct,
            "stud_nails_per_stud": args.stud_nails_per_stud,
            "sheath_fasteners_per_sheet": args.sheath_fasteners_per_sheet,
            "drywall_screws_per_sheet": args.drywall_screws_per_sheet
        },
        "framing": {
            "studs_total": studs_total
        },
        "plates": {
            "lf_base": plates_lf,
            "lf_with_waste": plates_lf_waste,
            "stock_length_ft": plate_stock,
            "pieces": plate_pieces
        },
        "sheathing": {
            "area_sqft": A_sheath,
            "sheet": args.sheath_sheet,
            "sheets": sheath_sheets
        },
        "drywall": {
            "area_sqft": A_drywall,
            "sheet": args.drywall_sheet,
            "sheets": drywall_sheets
        },
        "insulation": {
            "area_sqft": insul_area,
            "packs": insul_packs,
            "coverage_sqft_per_pack": args.insul_coverage_sqft_per_pack
        },
        "fasteners": {
            "stud_nails": stud_nails,
            "sheath_fasteners": sheath_fasteners,
            "drywall_screws": drywall_screws
        },
        "labor": labor,
        "cost_optional": cost,
        "totals": {
            "materials_cost_subtotal": materials_subtotal,
            "labor_cost_subtotal": labor_subtotal,
            "grand_total": grand_total
        }
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group","metric","value","unit"])
        w.writerow(["framing","studs_total", out["framing"]["studs_total"], "piece"])
        w.writerow(["plates","lf_with_waste", out["plates"]["lf_with_waste"], "ft"])
        w.writerow(["plates","pieces", out["plates"]["pieces"], "piece"])
        w.writerow(["sheathing","area", out["sheathing"]["area_sqft"], "sqft"])
        w.writerow(["sheathing","sheets", out["sheathing"]["sheets"], "sheet"])
        w.writerow(["drywall","area", out["drywall"]["area_sqft"], "sqft"])
        w.writerow(["drywall","sheets", out["drywall"]["sheets"], "sheet"])
        w.writerow(["insulation","area", out["insulation"]["area_sqft"], "sqft"])
        w.writerow(["insulation","packs", out["insulation"]["packs"], "pack"])
        w.writerow(["fasteners","stud_nails", out["fasteners"]["stud_nails"], "each"])
        w.writerow(["fasteners","sheath_fasteners", out["fasteners"]["sheath_fasteners"], "each"])
        w.writerow(["fasteners","drywall_screws", out["fasteners"]["drywall_screws"], "each"])
        for k,v in cost.items():
            w.writerow(["materials", k, v, "currency"])
        for k,v in labor.items():
            w.writerow(["labor", k, v, "currency"])
        w.writerow(["totals","materials_cost_subtotal", materials_subtotal, "currency"])
        w.writerow(["totals","labor_cost_subtotal", labor_subtotal, "currency"])
        w.writerow(["totals","grand_total", grand_total, "currency"])

    print("OK: USA-mode quantities computed.")
    print(f"JSON: {args.out_json}")
    print(f"CSV : {args.out_csv}")
    if prices:
        print("Note: costs included from prices.json if matching US keys were found.")
    else:
        print("Note: prices.json not found; cost sections default to zero.")

if __name__ == "__main__":
    main()
