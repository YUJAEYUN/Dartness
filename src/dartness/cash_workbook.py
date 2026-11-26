"""Readable three-column workbook for a specified-report checkpoint, not final screening."""

import io
import math
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.hyperlink import Hyperlink
from openpyxl.worksheet.worksheet import Worksheet

from dartness.cash_contract import CashValue
from dartness.cash_report_result import CashReportResult
from dartness.query_contract import QueryRun


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


def write_cash_report_workbook(
    result: CashReportResult,
    output: Path,
    *,
    source_scope: Literal[
        "specified_report", "captured_history_periodic_reports"
    ] = "specified_report",
) -> None:
    """Only matching, known values become rows; preserve scope limits visibly."""
    if source_scope not in ("specified_report", "captured_history_periodic_reports"):
        raise ValueError("supported_workbook_source_scope_required")
    if source_scope == "captured_history_periodic_reports" and result.request_run is None:
        raise ValueError("captured_history_request_run_required")
    if output.suffix.lower() != ".xlsx":
        raise ValueError("xlsx_output_required")
    result = replace(result)
    book, sheet = _new_cash_sheet("지정 공시 확인")
    minimum = format(_eok(result.minimum_krw), ",f")
    if "." in minimum:
        minimum = minimum.rstrip("0").rstrip(".")
    day = result.checked_at.astimezone(ZoneInfo("Asia/Seoul")).date()
    requested = f"기준 {result.request_run.anchor_date} | " if result.request_run else ""
    scope_note = (
        "지정 이력 내 최신 선택·개발용(전수 미완료)"
        if source_scope == "captured_history_periodic_reports"
        else "제공 공시 내 선택·개발용(전수/최신정정 미확인)"
        if result.request_run
        else "지정 공시 1건·개발용(전수/최신정정 미확인)"
    )
    _text(
        sheet,
        1,
        1,
        f"{day} 조회 | {requested}{minimum}억원 이상 | {scope_note}",
    )
    value = result.value
    if result.status == "document_match" and isinstance(value, CashValue):
        _write_match_row(sheet, 3, result.disclosure.corp_name, result)
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
    _save_cash_sheet(book, sheet, output, wrap_header=result.request_run is not None)


def _new_cash_sheet(title: str) -> tuple[Workbook, Worksheet]:
    book = Workbook()
    sheet = book.active
    if not isinstance(sheet, Worksheet):
        raise ValueError("workbook_sheet_unavailable")
    sheet.title = title
    sheet.merge_cells("A1:C1")
    for column, title in enumerate(("법인명", "현금및현금성자산(억원)", "조회 기준"), 1):
        _text(sheet, 2, column, title)
    return book, sheet


def _write_match_row(
    sheet: Worksheet, row_index: int, display_name: str, result: CashReportResult
) -> None:
    value = result.value
    if result.status != "document_match" or not isinstance(value, CashValue):
        raise ValueError("confirmed_cash_match_required")
    amount = _numeric_eok(value.amount_krw)
    _text(sheet, row_index, 1, display_name)
    if result.viewer_link is not None and result.viewer_link.value != value:
        raise ValueError("viewer_link_value_mismatch")
    target = result.viewer_link.url if result.viewer_link else value.evidence.source_url
    sheet.cell(row_index, 1).hyperlink = Hyperlink(ref=f"A{row_index}", target=target)
    sheet.cell(row_index, 2, amount)
    # Display rounding never participates in condition comparison.
    sheet.cell(row_index, 2).number_format = "#,##0.00"
    basis = {
        "separate": "법인 자체(별도)",
        "individual": "법인 자체(개별)",
        "consolidated": "그룹 전체(연결)",
    }[value.basis]
    prior = (
        " · 이전 자료"
        if result.request_run and value.as_of < result.request_run.anchor_date
        else ""
    )
    _text(sheet, row_index, 3, f"{value.as_of:%Y.%m.%d} · {basis}{prior}")
    sheet.cell(row_index, 2).comment = Comment(
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


def _style_cash_sheet(sheet: Worksheet, *, wrap_header: bool) -> None:
    sheet.column_dimensions["A"].width = 22
    sheet.column_dimensions["B"].width = 24
    sheet.column_dimensions["C"].width = 45
    sheet.freeze_panes = "A3"
    sheet.sheet_view.showGridLines = True
    sheet.sheet_format.defaultRowHeight = 15
    sheet.print_area = f"A1:C{max(3, sheet.max_row)}"
    for row in sheet:
        for cell in row:
            cell.font = Font(name="맑은 고딕", size=10, color="000000", bold=cell.row in (1, 2))
            cell.alignment = Alignment(horizontal="left", vertical="center")
    if wrap_header:
        sheet.cell(1, 1).alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        sheet.row_dimensions[1].height = 30
    for row_index in range(3, sheet.max_row + 1):
        if sheet.cell(row_index, 1).hyperlink is not None:
            sheet.cell(row_index, 1).font = Font(
                name="맑은 고딕", size=10, color="0563C1", underline="single"
            )


def _save_cash_sheet(book: Workbook, sheet: Worksheet, output: Path, *, wrap_header: bool) -> None:
    _style_cash_sheet(sheet, wrap_header=wrap_header)
    for other in book.worksheets:
        if other is not sheet:
            _style_cash_sheet(other, wrap_header=True)
    buffer = io.BytesIO()
    book.save(buffer)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(buffer.getvalue())


def write_cash_matches_workbook(
    rows: tuple[tuple[str, CashReportResult], ...],
    output: Path,
    *,
    run: QueryRun,
    minimum_krw: Decimal,
    summary: str,
    review_rows: tuple[tuple[str, str, str], ...] | None = None,
) -> None:
    """Render confirmed rows; the survey layer supplies counts, never unknown financial values."""
    if output.suffix.lower() != ".xlsx":
        raise ValueError("xlsx_output_required")
    if not isinstance(minimum_krw, Decimal) or not minimum_krw.is_finite() or minimum_krw < 0:
        raise ValueError("nonnegative_exact_minimum_required")
    seen: set[str] = set()
    book, sheet = _new_cash_sheet("현금 조건 조회")
    minimum = format(_eok(minimum_krw), ",f")
    if "." in minimum:
        minimum = minimum.rstrip("0").rstrip(".")
    _text(
        sheet,
        1,
        1,
        f"{run.execution_date} 조회 | 기준 {run.anchor_date} | {minimum}억원 이상\n{summary}",
    )
    for row_index, (name, report) in enumerate(rows, 3):
        report = replace(report)
        if (
            report.request_run != run
            or report.minimum_krw != minimum_krw
            or report.disclosure.corp_code in seen
            or not name.strip()
        ):
            raise ValueError("cash_workbook_row_request_mismatch")
        seen.add(report.disclosure.corp_code)
        _write_match_row(sheet, row_index, name, report)
    if rows:
        sheet.auto_filter.ref = f"A2:C{len(rows) + 2}"
    else:
        sheet.merge_cells("A3:C3")
        _text(
            sheet,
            3,
            1,
            "확인된 조건 충족 법인이 없습니다. 처리 범위는 상단과 내부 기록을 확인하세요.",
        )
    if review_rows is not None:
        review = book.create_sheet("확인 내역")
        review.merge_cells("A1:C1")
        _text(review, 1, 1, "확인 필요·미처리 내역입니다. 조건 미충족이나 0원을 뜻하지 않습니다.")
        for column, title in enumerate(("법인명", "상태", "사유"), 1):
            _text(review, 2, column, title)
        for row_index, values in enumerate(review_rows, 3):
            for column, text in enumerate(values, 1):
                _text(review, row_index, column, text)
        if review_rows:
            review.auto_filter.ref = f"A2:C{len(review_rows) + 2}"
        else:
            review.merge_cells("A3:C3")
            _text(review, 3, 1, "추가 확인이 필요한 법인이 없습니다.")
    _save_cash_sheet(book, sheet, output, wrap_header=True)
