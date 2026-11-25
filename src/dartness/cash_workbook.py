"""Readable three-column workbook for a specified-report checkpoint, not final screening."""

import io
import math
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.hyperlink import Hyperlink
from openpyxl.worksheet.worksheet import Worksheet

from dartness.cash_contract import CashValue
from dartness.cash_report_result import CashReportResult


def _text(sheet: Worksheet, row: int, column: int, value: str) -> None:
    cell = sheet.cell(row, column, value)
    # Company names and disclosure text must remain text, including leading '='.
    cell.data_type = "s"


def _eok(value: Decimal) -> Decimal:
    parts = value.as_tuple()
    if not isinstance(parts.exponent, int):
        raise ValueError("finite_workbook_amount_required")
    return Decimal((parts.sign, parts.digits, parts.exponent - 8))


def _numeric_eok(value: Decimal) -> Decimal:
    amount = _eok(value)
    parts = value.as_tuple()
    significant = len("".join(str(digit) for digit in parts.digits).rstrip("0"))
    if (
        significant > 15
        or not math.isfinite(float(amount))
        or Decimal(str(float(amount))) != amount
    ):
        raise ValueError("excel_numeric_precision_unavailable")
    return amount


def write_cash_report_workbook(result: CashReportResult, output: Path) -> None:
    """Only matching, known values become rows; preserve scope limits visibly."""
    if output.suffix.lower() != ".xlsx":
        raise ValueError("xlsx_output_required")
    result = replace(result)
    book = Workbook()
    sheet = book.active
    if not isinstance(sheet, Worksheet):
        raise ValueError("workbook_sheet_unavailable")
    sheet.title = "지정 공시 확인"
    sheet.merge_cells("A1:C1")
    sheet.merge_cells("A2:C2")
    sheet.merge_cells("A3:C3")
    _text(sheet, 1, 1, "현금 조회 · 지정 공시 확인")
    _text(
        sheet,
        2,
        1,
        "개발용: 공시 한 건의 비교입니다. 전수조사·최신 자료·정정 적용은 확인 전입니다.",
    )
    minimum = format(_eok(result.minimum_krw), ",f")
    if "." in minimum:
        minimum = minimum.rstrip("0").rstrip(".")
    _text(sheet, 3, 1, f"조건: {minimum}억원 이상 · 법인명 → 원문 · 금액 메모 → 정확한 원문 금액")
    for column, title in enumerate(("법인명", "현금및현금성자산(억원)", "조회 기준"), 1):
        _text(sheet, 4, column, title)
    value = result.value
    if result.status == "document_match" and isinstance(value, CashValue):
        amount = _numeric_eok(value.amount_krw)
        _text(sheet, 5, 1, result.disclosure.corp_name)
        sheet.cell(5, 1).hyperlink = Hyperlink(ref="A5", target=value.evidence.source_url)
        sheet.cell(5, 2, amount)
        # Display rounding never participates in condition comparison.
        sheet.cell(5, 2).number_format = "#,##0.00"
        basis = {
            "separate": "법인 자체(별도)",
            "individual": "법인 자체(개별)",
            "consolidated": "그룹 전체(연결)",
        }[value.basis]
        _text(sheet, 5, 3, f"{value.as_of:%Y.%m.%d}\n{basis}")
        sheet.cell(5, 2).comment = Comment(
            f"원문 숫자: {value.raw_amount.raw_value}\n적용 단위: {value.raw_amount.unit}\n"
            f"정확한 원화 금액: {value.amount_krw:,}원\n공시일: {result.disclosure.filed_on}\n"
            f"접수번호: {result.disclosure.receipt}\n"
            "표시는 억원 단위 소수 둘째 자리이며 조건은 정확한 원화 값으로 비교했습니다.\n"
            "법인명 링크에서 원문을 확인하세요. 이 미리보기의 재무 범위는 입력 기준입니다.",
            "Dartness",
        )
        sheet.auto_filter.ref = "A4:C5"
    else:
        sheet.merge_cells("A5:C5")
        _text(
            sheet,
            5,
            1,
            "확인 필요: 결과를 확정하지 못했습니다."
            if result.status == "needs_review"
            else "지정 공시에서는 조건 충족 금액이 확인되지 않았습니다.",
        )
    sheet.column_dimensions["A"].width = 25
    sheet.column_dimensions["B"].width = 31
    sheet.column_dimensions["C"].width = 30
    sheet.freeze_panes = "A5"
    sheet.sheet_view.showGridLines = False
    sheet.print_options.horizontalCentered = True
    sheet.print_area = "A1:C5"
    for row in sheet:
        for cell in row:
            cell.font = Font(name="맑은 고딕", size=14, color="17365D")
            cell.alignment = Alignment(vertical="center", wrap_text=True)
    sheet.row_dimensions[1].height = 36
    sheet.row_dimensions[2].height = 38
    sheet.row_dimensions[3].height = 34
    sheet.row_dimensions[4].height = 32
    sheet.row_dimensions[5].height = 42
    sheet.cell(1, 1).font = Font(name="맑은 고딕", size=20, bold=True, color="087E8B")
    sheet.cell(2, 1).font = Font(name="맑은 고딕", size=11, color="666666")
    sheet.cell(3, 1).font = Font(name="맑은 고딕", size=11, color="666666")
    for cell in sheet[4]:
        cell.font = Font(name="맑은 고딕", size=13, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="087E8B")
    if sheet.cell(5, 1).hyperlink is not None:
        sheet.cell(5, 1).font = Font(name="맑은 고딕", size=14, color="0563C1", underline="single")
    buffer = io.BytesIO()
    book.save(buffer)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(buffer.getvalue())
