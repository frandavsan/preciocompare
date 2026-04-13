"""
Excel I/O for the pricing spreadsheet.

read_template()  — parses the .xlsx template into TemplateRow objects
write_results()  — writes computed rates to store columns
"""

from __future__ import annotations

from pathlib import Path

import openpyxl

from .adapters import PRICING_STORES
from .card_mapping import find_matching_plan, parse_template_row
from .models import PricingResult, TemplateRow


# Template layout constants
_SHEET_NAME = "Datos"
_DATA_ROW_START = 4
_DATA_ROW_END = 64  # inclusive
_COL_CARD_LABEL = 1   # A
_COL_COUNT = 2         # B
_COL_DESCRIPTION = 9   # I


def read_template(path: str | Path) -> list[TemplateRow]:
    """
    Parse the Excel template and return all data rows as TemplateRow objects.

    Reads rows 4-64 from the "Datos" sheet, extracting:
      - Column A: card label (e.g. "VISA/MASTER MACRO")
      - Column B: installment count (e.g. 3, 6, 12)
      - Column I: description text (e.g. "3 sin int Macro")

    Rows with missing card_label or count are skipped.
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    try:
        ws = wb[_SHEET_NAME]

        rows: list[TemplateRow] = []
        for excel_row in range(_DATA_ROW_START, _DATA_ROW_END + 1):
            card_label = ws.cell(excel_row, _COL_CARD_LABEL).value
            count_val = ws.cell(excel_row, _COL_COUNT).value
            description = ws.cell(excel_row, _COL_DESCRIPTION).value

            if not card_label or count_val is None:
                continue

            try:
                count = int(count_val)
            except (ValueError, TypeError):
                continue

            rows.append(parse_template_row(
                excel_row=excel_row,
                card_label=str(card_label),
                installment_count=count,
                description=str(description) if description else "",
            ))
    finally:
        wb.close()
    return rows


def write_results(
    template_path: str | Path,
    output_path: str | Path,
    template_rows: list[TemplateRow],
    results: dict[str, PricingResult],
) -> int:
    """
    Write computed interest rates to the Excel spreadsheet.

    For each template row × store, finds the matching PaymentPlan and writes
    the interest rate to the store's column.

    Values written:
      - 0        for sin-interes plans available (rate = 0%)
      - 0.1952   for con-interes plans (decimal fraction)
      - "-"      for plans not available at this store
      - (blank)  for stores with no PricingResult

    Saves to output_path — never overwrites the template file.

    Returns the number of cells written.
    """
    store_col_idx = {
        ps.name: openpyxl.utils.column_index_from_string(ps.column)
        for ps in PRICING_STORES
    }

    wb = openpyxl.load_workbook(template_path)
    try:
        ws = wb[_SHEET_NAME]
        cells_written = 0

        for row in template_rows:
            for store_name, pricing_result in results.items():
                col_idx = store_col_idx.get(store_name)
                if not col_idx:
                    continue

                if pricing_result.status != "ok":
                    ws.cell(row.excel_row, col_idx, "-")
                    cells_written += 1
                    continue

                plan = find_matching_plan(row, pricing_result.plans)
                if plan is None:
                    ws.cell(row.excel_row, col_idx, "-")
                else:
                    ws.cell(row.excel_row, col_idx, plan.interest_rate)
                cells_written += 1

        wb.save(output_path)
    finally:
        wb.close()

    return cells_written
