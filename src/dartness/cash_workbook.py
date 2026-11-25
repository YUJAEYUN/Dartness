"""Readable three-column workbook for a specified-report checkpoint, not final screening."""

import io
import math
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font
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
    minimum = format(_eok(result.minimum_krw), ",f")
    if "." in minimum:
        minimum = minimum.rstrip("0").rstrip(".")
    day = result.checked_at.astimezone(ZoneInfo("Asia/Seoul")).date()
    _text(
        sheet,
        1,
        1,
        f"{day} 조회 | {minimum}억원 이상 | 지정 공시 1건·개발용(전수/최신정정 미확인)",
    )
    for column, title in enumerate(("법인명", "현금및현금성자산(억원)", "조회 기준"), 1):
        _text(sheet, 2, column, title)
    value = result.value
    if result.status == "document_match" and isinstance(value, CashValue):
        amount = _numeric_eok(value.amount_krw)
        _text(sheet, 3, 1, result.disclosure.corp_name)
        if result.viewer_link is not None and result.viewer_link.value != value:
            raise ValueError("viewer_link_value_mismatch")
        target = result.viewer_link.url if result.viewer_link else value.evidence.source_url
        sheet.cell(3, 1).hyperlink = Hyperlink(ref="A3", target=target)
        sheet.cell(3, 2, amount)
        # Display rounding never participates in condition comparison.
        sheet.cell(3, 2).number_format = "#,##0.00"
        basis = {
            "separate": "법인 자체(별도)",
            "individual": "법인 자체(개별)",
            "consolidated": "그룹 전체(연결)",
        }[value.basis]
        _text(sheet, 3, 3, f"{value.as_of:%Y.%m.%d} · {basis}")
        sheet.cell(3, 2).comment = Comment(
            f"원문 숫자: {value.raw_amount.raw_value}\n적용 단위: {value.raw_amount.unit}\n"
            f"정확한 원화 금액: {value.amount_krw:,}원\n공시일: {result.disclosure.filed_on}\n"
            f"접수번호: {result.disclosure.receipt}\n"
            "표시는 억원 단위 소수 둘째 자리이며 조건은 정확한 원화 값으로 비교했습니다.\n"
            + (
                "법인명 링크: 금액·기준일·단위를 대조한 재무상태표 구간입니다.\n"
                if result.viewer_link
                else "표 바로가기 미확인: 법인명 링크는 공시 전체를 엽니다.\n"
            )
            + "이 미리보기의 재무 범위는 입력 기준입니다.",
            "Dartness",
        )
        sheet.auto_filter.ref = "A2:C3"
    else:
        sheet.merge_cells("A3:C3")
        _text(
            sheet,
            3,
            1,
            "확인 필요: 결과를 확정하지 못했습니다."
            if result.status == "needs_review"
            else "지정 공시에서는 조건 충족 금액이 확인되지 않았습니다.",
        )
    sheet.column_dimensions["A"].width = 22
    sheet.column_dimensions["B"].width = 24
    sheet.column_dimensions["C"].width = 45
    sheet.freeze_panes = "A3"
    sheet.sheet_view.showGridLines = True
    sheet.sheet_format.defaultRowHeight = 15
    sheet.print_area = "A1:C3"
    for row in sheet:
        for cell in row:
            cell.font = Font(name="맑은 고딕", size=10, color="000000", bold=cell.row in (1, 2))
            cell.alignment = Alignment(horizontal="left", vertical="center")
    if sheet.cell(3, 1).hyperlink is not None:
        sheet.cell(3, 1).font = Font(name="맑은 고딕", size=10, color="0563C1", underline="single")
    buffer = io.BytesIO()
    book.save(buffer)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(buffer.getvalue())
