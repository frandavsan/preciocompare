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
_ANALYSIS_SHEET_NAMES = ("Analisis", "Análisis")
_PRICE_ROW_LABEL = "precio"
_DATA_ROW_START = 5
_COL_CARD_LABEL = 1   # A
_COL_COUNT = 2         # B
_COL_DESCRIPTION = 9   # I
_DATA_COMMERCE_CELL = "C3"
_ANALYSIS_COMMERCE_CELL = "K1"


def _find_price_row(ws) -> int | None:
    for excel_row in range(1, ws.max_row + 1):
        card_label = ws.cell(excel_row, _COL_CARD_LABEL).value
        description = ws.cell(excel_row, _COL_DESCRIPTION).value
        if (
            str(card_label or "").strip().lower() == _PRICE_ROW_LABEL
            or str(description or "").strip().lower() == _PRICE_ROW_LABEL
        ):
            return excel_row
    return None


def _get_analysis_sheet(wb):
    for sheet_name in _ANALYSIS_SHEET_NAMES:
        if sheet_name in wb.sheetnames:
            return wb[sheet_name]
    return None


def read_template(path: str | Path) -> list[TemplateRow]:
    """
    Parse the Excel template and return all data rows as TemplateRow objects.

    Reads the payment-plan rows from the "Datos" sheet, extracting:
      - Column A: card label (e.g. "VISA/MASTER MACRO")
      - Column B: installment count (e.g. 3, 6, 12)
      - Column I: description text (e.g. "3 sin int Macro")

    Rows with missing card_label or count are skipped. The template's "Precio"
    row is intentionally skipped because it is filled separately with product
    prices instead of interest rates.
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    try:
        ws = wb[_SHEET_NAME]

        rows: list[TemplateRow] = []
        for excel_row in range(_DATA_ROW_START, ws.max_row + 1):
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
    commerce_name: str | None = None,
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
        price_row = _find_price_row(ws)
        normalized_commerce_name = (commerce_name or "").strip()

        if normalized_commerce_name:
            ws[_DATA_COMMERCE_CELL] = normalized_commerce_name
            cells_written += 1
            analysis_ws = _get_analysis_sheet(wb)
            if analysis_ws is not None:
                analysis_ws[_ANALYSIS_COMMERCE_CELL] = normalized_commerce_name
                cells_written += 1

        if price_row is not None:
            for store_name, pricing_result in results.items():
                col_idx = store_col_idx.get(store_name)
                if not col_idx:
                    continue
                ws.cell(
                    price_row,
                    col_idx,
                    pricing_result.base_price if pricing_result.base_price > 0 else "-",
                )
                cells_written += 1

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
