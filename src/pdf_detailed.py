# src/pdf_detailed.py
"""
Generates a polished PDF with title/logo, date, summary tables, charts,
and enhancement sections (Doors & Windows, Flooring, Area Summary).

Reads:
  data/output/qty_india_total.json   (optional)
  data/output/qty_usa.json           (optional)
  data/output/final_breakdown.json   (preferred if exists)
  data/output/doors_windows.json     (optional, Day 2)
  data/output/flooring.json          (optional, Day 3)
  data/output/area_summary.json      (optional, Day 4)
  data/prices.json                   (for currency)
  data/logo.png                      (optional)

Writes:
  data/output/final_estimate_detailed.pdf
"""

from pathlib import Path
import json
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart

# ---------- helpers ----------
def load_json(p: Path):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def try_load(p: Path, default=None):
    if p.exists():
        return load_json(p)
    return default

def safe_num(d, *keys, default=0.0):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    try:
        return float(cur)
    except Exception:
        return default

def fmt_money(x, currency=""):
    try:
        s = f"{float(x):,.2f}"
    except Exception:
        s = "0.00"
    return (currency + " " + s) if currency else s

def heading(text, styles):
    return Paragraph(text, styles["Heading2"])

def subheading(text, styles):
    return Paragraph(text, styles["Heading3"])

# ---------- main ----------
def main():
    out_pdf = Path("data/output/final_estimate_detailed.pdf")
    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    prices = try_load(Path("data/prices.json"), {}) or {}
    currency = ""
    if isinstance(prices, dict) and "GLOBAL" in prices and isinstance(prices["GLOBAL"], dict):
        currency = str(prices["GLOBAL"].get("currency", "")) or ""

    # Prefer the consolidated breakdown if present
    fb = try_load(Path("data/output/final_breakdown.json"), {}) or {}
    india = try_load(Path("data/output/qty_india_total.json"), {}) or {}
    usa   = try_load(Path("data/output/qty_usa.json"), {}) or {}

    # Enhancements (new)
    doors_windows = try_load(Path("data/output/doors_windows.json"), {}) or {}
    flooring      = try_load(Path("data/output/flooring.json"), {}) or {}
    area_summary  = try_load(Path("data/output/area_summary.json"), {}) or {}

    # Pull subtotals either from final_breakdown or raw files
    IN_mat = safe_num(fb, "subtotals", "india", "materials",
                      default=safe_num(india, "totals", "materials_cost_subtotal"))
    IN_lab = safe_num(fb, "subtotals", "india", "labor",
                      default=safe_num(india, "totals", "labor_cost_subtotal"))
    US_mat = safe_num(fb, "subtotals", "usa", "materials",
                      default=safe_num(usa, "totals", "materials_cost_subtotal"))
    US_lab = safe_num(fb, "subtotals", "usa", "labor",
                      default=safe_num(usa, "totals", "labor_cost_subtotal"))

    grand_total = safe_num(fb, "summary", "grand_total", default=IN_mat+IN_lab+US_mat+US_lab)
    overhead_pct    = safe_num(fb, "summary", "overhead_pct",    default=0.0)
    contingency_pct = safe_num(fb, "summary", "contingency_pct", default=0.0)
    profit_pct      = safe_num(fb, "summary", "profit_pct",      default=0.0)
    tax_pct         = safe_num(fb, "summary", "tax_pct",         default=0.0)

    # Build the document
    doc = SimpleDocTemplate(
        str(out_pdf),
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=18*mm, bottomMargin=18*mm
    )
    styles = getSampleStyleSheet()
    story = []

    # Header row with optional logo
    logo_path = Path("data/logo.png")
    if logo_path.exists():
        img = Image(str(logo_path), width=28*mm, height=28*mm)
        story.append(img)
        story.append(Spacer(1, 6))

    # Title & meta
    story.append(Paragraph("Final Estimate Report", styles["Title"]))
    meta = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  Currency: {currency or 'N/A'}"
    story.append(Paragraph(meta, styles["Normal"]))
    story.append(Spacer(1, 10))

    # -------- Summary Table (materials/labor + grand total) --------
    summary_rows = [
        ["Section", "Amount"],
        ["Materials Subtotal", fmt_money(IN_mat + US_mat, currency)],
        ["Labor Subtotal",     fmt_money(IN_lab + US_lab, currency)],
        ["Grand Total",        fmt_money(grand_total, currency)],
    ]
    t = Table(summary_rows, colWidths=[75*mm, 50*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (1,1), (-1,-1), "RIGHT"),
        ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
        ("BOTTOMPADDING", (0,0), (-1,0), 6),
    ]))
    story.append(heading("Summary", styles))
    story.append(t)
    story.append(Spacer(1, 10))

    # -------- Assumptions Table --------
    ass_rows = [
        ["Assumption", "Value"],
        ["Overhead %",    f"{overhead_pct:g}"],
        ["Contingency %", f"{contingency_pct:g}"],
        ["Profit %",      f"{profit_pct:g}"],
        ["Tax %",         f"{tax_pct:g}"],
    ]
    t2 = Table(ass_rows, colWidths=[60*mm, 65*mm])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (1,1), (-1,-1), "RIGHT"),
        ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
    ]))
    story.append(heading("Assumptions", styles))
    story.append(t2)
    story.append(Spacer(1, 12))

    # -------- Pie: Materials vs Labor (combined) --------
    story.append(subheading("Materials vs Labor (Overall)", styles))
    d = Drawing(160, 120)
    pie = Pie()
    pie.x = 20; pie.y = 5
    pie.width = 120; pie.height = 120
    mat_total = IN_mat + US_mat
    lab_total = IN_lab + US_lab
    pie.data = [mat_total, lab_total] if (mat_total + lab_total) > 0 else [0, 0]
    pie.labels = ["Materials", "Labor"]
    pie.sideLabels = True
    d.add(pie)
    story.append(d)
    story.append(Spacer(1, 12))

    # -------- Comparison Table: India vs USA --------
    story.append(heading("Regional Comparison (India vs USA)", styles))
    comp_rows = [
        ["Category", "INDIA", "USA"],
        ["Materials", fmt_money(IN_mat, currency), fmt_money(US_mat, currency)],
        ["Labor",     fmt_money(IN_lab, currency), fmt_money(US_lab, currency)],
        ["Total",     fmt_money(IN_mat+IN_lab, currency), fmt_money(US_mat+US_lab, currency)],
    ]
    t3 = Table(comp_rows, colWidths=[55*mm, 45*mm, 45*mm])
    t3.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (1,1), (-1,-1), "RIGHT"),
        ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
    ]))
    story.append(t3)
    story.append(Spacer(1, 12))

    # -------- Mini bar chart: IN vs US totals --------
    story.append(subheading("Totals by Region (Bar)", styles))
    d2 = Drawing(300, 160)
    bar = VerticalBarChart()
    bar.x = 40; bar.y = 30
    bar.height = 100; bar.width = 220
    bar.data = [[IN_mat+IN_lab], [US_mat+US_lab]]
    bar.categoryAxis.categoryNames = ["Total"]
    bar.groupSpacing = 10
    bar.barWidth = 15
    bar.valueAxis.labels.fontName = "Helvetica"
    bar.valueAxis.visibleGrid = True
    d2.add(bar)
    story.append(d2)
    story.append(Spacer(1, 16))

    # =========================
    # NEW: Enhancement Sections
    # =========================

    # Doors & Windows
    if doors_windows:
        story.append(heading("Doors & Windows", styles))
        rows = [["Category", "Type", "Count", "Area m² (each)", "Rate/m²", "Amount"]]
        for cat in ("doors", "windows"):
            for it in doors_windows.get(cat, []):
                rows.append([
                    cat.capitalize(),
                    it.get("type", ""),
                    it.get("count", 0),
                    f"{it.get('area_m2_each', 0):.3f}",
                    fmt_money(it.get("rate_per_m2", 0), currency),
                    fmt_money(it.get("amount", 0), currency),
                ])
        totals = doors_windows.get("totals", {})
        rows.append(["", "", "", "", "Total", fmt_money(totals.get("total_amount", 0), currency)])
        t_dw = Table(rows, colWidths=[28*mm, 22*mm, 16*mm, 28*mm, 26*mm, 30*mm])
        t_dw.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("ALIGN", (2,1), (-1,-1), "RIGHT"),
            ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
        ]))
        story.append(t_dw)
        story.append(Spacer(1, 12))

    # Flooring
    if flooring:
        story.append(heading("Flooring / Marble / Tiles", styles))
        fr = [
            ["Material", str(flooring.get("material", ""))],
            ["Base Area (m²)", f"{flooring.get('area_m2', 0):.2f}"],
            ["Wastage %", f"{flooring.get('wastage_pct', 0):.2f}"],
            ["Total Area (m²)", f"{flooring.get('total_area_m2_with_wastage', 0):.2f}"],
            ["Rate / m²", fmt_money(flooring.get("rate_per_m2", 0), currency)],
            ["Amount", fmt_money(flooring.get("amount", 0), currency)],
        ]
        t_fl = Table(fr, colWidths=[55*mm, 70*mm])
        t_fl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
        ]))
        story.append(t_fl)
        story.append(Spacer(1, 12))

    # Area Summary
    if area_summary:
        story.append(heading("Area Summary", styles))
        ar = [
            ["Wall Area (m²)", f"{area_summary.get('wall_area_m2', 0):.2f}"],
            ["Openings Area (m²)", f"{area_summary.get('openings_area_m2', 0):.2f}"],
            ["Net Wall Area (m²)", f"{area_summary.get('net_wall_area_m2', 0):.2f}"],
            ["Floor Area (m²)", f"{area_summary.get('floor_area_m2', 0):.2f}"],
            ["Gross Area (m²)", f"{area_summary.get('gross_area_m2', 0):.2f}"],
        ]
        t_as = Table(ar, colWidths=[60*mm, 60*mm])
        t_as.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
        ]))
        story.append(t_as)
        story.append(Spacer(1, 10))

    # Build the PDF
    doc.build(story)
    print(f"OK: Detailed PDF generated -> {out_pdf}")

if __name__ == "__main__":
    main()
