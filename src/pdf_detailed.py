# src/pdf_detailed.py
"""
Generates a polished PDF with title/logo, date, summary tables and charts:
- Reads:
    data/output/qty_india_total.json (optional)
    data/output/qty_usa.json        (optional)
    data/output/final_breakdown.json  (preferred if exists)
    data/prices.json (for currency)
    data/logo.png (optional)
- Writes:
    data/output/final_estimate_detailed.pdf
"""

from pathlib import Path
import json
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image, PageBreak
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

# ---------- main ----------
def main():
    out_pdf = Path("data/output/final_estimate_detailed.pdf")
    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    prices = try_load(Path("data/prices.json"), {})
    currency = ""
    if isinstance(prices, dict) and "GLOBAL" in prices and isinstance(prices["GLOBAL"], dict):
        currency = str(prices["GLOBAL"].get("currency", "")) or ""

    # Prefer the consolidated breakdown if present
    fb = try_load(Path("data/output/final_breakdown.json"), {})
    india = try_load(Path("data/output/qty_india_total.json"), {})
    usa   = try_load(Path("data/output/qty_usa.json"), {})

    # Pull subtotals either from final_breakdown or raw files
    IN_mat = safe_num(fb, "subtotals", "india", "materials", default=safe_num(india, "totals", "materials_cost_subtotal"))
    IN_lab = safe_num(fb, "subtotals", "india", "labor",     default=safe_num(india, "totals", "labor_cost_subtotal"))
    US_mat = safe_num(fb, "subtotals", "usa",   "materials", default=safe_num(usa,   "totals", "materials_cost_subtotal"))
    US_lab = safe_num(fb, "subtotals", "usa",   "labor",     default=safe_num(usa,   "totals", "labor_cost_subtotal"))

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
        ["Materials Subtotal", f"{IN_mat + US_mat:,.2f}"],
        ["Labor Subtotal",     f"{IN_lab + US_lab:,.2f}"],
        ["Grand Total",        f"{grand_total:,.2f}"],
    ]
    t = Table(summary_rows, colWidths=[75*mm, 50*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (1,1), (-1,-1), "RIGHT"),
        ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
        ("BOTTOMPADDING", (0,0), (-1,0), 6),
    ]))
    story.append(Paragraph("Summary", styles["Heading2"]))
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
    story.append(Paragraph("Assumptions", styles["Heading2"]))
    story.append(t2)
    story.append(Spacer(1, 12))

    # -------- Pie: Materials vs Labor (combined) --------
    story.append(Paragraph("Materials vs Labor (Overall)", styles["Heading3"]))
    d = Drawing(160, 120)
    pie = Pie()
    pie.x = 20; pie.y = 5
    pie.width = 120; pie.height = 120
    mat_total = IN_mat + US_mat
    lab_total = IN_lab + US_lab
    # Avoid zero-division: if both zero, keep 0,0
    pie.data = [mat_total, lab_total] if (mat_total + lab_total) > 0 else [0, 0]
    pie.labels = ["Materials", "Labor"]
    pie.sideLabels = True
    d.add(pie)
    story.append(d)
    story.append(Spacer(1, 12))

    # -------- Comparison Table: India vs USA --------
    story.append(Paragraph("Regional Comparison (India vs USA)", styles["Heading2"]))
    comp_rows = [
        ["Category", "INDIA", "USA"],
        ["Materials", f"{IN_mat:,.2f}", f"{US_mat:,.2f}"],
        ["Labor",     f"{IN_lab:,.2f}", f"{US_lab:,.2f}"],
        ["Total",     f"{(IN_mat+IN_lab):,.2f}", f"{(US_mat+US_lab):,.2f}"],
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
    story.append(Paragraph("Totals by Region (Bar)", styles["Heading3"]))
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
    # two series: India, USA
    d2.add(bar)
    story.append(d2)

    # Footer page break (future pages could hold BOQ / line-items)
    # story.append(PageBreak())

    doc.build(story)
    print(f"OK: Detailed PDF generated -> {out_pdf}")

if __name__ == "__main__":
    main()
