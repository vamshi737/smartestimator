# src/excel_charts.py
"""
Adds a 'Charts' sheet to final_estimate.xlsx with:
- Pie chart: Materials vs Labor
- Bar chart: Overheads, Contingency, Profit, Tax
- Grand Total callout

Assumes the 'Summary' sheet has:
Row 4: headers ["Section","Amount"]
Rows 5..12: the 8 rows created by rates_export.py:
  5  Materials Subtotal
  6  Labor Subtotal
  7  Subtotal (Materials + Labor)
  8  Overheads
  9  Contingency
 10  Profit
 11  Tax
 12  Grand Total
"""

import sys
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment
from openpyxl.chart import PieChart, BarChart, Reference

def main():
    xlsx_path = Path("data/output/final_estimate.xlsx")
    if not xlsx_path.exists():
        sys.exit("[Error] Excel not found. Run rates_export.py first to generate data/output/final_estimate.xlsx")

    wb = load_workbook(xlsx_path)
    if "Summary" not in wb.sheetnames:
        sys.exit("[Error] 'Summary' sheet not found. Did you generate the workbook with rates_export.py?")

    # Remove old Charts sheet if present (so re-runs are clean)
    if "Charts" in wb.sheetnames:
        ws_old = wb["Charts"]
        wb.remove(ws_old)

    ws_sum = wb["Summary"]
    ws = wb.create_sheet("Charts")

    # Title
    ws["A1"] = "Visualization – Final Estimate"
    ws["A1"].font = Font(bold=True, size=14)

    # Grand Total callout (Summary!B12)
    ws["A3"] = "Grand Total"
    ws["A3"].font = Font(bold=True, size=12)
    ws["B3"] = ws_sum["B12"].value  # copy the number
    ws["B3"].number_format = ws_sum["B5"].number_format or "#,##0.00"
    ws["B3"].font = Font(bold=True, size=14)
    ws["B3"].alignment = Alignment(horizontal="left")

    # Pie: Materials vs Labor (Summary!A5:A6 and B5:B6)
    pie = PieChart()
    pie.title = "Materials vs Labor"
    data = Reference(ws_sum, min_col=2, min_row=5, max_row=6)      # B5:B6
    labels = Reference(ws_sum, min_col=1, min_row=5, max_row=6)    # A5:A6
    pie.add_data(data, titles_from_data=False)
    pie.set_categories(labels)
    pie.height = 12
    pie.width = 18
    ws.add_chart(pie, "A5")

    # Bar: Overheads, Contingency, Profit, Tax (Summary!A8:A11 & B8:B11)
    bar = BarChart()
    bar.title = "Overheads / Contingency / Profit / Tax"
    bar.y_axis.title = "Amount"
    bar.x_axis.title = "Component"
    data2 = Reference(ws_sum, min_col=2, min_row=8, max_row=11)     # B8:B11
    cats2 = Reference(ws_sum, min_col=1, min_row=8, max_row=11)     # A8:A11
    bar.add_data(data2, titles_from_data=False)
    bar.set_categories(cats2)
    bar.height = 12
    bar.width = 24
    ws.add_chart(bar, "J5")

    # Neaten columns a bit
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 20

    wb.save(xlsx_path)
    print("OK: Charts added to Excel.")
    print(f"Updated workbook: {xlsx_path}")

if __name__ == "__main__":
    main()
