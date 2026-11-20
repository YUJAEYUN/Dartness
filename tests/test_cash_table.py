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
    }
    assert changes[kind] != html
    return changes[kind]


@pytest.mark.parametrize(
    "kind",
    [
        "missing_unit",
        "missing_periods",
        "unsupported_unit",
        "dash",
        "duplicate_cash",
        "missing_cash",
        "merged_cell",
        "nested_table",
        "unclosed_table",
        "duplicate_header",
        "duplicate_context",
        "invalid_date",
        "extra_table",
        "oversized",
    ],
)
def test_ambiguous_or_unsupported_input_does_not_produce_money(kind: str) -> None:
    result = extract_cash_table(
        CashQuery("00359395", date(2025, 12, 31)),
        modified(kind),
        "separate",
        evidence(),
        CHECKED_AT,
    )
    assert isinstance(result, CashNeedsReview)
    assert result.reason == "extraction_failed" and result.detail
    assert result.next_action and result.checked_at == CHECKED_AT
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
