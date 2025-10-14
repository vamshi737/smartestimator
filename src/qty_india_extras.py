# src/qty_india_extras.py
"""
Extends India-mode quantities with:
- Paint areas & liters (interior/exterior, coats, coverage, openings deduction)
- Basic steel placeholders (lintels/sunshades/stair waist) via simple inputs
- Labor cost (brickwork m3, plaster m2, paint m2 per-coat)
- Optional rate merge from data/prices.json
Reads Day-7 JSON and writes merged total JSON/CSV.
"""

from pathlib import Path
import json, argparse, sys, csv

def load_json(p: Path):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def try_load(p: Path):
    return load_json(p) if p.exists() else None

def clamp_nonneg(x: float) -> float:
    return x if x > 0 else 0.0

def main():
    ap = argparse.ArgumentParser(description="India extras: paint, basic steel, labor, cost merge")
    ap.add_argument("--base", default="data/output/qty_india.json",
                    help="Day-7 output JSON to extend")
    ap.add_argument("--prices", default="data/prices.json",
                    help="optional prices.json to add costs")
    # Paint
    ap.add_argument("--int_coats", type=int, default=2)
    ap.add_argument("--ext_coats", type=int, default=2)
    ap.add_argument("--coverage_m2_per_liter", type=float, default=10.0,
                    help="paint coverage per coat (m2 per liter)")
    ap.add_argument("--int_openings_m2", type=float, default=0.0)
    ap.add_argument("--ext_openings_m2", type=float, default=0.0)
    # Steel (simple placeholders; all optional)
    ap.add_argument("--lintel_length_m", type=float, default=0.0,
                    help="total lintel length (m) across openings")
    ap.add_argument("--lintel_kg_per_m", type=float, default=4.0,
                    help="kg of steel per meter of lintel (thumb rule)")
    ap.add_argument("--sunshade_area_m2", type=float, default=0.0)
    ap.add_argument("--sunshade_kg_per_m2", type=float, default=12.0)
    ap.add_argument("--stair_area_m2", type=float, default=0.0,
                    help="waist slab plan area")
    ap.add_argument("--stair_kg_per_m2", type=float, default=25.0)
    # Labor (simple factors)
    ap.add_argument("--labor_brickwork_per_m3", type=float, default=0.0)
    ap.add_argument("--labor_plaster_per_m2", type=float, default=0.0)
    ap.add_argument("--labor_paint_per_m2_per_coat", type=float, default=0.0)
    # Outputs
    ap.add_argument("--out_json", default="data/output/qty_india_total.json")
    ap.add_argument("--out_csv",  default="data/output/qty_india_total.csv")
    args = ap.parse_args()

    base_path = Path(args.base)
    if not base_path.exists():
        sys.exit(f"[Error] Base JSON not found: {args.base} (run Day-7 first)")

    base = load_json(base_path)
    prices = try_load(Path(args.prices))
    rates = prices.get("IN", {}) if prices and "IN" in prices else {}

    # Pull needed Day-7 values
    derived = base.get("derived", {})
    plaster = base.get("plaster", {})
    brickwork = base.get("brickwork", {})
    mortar_brickwork = base.get("mortar_brickwork", {})
    inputs = base.get("inputs", {})

    sum_int_m = float(derived.get("sum_interior_m", 0.0))
    sum_ext_m = float(derived.get("sum_exterior_m", 0.0))
    height = float(inputs.get("wall_height_value", 0.0))
    height_unit = inputs.get("wall_height_unit", "m")

    # Day-7 stored height value in given unit; derived lengths are meters.
    # For volumes/areas in meters, we must convert height to meters.
    # If unit is ft, assume it was converted already in Day-7 math; however we only have numeric.
    # To remain consistent with Day-7 outputs (which used meters), compute area using meters:
    # We cannot 100% know if height is meters here; safe path: reconstruct height_m from plaster area if non-zero.
    # But simplest: ask user to trust meters—Day-7 did conversions internally. We will re-derive height_m:
    # height_m can be recovered from plaster sides/area; but keep simple and read from derived volumes:
    # We will compute height_m from Day-7 brickwork volume to avoid mismatch only if possible.
    # If sum of lengths is > 0, estimate height as plaster.area / (sum_int_m*sides + sum_ext_m*sides)
    # To avoid complexity, use the same approach as Day-7: assume height used there equals wall_height_value in args,
    # and if inputs unit was ft, we cannot convert reliably here. So we compute areas via Day-7 plaster area
    # when available and recompute paint areas proportionally to plaster sides. For clarity and stability,
    # we will compute paint areas directly: int_area = sum_int_m * height_m; ext_area = sum_ext_m * height_m.
    # We try to back out height_m from plaster.area when possible.

    # Try to infer height_m from Day-7 plaster area if available:
    A_plaster_total = float(plaster.get("area_m2", 0.0))
    pl_int_sides = int(inputs.get("plaster_int_sides", 2))
    pl_ext_sides = int(inputs.get("plaster_ext_sides", 1))
    height_m_inferred = None
    denom = (sum_int_m * pl_int_sides) + (sum_ext_m * pl_ext_sides)
    if A_plaster_total > 0 and denom > 0:
        height_m_inferred = A_plaster_total / denom

    # Fallback: if we cannot infer, assume height is meters already (common if Day-7 ran in meters).
    height_m = height_m_inferred if height_m_inferred is not None else height

    # Paintable areas before openings
    int_area_m2 = clamp_nonneg(sum_int_m * height_m)
    ext_area_m2 = clamp_nonneg(sum_ext_m * height_m)

    # Deduct openings
    int_area_net_m2 = clamp_nonneg(int_area_m2 - float(args.int_openings_m2))
    ext_area_net_m2 = clamp_nonneg(ext_area_m2 - float(args.ext_openings_m2))

    # Coats and liters (per coat coverage)
    cov = max(float(args.coverage_m2_per_liter), 0.0001)
    int_liters = (int_area_net_m2 * int(args.int_coats)) / cov
    ext_liters = (ext_area_net_m2 * int(args.ext_coats)) / cov
    paint = {
        "interior_area_m2": int_area_net_m2,
        "exterior_area_m2": ext_area_net_m2,
        "interior_coats": int(args.int_coats),
        "exterior_coats": int(args.ext_coats),
        "coverage_m2_per_liter": cov,
        "interior_liters": int_liters,
        "exterior_liters": ext_liters,
        "total_liters": int_liters + ext_liters
    }

    # Basic steel placeholders
    lintel_kg = clamp_nonneg(float(args.lintel_length_m) * float(args.lintel_kg_per_m))
    sunshade_kg = clamp_nonneg(float(args.sunshade_area_m2) * float(args.sunshade_kg_per_m2))
    stair_kg = clamp_nonneg(float(args.stair_area_m2) * float(args.stair_kg_per_m2))
    steel_basic = {
        "lintel_length_m": float(args.lintel_length_m),
        "lintel_kg_per_m": float(args.lintel_kg_per_m),
        "lintel_kg": lintel_kg,
        "sunshade_area_m2": float(args.sunshade_area_m2),
        "sunshade_kg_per_m2": float(args.sunshade_kg_per_m2),
        "sunshade_kg": sunshade_kg,
        "stair_area_m2": float(args.stair_area_m2),
        "stair_kg_per_m2": float(args.stair_kg_per_m2),
        "stair_kg": stair_kg,
        "total_steel_kg": lintel_kg + sunshade_kg + stair_kg
    }

    # Labor
    vol_brickwork_m3 = float(derived.get("vol_brickwork_m3", 0.0))
    A_plaster_total_m2 = float(plaster.get("area_m2", 0.0))
    coats_total = int(args.int_coats) + int(args.ext_coats)

    labor = {
        "factors": {
            "brickwork_per_m3": float(args.labor_brickwork_per_m3),
            "plaster_per_m2": float(args.labor_plaster_per_m2),
            "paint_per_m2_per_coat": float(args.labor_paint_per_m2_per_coat)
        },
        "quantities": {
            "brickwork_m3": vol_brickwork_m3,
            "plaster_m2": A_plaster_total_m2,
            "paint_m2_total_coats": (paint["interior_area_m2"] * int(args.int_coats)) + (paint["exterior_area_m2"] * int(args.ext_coats))
        }
    }
    labor["costs"] = {
        "brickwork_labor": vol_brickwork_m3 * float(args.labor_brickwork_per_m3),
        "plaster_labor": A_plaster_total_m2 * float(args.labor_plaster_per_m2),
        "paint_labor": labor["quantities"]["paint_m2_total_coats"] * float(args.labor_paint_per_m2_per_coat)
    }
    labor["total_labor"] = sum(labor["costs"].values())

    # Cost merge (optional)
    cost_optional = base.get("cost_optional", {}).copy() if isinstance(base.get("cost_optional", {}), dict) else {}

    # Paint material
    if "paint_per_liter" in rates:
        cost_optional["paint_material"] = paint["total_liters"] * float(rates["paint_per_liter"])

    # Steel material
    if "steel_per_kg" in rates:
        cost_optional["steel_material"] = steel_basic["total_steel_kg"] * float(rates["steel_per_kg"])

    # Labor (if not set via CLI, allow rates from file)
    if labor["costs"]["brickwork_labor"] == 0 and "labor_brickwork_per_m3" in rates:
        labor["costs"]["brickwork_labor"] = vol_brickwork_m3 * float(rates["labor_brickwork_per_m3"])
    if labor["costs"]["plaster_labor"] == 0 and "labor_plaster_per_m2" in rates:
        labor["costs"]["plaster_labor"] = A_plaster_total_m2 * float(rates["labor_plaster_per_m2"])
    if labor["costs"]["paint_labor"] == 0 and "labor_paint_per_m2_per_coat" in rates:
        labor["costs"]["paint_labor"] = labor["quantities"]["paint_m2_total_coats"] * float(rates["labor_paint_per_m2_per_coat"])

    # Recompute total labor after rate overrides
    labor["total_labor"] = sum(labor["costs"].values())

    # If prices provided, keep previous bricks/cement/sand costs and add new items
    if cost_optional is None:
        cost_optional = {}

    # Merge all
    merged = {
        "inputs_base": inputs,
        "derived_base": derived,
        "brickwork_base": brickwork,
        "mortar_brickwork_base": mortar_brickwork,
        "plaster_base": plaster,
        "paint": paint,
        "steel_basic": steel_basic,
        "labor": labor,
        "cost_optional": cost_optional
    }

    # Totals rollup (if any material/labor present)
    totals = {}
    if cost_optional:
        totals["materials_cost_subtotal"] = sum(v for v in cost_optional.values() if isinstance(v, (int, float)))
    totals["labor_cost_subtotal"] = labor["total_labor"]
    totals["grand_total"] = totals.get("materials_cost_subtotal", 0.0) + totals.get("labor_cost_subtotal", 0.0)
    merged["totals"] = totals

    # Write JSON
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)

    # Write CSV
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        # Base summary
        w.writerow(["group","metric","value","unit"])
        w.writerow(["base","vol_brickwork", derived.get("vol_brickwork_m3", 0.0), "m3"])
        w.writerow(["base","plaster_area", plaster.get("area_m2", 0.0), "m2"])
        # Paint
        w.writerow(["paint","interior_area", paint["interior_area_m2"], "m2"])
        w.writerow(["paint","exterior_area", paint["exterior_area_m2"], "m2"])
        w.writerow(["paint","coats_interior", paint["interior_coats"], "coat"])
        w.writerow(["paint","coats_exterior", paint["exterior_coats"], "coat"])
        w.writerow(["paint","coverage", paint["coverage_m2_per_liter"], "m2_per_liter"])
        w.writerow(["paint","interior_liters", paint["interior_liters"], "liter"])
        w.writerow(["paint","exterior_liters", paint["exterior_liters"], "liter"])
        w.writerow(["paint","total_liters", paint["total_liters"], "liter"])
        # Steel
        w.writerow(["steel","lintel_length", steel_basic["lintel_length_m"], "m"])
        w.writerow(["steel","lintel_kg", steel_basic["lintel_kg"], "kg"])
        w.writerow(["steel","sunshade_area", steel_basic["sunshade_area_m2"], "m2"])
        w.writerow(["steel","sunshade_kg", steel_basic["sunshade_kg"], "kg"])
        w.writerow(["steel","stair_area", steel_basic["stair_area_m2"], "m2"])
        w.writerow(["steel","stair_kg", steel_basic["stair_kg"], "kg"])
        w.writerow(["steel","total_kg", steel_basic["total_steel_kg"], "kg"])
        # Labor
        w.writerow(["labor","brickwork_m3", labor["quantities"]["brickwork_m3"], "m3"])
        w.writerow(["labor","plaster_m2", labor["quantities"]["plaster_m2"], "m2"])
        w.writerow(["labor","paint_m2_total_coats", labor["quantities"]["paint_m2_total_coats"], "m2*coat"])
        w.writerow(["labor","brickwork_cost", labor["costs"]["brickwork_labor"], "currency"])
        w.writerow(["labor","plaster_cost", labor["costs"]["plaster_labor"], "currency"])
        w.writerow(["labor","paint_cost", labor["costs"]["paint_labor"], "currency"])
        w.writerow(["labor","labor_total", labor["total_labor"], "currency"])
        # Cost optional (materials)
        for k,v in cost_optional.items():
            w.writerow(["materials", k, v, "currency"])
        # Totals
        w.writerow(["totals","materials_cost_subtotal", totals.get("materials_cost_subtotal", 0.0), "currency"])
        w.writerow(["totals","labor_cost_subtotal", totals.get("labor_cost_subtotal", 0.0), "currency"])
        w.writerow(["totals","grand_total", totals.get("grand_total", 0.0), "currency"])

    print("OK: Extras computed and merged.")
    print(f"JSON: {args.out_json}")
    print(f"CSV : {args.out_csv}")
    if prices:
        print("Note: costs included from prices.json if matching keys were found.")
    else:
        print("Note: prices.json not found; materials/labor defaults used if provided.")
    
if __name__ == "__main__":
    main()
