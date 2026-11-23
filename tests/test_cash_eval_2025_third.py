"""Non-December fiscal year evaluation for issue #58: three companies not used in development.

Answers were read from the originals and committed before the extractor ran. 신영증권 has only
현금및예치금 on the balance sheet; the two Japanese-listed companies report in JPY, which the
KRW-only amount rules do not interpret (docs/amounts.md). Every answer is needs_review, so a
KRW amount from any of these sections is a wrong answer.
"""

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from dartness.cash_contract import CashEvidence, CashNeedsReview, CashQuery, CashValue
from dartness.cash_table import extract_cash_table

FOLDER = Path(__file__).parent / "fixtures/cash/dart-2025-eval-3"
CASES: list[dict[str, Any]] = json.loads((FOLDER / "cases.json").read_text())["cases"]


def run(case: dict[str, Any]) -> CashValue | CashNeedsReview:
    evidence = CashEvidence(
        case["source_url"], case["document_sha256"], case["section_locator"], "DART 원문 XML"
    )
    query = CashQuery(case["corp_code"], date.fromisoformat(case["as_of"]), case["scope"])
    html = (FOLDER / case["section_file"]).read_text()
    return extract_cash_table(
        query, html, case["basis"], evidence, datetime(2026, 11, 23, tzinfo=UTC)
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_section_hash_and_non_december_period_match_record(case: dict[str, Any]) -> None:
    data = (FOLDER / case["section_file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == case["section_sha256"]
    assert case["fiscal_month"] != "12"
    assert f"{case['as_of'].replace('-', '.')} 현재" in data.decode()
    assert case["report_name"] == f"사업보고서 ({case['as_of'][:7].replace('-', '.')})"


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_recorded_reason_for_review_is_in_the_source(case: dict[str, Any]) -> None:
    html = (FOLDER / case["section_file"]).read_text()
    if "foreign_currency_cash_row" in case:
        row = case["foreign_currency_cash_row"]
        assert f"(단위 : {row['unit']})" in html and row["raw_value"] in html
    else:
        row = case["balance_sheet_row_not_cash"]
        assert f"{row['label']}<" in html and row["raw_value"] in html
        assert "현금및현금성자산" not in html.replace(" ", "")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_no_krw_amount_is_returned(case: dict[str, Any]) -> None:
    # CASH-002 and docs/amounts.md: no substitute row, no JPY figure read as KRW.
    result = run(case)
    assert isinstance(result, CashNeedsReview) and not hasattr(result, "amount_krw")
    assert result.reason == case["expected"]["reason"]
