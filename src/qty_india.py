# src/qty_india.py
"""
India mode quantities:
- Uses wall lengths (interior/exterior) from metrics_walls.json
- Applies wall heights & thicknesses
- Computes brickwork volume, bricks, mortar (cement+sand), and plaster
- Optional simple costing if prices.json is present
"""

from pathlib import Path
import json, argparse, math, sys

FT_TO_M = 0.3048

def load_json(p: Path):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def try_load(p: Path):
    return load_json(p) if p.exists() else None

def parse_ratio(s: str):
    a, b = s.split(":")
    return float(a), float(b)

def main():
    ap = argparse.ArgumentParser(description="India quantities (bricks, cement, sand, plaster)")
    ap.add_argument("--walls", default="data/samples/metrics_walls.json",
                    help="metrics_walls.json (from Day-5)")
    ap.add_argument("--prices", default="data/prices.json",
                    help="optional prices.json for rough cost")
    ap.add_argument("--height", type=float, required=True,
                    help="Wall height value")
    ap.add_argument("--unit", choices=["ft", "m"], default="ft",
                    help="Unit for height (and walls metrics unit). Use 'ft' if your scaling was in feet.")
    ap.add_argument("--ext_thk_mm", type=float, default=230.0,
                    help="Exterior wall thickness in mm (default 230)")
    ap.add_argument("--int_thk_mm", type=float, default=115.0,
                    help="Interior wall thickness in mm (default 115)")
    ap.add_argument("--brick_size_mm", default="190x90x90",
                    help="Modular brick size (without mortar), e.g. 190x90x90")
    ap.add_argument("--mortar_ratio", default="1:6",
                    help="Cement : Sand ratio for brickwork (default 1:6)")
    ap.add_argument("--mortar_dry_factor", type=float, default=1.33,
                    help="Dry volume factor for mortar (default 1.33)")
    ap.add_argument("--plaster_thk_mm", type=float, default=12.0,
                    help="Plaster thickness in mm (per side, default 12)")
    ap.add_argument("--plaster_ratio", default="1:4",
                    help="Cement : Sand ratio for plaster (default 1:4)")
    ap.add_argument("--plaster_int_sides", type=int, default=2,
                    help="Interior wall sides to plaster (default 2)")
    ap.add_argument("--plaster_ext_sides", type=int, default=1,
                    help="Exterior wall sides to plaster (default 1)")
    ap.add_argument("--out_json", default="data/output/qty_india.json")
    ap.add_argument("--out_csv", default="data/output/qty_india.csv")
    args = ap.parse_args()

    walls_path = Path(args.walls)
    if not walls_path.exists():
        sys.exit(f"[Error] '{args.walls}' not found. Make sure Day-5 produced metrics_walls.json at that path.")

    try:
        walls = load_json(walls_path)
    except Exception as e:
        sys.exit(f"[Error] Could not read '{args.walls}': {e}")

    prices = try_load(Path(args.prices))

    unit_from_walls = walls.get("unit", "ft")
    perpx = float(walls.get("per_pixel", 0.02))
    totals = walls.get("totals", {})

    sum_ext = float(totals.get(f"sum_exterior_{unit_from_walls}", 0.0))
    sum_int = float(totals.get(f"sum_interior_{unit_from_walls}", 0.0))

    # Convert lengths & height to meters
    if args.unit == "ft":
        height_m = args.height * FT_TO_M
        sum_ext_m = sum_ext * FT_TO_M
        sum_int_m = sum_int * FT_TO_M
    else:
        height_m = args.height
        sum_ext_m = sum_ext
        sum_int_m = sum_int

    # Wall thickness (m)
    ext_t_m = args.ext_thk_mm / 1000.0
    int_t_m = args.int_thk_mm / 1000.0

    # Brick nominal incl. 10mm mortar
    try:
        bL, bW, bH = [float(x) for x in args.brick_size_mm.lower().split("x")]
    except:
        bL, bW, bH = 190.0, 90.0, 90.0
    bL_nom = (bL + 10.0) / 1000.0
    bW_nom = (bW + 10.0) / 1000.0
    bH_nom = (bH + 10.0) / 1000.0
    brick_vol_m3 = bL_nom * bW_nom * bH_nom

    # Brickwork volumes (m3)
    vol_ext_m3 = sum_ext_m * height_m * ext_t_m
    vol_int_m3 = sum_int_m * height_m * int_t_m
    vol_brickwork_m3 = vol_ext_m3 + vol_int_m3

    # Bricks count
    bricks_nos = vol_brickwork_m3 / brick_vol_m3
    wastage = 0.07
    if prices and "IN" in prices and "wastage" in prices["IN"]:
        wastage = float(prices["IN"]["wastage"])
    bricks_nos_w = bricks_nos * (1.0 + wastage)

    # Mortar for brickwork
    wet_mortar_m3 = 0.30 * vol_brickwork_m3
    dry_factor = args.mortar_dry_factor
    dry_mortar_m3 = wet_mortar_m3 * dry_factor

    c_part, s_part = parse_ratio(args.mortar_ratio)
    total_part = c_part + s_part
    cement_m3 = dry_mortar_m3 * (c_part / total_part)
    sand_m3 = dry_mortar_m3 * (s_part / total_part)
    cement_bags = cement_m3 / 0.035

    # Plaster
    A_plaster_int_m2 = sum_int_m * args.plaster_int_sides * height_m
    A_plaster_ext_m2 = sum_ext_m * args.plaster_ext_sides * height_m
    A_plaster_total_m2 = A_plaster_int_m2 + A_plaster_ext_m2

    t_pl_m = args.plaster_thk_mm / 1000.0
    wet_plaster_m3 = A_plaster_total_m2 * t_pl_m
    dry_plaster_m3 = wet_plaster_m3 * 1.27

    pc_part, ps_part = parse_ratio(args.plaster_ratio)
    total_p = pc_part + ps_part
    pl_cement_m3 = dry_plaster_m3 * (pc_part / total_p)
    pl_sand_m3 = dry_plaster_m3 * (ps_part / total_p)
    pl_cement_bags = pl_cement_m3 / 0.035

    # Cost (optional)
    cost = {}
    if prices and "IN" in prices:
        rate = prices["IN"]
        cost["bricks"] = bricks_nos_w * float(rate.get("brick_per_piece", 0.0))
        cost["cement_bags"] = (cement_bags + pl_cement_bags) * float(rate.get("cement_bag_50kg", 0.0))
        cost["sand_m3"] = (sand_m3 + pl_sand_m3) * float(rate.get("sand_per_cum", 0.0))
        if "plaster_per_sqm" in rate:
            cost["plaster_per_sqm"] = A_plaster_total_m2 * float(rate["plaster_per_sqm"])

    out = {
        "inputs": {
            "unit_source": unit_from_walls,
            "per_pixel": perpx,
            "wall_height_unit": args.unit,
            "wall_height_value": args.height,
            "ext_thickness_mm": args.ext_thk_mm,
            "int_thickness_mm": args.int_thk_mm,
            "brick_size_mm": args.brick_size_mm,
            "mortar_ratio": args.mortar_ratio,
            "mortar_dry_factor": args.mortar_dry_factor,
            "plaster_thk_mm": args.plaster_thk_mm,
            "plaster_ratio": args.plaster_ratio,
            "plaster_int_sides": args.plaster_int_sides,
            "plaster_ext_sides": args.plaster_ext_sides,
            "wastage": wastage
        },
        "derived": {
            "sum_exterior_m": sum_ext_m,
            "sum_interior_m": sum_int_m,
            "vol_brickwork_m3": vol_brickwork_m3
        },
        "brickwork": {
            "bricks_nominal_vol_m3": brick_vol_m3,
            "bricks_count_without_wastage": bricks_nos,
            "bricks_count_with_wastage": bricks_nos_w
        },
        "mortar_brickwork": {
            "wet_mortar_m3": wet_mortar_m3,
            "dry_mortar_m3": dry_mortar_m3,
            "cement_bags": cement_bags,
            "sand_m3": sand_m3
        },
        "plaster": {
            "area_m2": A_plaster_total_m2,
            "wet_mortar_m3": wet_plaster_m3,
            "dry_mortar_m3": dry_plaster_m3,
            "cement_bags": pl_cement_bags,
            "sand_m3": pl_sand_m3
        },
        "cost_optional": cost
    }

    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    import csv
    csv_path = Path(args.out_csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group", "metric", "value", "unit"])
        w.writerow(["brickwork", "volume", out["derived"]["vol_brickwork_m3"], "m3"])
        w.writerow(["brickwork", "bricks (with wastage)", out["brickwork"]["bricks_count_with_wastage"], "nos"])
        w.writerow(["mortar", "cement bags (brickwork)", out["mortar_brickwork"]["cement_bags"], "bag"])
        w.writerow(["mortar", "sand (brickwork)", out["mortar_brickwork"]["sand_m3"], "m3"])
        w.writerow(["plaster", "area", out["plaster"]["area_m2"], "m2"])
        w.writerow(["plaster", "cement bags", out["plaster"]["cement_bags"], "bag"])
        w.writerow(["plaster", "sand", out["plaster"]["sand_m3"], "m3"])

    print("OK: Quantities computed (India mode).")
    print(f"JSON: {args.out_json}")
    print(f"CSV : {args.out_csv}")
    if prices:
        print("Note: 'cost_optional' section added using data/prices.json")
    else:
        print("Note: prices.json not found; skipped cost section.")

if __name__ == "__main__":
    main()
