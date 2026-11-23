"""Source-backed development extraction and explicitly modified failure cases."""

import hashlib
import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from doc_examples import DocExample, check_example, load_examples

from dartness.cash_contract import (
    CashBasis,
    CashEvidence,
    CashNeedsReview,
    CashQuery,
    CashResult,
    CashScope,
    CashValue,
)
from dartness.cash_table import extract_cash_table

FOLDER = Path(__file__).parent / "fixtures/cash/helixmith-2025"
MANIFEST = json.loads((FOLDER / "balance-sections.json").read_text())
SOURCE = json.loads((FOLDER / "expected-draft.json").read_text())
CHECKED_AT = datetime(2026, 11, 20, tzinfo=UTC)


def section(basis: str = "separate") -> str:
    path = FOLDER / str(MANIFEST[basis]["file"])
    return path.read_text()


def evidence() -> CashEvidence:
    return CashEvidence(
        SOURCE["source_url"],
        SOURCE["source_sha256"],
        "III. 재무에 관한 사항 / 선택한 재무상태표 구간",
        "원문에서 선정한 개발용 구간",
    )


@pytest.mark.parametrize(
    "basis,expected",
    [
        ("separate", "31653154838"),
        ("consolidated", "31827123947"),
    ],
)
def test_real_development_sections(basis: CashBasis, expected: str) -> None:
    data = (FOLDER / MANIFEST[basis]["file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == MANIFEST[basis]["sha256"]
    assert MANIFEST[basis]["full_source_sha256"] == SOURCE["source_sha256"]
    query = CashQuery(
        "00359395", date(2025, 12, 31), "consolidated" if basis == "consolidated" else "standalone"
    )
    result = extract_cash_table(query, data.decode(), basis, evidence(), CHECKED_AT)
    assert isinstance(result, CashValue)
    assert result.amount_krw == Decimal(expected)
    assert result.basis == basis and result.as_of == query.as_of
    assert result.raw_amount.unit == "원"
    assert result.evidence.locator.endswith("table[2]/tr[4]/td[2]")
    assert "2025.12.31" in result.evidence.context
    assert result.evidence.document_sha256 == SOURCE["source_sha256"]


def test_requested_previous_period_is_not_first_numeric_cell() -> None:
    # Original source has 2024 and 2023 as well as 2025; no document mutation.
    query = CashQuery("00359395", date(2024, 12, 31), "consolidated")
    result = extract_cash_table(
        query, section("consolidated"), "consolidated", evidence(), CHECKED_AT
    )
    assert isinstance(result, CashValue)
    assert result.amount_krw == Decimal("36840718479")
    assert result.evidence.locator.endswith("td[3]")
    assert result.as_of == date(2024, 12, 31)


@pytest.mark.parametrize(
    "scope,basis,reason",
    [
        ("standalone", "consolidated", "basis_unavailable"),
        ("consolidated", "separate", "basis_unavailable"),
    ],
)
def test_never_substitutes_other_basis(scope: CashScope, basis: CashBasis, reason: str) -> None:
    query = CashQuery("00359395", date(2025, 12, 31), scope)
    result = extract_cash_table(query, section(basis), basis, evidence(), CHECKED_AT)
    assert isinstance(result, CashNeedsReview) and result.reason == reason
    assert not hasattr(result, "amount_krw")


def test_requested_date_missing_is_not_previous_value() -> None:
    query = CashQuery("00359395", date(2026, 12, 31))
    result = extract_cash_table(query, section(), "separate", evidence(), CHECKED_AT)
    assert isinstance(result, CashNeedsReview) and result.reason == "period_unavailable"
    assert not hasattr(result, "amount_krw")


def modified(kind: str) -> str:
    # All mutations are test inputs; the source fixtures remain byte-for-byte unchanged.
    html = section()
    row = re.search(r"<TR>\s*<TD[^>]*>\s*현금및현금성자산</TD>.*?</TR>", html, re.DOTALL)
    assert row is not None
    first_table = re.compile(r"<TABLE.*?</TABLE>", re.DOTALL)
    short_row = re.sub(r"<TD[^>]*>[^<]*</TD>\s*</TR>", "</TR>", row[0])
    changes = {
        "missing_unit": html.replace("(단위 : 원)", ""),
        "missing_periods": html.replace(" 현재", " 시점미확인"),
        "unsupported_unit": html.replace("(단위 : 원)", "(단위 : USD)"),
        "dash": html.replace("31,653,154,838", "-"),
        "duplicate_cash": html.replace(row[0], row[0] + row[0]),
        "missing_cash": html.replace("현금및현금성자산", "다른항목"),
        "merged_cell": html.replace("<TH ", '<TH colspan="2" ', 1),
        "nested_table": html.replace("<TH ", "<TABLE><TH ", 1),
        "unclosed_table": html.rsplit("</TABLE>", 1)[0],
        "duplicate_header": html.replace(">제 29 기</TH>", ">제 30 기</TH>"),
        "duplicate_context": html.replace("2024.12.31", "2025.12.31"),
        "invalid_date": html.replace("2025.12.31", "2025.02.31"),
        "extra_table": html + "<TABLE></TABLE>",
        "oversized": html + " " * (256 * 1024),
        # Added after mutation testing (issue #41): each targets one guard.
        "script": html.replace("<TABLE", "<SCRIPT></SCRIPT><TABLE", 1),
        "duplicate_period_name": html.replace("제 29 기", "제 30 기", 1),
        "empty_context_table": first_table.sub("<TABLE></TABLE>", html, count=1),
        "empty_amount_table": html[: html.rindex("<TABLE")] + "<TABLE></TABLE>",
        "short_cash_row": html.replace(row[0], short_row),
        "style": html.replace("<TABLE", "<STYLE></STYLE><TABLE", 1),
        "rowspan": html.replace("<TH ", '<TH rowspan="2" ', 1),
        "row_outside_table": html.replace("<TABLE", "<TR></TR><TABLE", 1),
        "cell_outside_row": html.replace("<TR>", "", 1),
        "mismatched_cell_end": html.replace("</TD>", "</TH>", 1),
        "row_end_inside_cell": html.replace("</TD>", "", 1),
        "table_end_inside_row": html[: html.rindex("</TR>")] + html[html.rindex("</TR>") + 5 :],
        "duplicate_cell_end": html.replace("</TD>", "</TD></TD>", 1),
        "duplicate_row_end": html.replace("</TR>", "</TR></TR>", 1),
        # Current behavior: a labeled corner cell (e.g. "과목") is rejected, not ignored.
        "labeled_header_corner": html.replace(">　</TH>", ">과목</TH>", 1),
    }
    assert changes[kind] != html
    return changes[kind]


# The detail names the guard that fired, so a later guard cannot hide a broken earlier one.
FAILURES = {
    "missing_unit": "단일 적용 단위",
    "missing_periods": "명시한 기간",
    "unsupported_unit": "현금 금액이나 적용 단위",
    "dash": "현금 금액이나 적용 단위",
    "duplicate_cash": "현금 행이 없거나 중복",
    "missing_cash": "현금 행이 없거나 중복",
    "merged_cell": "병합 셀",
    "nested_table": "중첩 표",
    "unclosed_table": "완전한 기간·단위 표와 금액 표",
    "duplicate_header": "머리글 구조가 모호하거나 중복",
    "duplicate_context": "기간이나 머리글이 모호",
    "invalid_date": "day is out of range",
    "extra_table": "두 개를 넘는 표",
    "oversized": "구간 크기",
    "script": "실행 코드",
    "duplicate_period_name": "기간 이름이 중복",
    "empty_context_table": "표 제목",
    "empty_amount_table": "기간이나 머리글이 모호",
    "short_cash_row": "현금 행과 머리글의 열 구조",
    "style": "실행 코드·스타일",
    "rowspan": "병합 셀",
    "row_outside_table": "행의 경계",
    "cell_outside_row": "셀의 경계",
    "mismatched_cell_end": "셀의 끝",
    "row_end_inside_cell": "행의 끝",
    "table_end_inside_row": "표의 끝",
    "labeled_header_corner": "머리글 구조가 모호하거나 중복",
    "duplicate_cell_end": "셀의 끝",
    "duplicate_row_end": "행의 끝",
}


@pytest.mark.parametrize("kind", sorted(FAILURES))
def test_ambiguous_or_unsupported_input_does_not_produce_money(kind: str) -> None:
    result = extract_cash_table(
        CashQuery("00359395", date(2025, 12, 31)),
        modified(kind),
        "separate",
        evidence(),
        CHECKED_AT,
    )
    assert isinstance(result, CashNeedsReview)
    assert result.reason == "extraction_failed"
    assert FAILURES[kind] in result.detail, result.detail
    assert result.next_action and result.checked_at == CHECKED_AT
    assert result.evidence == evidence() and result.checked_path == evidence().locator
    assert not hasattr(result, "amount_krw")


def test_supported_unit_is_applied_without_changing_the_raw_value() -> None:
    # Synthetic unit change, not an actual corporate disclosure or a plausible cash balance.
    html = section().replace("(단위 : 원)", "(단위 : 천원)")
    result = extract_cash_table(
        CashQuery("00359395", date(2025, 12, 31)),
        html,
        "separate",
        evidence(),
        CHECKED_AT,
    )
    assert isinstance(result, CashValue)
    assert result.raw_amount.raw_value == "31,653,154,838"
    assert result.raw_amount.unit == "천원"
    assert result.amount_krw == Decimal("31653154838000")


def run_documented_case(data: dict[str, Any]) -> CashResult:
    basis: CashBasis = data["section"]
    html = section(basis)
    if data.get("remove_unit"):
        html = html.replace("(단위 : 원)", "")
    query = CashQuery("00359395", date.fromisoformat(data["as_of"]), data["scope"])
    return extract_cash_table(query, html, basis, evidence(), CHECKED_AT)


@pytest.mark.parametrize("example", load_examples("cash-table"), ids=lambda example: example.id)
def test_documented_extraction_examples(example: DocExample) -> None:
    check_example(example, run_documented_case)


def test_supplied_basis_cannot_override_the_printed_consolidated_title() -> None:
    result = extract_cash_table(
        CashQuery("00359395", date(2025, 12, 31)),
        section("consolidated"),
        "separate",
        evidence(),
        CHECKED_AT,
    )
    assert isinstance(result, CashNeedsReview)
    assert result.reason == "extraction_failed" and "표 제목" in result.detail


def test_check_time_must_include_timezone_even_on_success_path() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        extract_cash_table(
            CashQuery("00359395", date(2025, 12, 31)),
            section(),
            "separate",
            evidence(),
            datetime(2026, 11, 20),
        )


def test_repeated_header_cannot_redefine_the_column_mapping() -> None:
    html = section()
    header = re.search(r"<TR>\s*<TH[^>]*>.*?</TR>", html, re.DOTALL)
    assert header is not None
    # Modified source: a second header may change the meaning of subsequent columns.
    html = html.replace(header[0], header[0] + header[0])
    result = extract_cash_table(
        CashQuery("00359395", date(2025, 12, 31)),
        html,
        "separate",
        evidence(),
        CHECKED_AT,
    )
    assert isinstance(result, CashNeedsReview)
    assert result.reason == "extraction_failed" and "여러 머리글" in result.detail


def test_header_labels_must_all_be_stated_periods() -> None:
    # Modified source: the current-period header no longer matches any stated period,
    # even though the requested earlier period still has its own column.
    html = section().replace(">제 30 기</TH>", ">제 99 기</TH>")
    query = CashQuery("00359395", date(2024, 12, 31))
    result = extract_cash_table(query, html, "separate", evidence(), CHECKED_AT)
    assert isinstance(result, CashNeedsReview)
    assert "기간과 머리글 열을 대응" in result.detail


def test_value_evidence_records_the_selected_cell_and_its_context() -> None:
    query = CashQuery("00359395", date(2025, 12, 31))
    result = extract_cash_table(query, section(), "separate", evidence(), CHECKED_AT)
    assert isinstance(result, CashValue)
    assert result.evidence.locator.startswith(evidence().locator + " / table[2]/tr[")
    assert result.evidence.locator.endswith("]/td[2]")
    assert "재무상태표\n" in result.evidence.context
    assert "(단위 : 원)" in result.evidence.context
    assert result.evidence.context.endswith("입력 범위: separate; 선택 열: 제 30 기")


def test_individual_statements_are_accepted_for_standalone_requests() -> None:
    # Modified input: the separate section is passed as an individual statement.
    query = CashQuery("00359395", date(2025, 12, 31))
    result = extract_cash_table(query, section(), "individual", evidence(), CHECKED_AT)
    assert isinstance(result, CashValue) and result.basis == "individual"


@pytest.mark.parametrize(
    "label",
    ["<SPAN>현금및</SPAN>현금성자산", "현금&#48143;현금성자산"],
    ids=["inline-tag", "character-reference"],
)
def test_cell_text_joins_fragments_and_decodes_references(label: str) -> None:
    # Modified input: the label is split by markup that HTML allows inside a cell.
    html = section().replace(">　　현금및현금성자산</TD>", f">　　{label}</TD>")
    query = CashQuery("00359395", date(2025, 12, 31))
    result = extract_cash_table(query, html, "separate", evidence(), CHECKED_AT)
    assert isinstance(result, CashValue) and result.amount_krw == Decimal("31653154838")


@pytest.mark.parametrize("extra,accepted", [(0, True), (1, False)])
def test_section_size_limit_is_inclusive(extra: int, accepted: bool) -> None:
    html = section()
    html += " " * (256 * 1024 - len(html.encode("utf-8")) + extra)
    query = CashQuery("00359395", date(2025, 12, 31))
    result = extract_cash_table(query, html, "separate", evidence(), CHECKED_AT)
    assert isinstance(result, CashValue) is accepted
    if not accepted:
        assert isinstance(result, CashNeedsReview) and "구간 크기" in result.detail


def test_explicit_single_span_is_not_a_merged_cell() -> None:
    html = section().replace("<TH ", '<TH colspan="1" rowspan="1" ', 1)
    query = CashQuery("00359395", date(2025, 12, 31))
    result = extract_cash_table(query, html, "separate", evidence(), CHECKED_AT)
    assert isinstance(result, CashValue)


def test_amount_table_with_only_the_requested_period_column() -> None:
    # Modified input: drop the two earlier-period columns from every amount-table row.
    html = section()
    start = html.rindex("<TABLE")
    amounts = re.sub(
        r"(<T[HD][^>]*>[^<]*</T[HD]>)\s*<T[HD][^>]*>[^<]*</T[HD]>\s*<T[HD][^>]*>[^<]*</T[HD]>\s*</TR>",
        r"\1</TR>",
        html[start:],
    )
    query = CashQuery("00359395", date(2025, 12, 31))
    result = extract_cash_table(query, html[:start] + amounts, "separate", evidence(), CHECKED_AT)
    assert isinstance(result, CashValue) and result.amount_krw == Decimal("31653154838")
    assert result.evidence.locator.endswith("]/td[2]")


def test_dart_document_cells_are_read_like_html_cells() -> None:
    # Modified input: DART document XML writes body cells as <TE> (issue #31 evaluation).
    html = re.sub(r"(</?)TD\b", r"\1TE", section())
    query = CashQuery("00359395", date(2025, 12, 31))
    result = extract_cash_table(query, html, "separate", evidence(), CHECKED_AT)
    assert isinstance(result, CashValue) and result.amount_krw == Decimal("31653154838")


@pytest.mark.parametrize("label", ["현금및현금성자산 (주4,29)", "현금및현금성자산(주5)"])
def test_cash_label_may_carry_note_references(label: str) -> None:
    html = section().replace(">　　현금및현금성자산</TD>", f">　　{label}</TD>")
    query = CashQuery("00359395", date(2025, 12, 31))
    result = extract_cash_table(query, html, "separate", evidence(), CHECKED_AT)
    assert isinstance(result, CashValue) and result.amount_krw == Decimal("31653154838")


@pytest.mark.parametrize(
    "label",
    [
        "(5)현금및현금성자산",
        "(12) 현금및현금성자산",
        "1.현금및현금성자산",
        "Ⅴ. 현금및현금성자산",
        "가.현금및현금성자산",
        "①현금및현금성자산",
        "(a)현금및현금성자산",
        "(5)1.현금및현금성자산",
        "(5)현금및현금성자산 (주4)",
    ],
)
def test_cash_label_may_carry_leading_outline_markers(label: str) -> None:
    # Issue #56: e.g. "(5)현금및현금성자산" in the 대한약품 2025 annual report.
    html = section().replace(">　　현금및현금성자산</TD>", f">　　{label}</TD>")
    query = CashQuery("00359395", date(2025, 12, 31))
    result = extract_cash_table(query, html, "separate", evidence(), CHECKED_AT)
    assert isinstance(result, CashValue) and result.amount_krw == Decimal("31653154838")


@pytest.mark.parametrize(
    "label",
    [
        "현금및현금성자산 (주)",
        "현금및현금성자산 등",
        "현금및현금성자산 (주4) 외",
        "(주4)현금및현금성자산",
        "(주)현금및현금성자산",
        "5현금및현금성자산",
        "().현금및현금성자산",
        "제한된 현금및현금성자산",
        "(5)제한된 현금및현금성자산",
    ],
)
def test_other_labels_are_not_treated_as_cash(label: str) -> None:
    html = section().replace(">　　현금및현금성자산</TD>", f">　　{label}</TD>")
    query = CashQuery("00359395", date(2025, 12, 31))
    result = extract_cash_table(query, html, "separate", evidence(), CHECKED_AT)
    assert isinstance(result, CashNeedsReview) and "현금 행이 없거나 중복" in result.detail
