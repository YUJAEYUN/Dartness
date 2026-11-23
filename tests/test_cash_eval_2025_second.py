"""Second DART 2025 evaluation for issue #31: five companies not used in development.

Answers were read from the originals and committed before the extractor ran. The extractor
was not changed for these cases. Financial companies have no cash-and-cash-equivalents row
on the balance sheet, so the source-derived answer is needs_review, never another row.

The test fixes provenance and "no wrong amount". It does not fix how many cases extract,
so improving the extractor later does not break it.
"""

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from dartness.amounts import AmountInput, NormalizedAmount, normalize_krw_amount
from dartness.cash_contract import CashEvidence, CashNeedsReview, CashQuery, CashValue
from dartness.cash_table import extract_cash_table

FOLDER = Path(__file__).parent / "fixtures/cash/dart-2025-eval-2"
CASES: list[dict[str, Any]] = json.loads((FOLDER / "cases.json").read_text())["cases"]
VALUE_CASES = [case for case in CASES if case["expected"]["outcome"] == "value"]
REVIEW_CASES = [case for case in CASES if case["expected"]["outcome"] == "needs_review"]


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
def test_section_hash_and_period_match_record(case: dict[str, Any]) -> None:
    data = (FOLDER / case["section_file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == case["section_sha256"]
    assert "2025.12.31 현재" in data.decode()


@pytest.mark.parametrize("case", VALUE_CASES, ids=lambda case: case["id"])
def test_value_answer_matches_source_text_and_api(case: dict[str, Any]) -> None:
    expected = case["expected"]
    html = (FOLDER / case["section_file"]).read_text()
    assert f">{expected['label']}<" in html and expected["raw_value"] in html
    assert f"(단위 : {expected['unit']})" in html
    normalized = normalize_krw_amount(AmountInput(expected["raw_value"], expected["unit"]))
    assert isinstance(normalized, NormalizedAmount)
    assert normalized.amount_krw == Decimal(expected["amount_krw"])
    assert Decimal(case["api_cross_check"]["thstrm_amount"]) == normalized.amount_krw


@pytest.mark.parametrize("case", REVIEW_CASES, ids=lambda case: case["id"])
def test_review_answer_has_no_cash_row_in_source(case: dict[str, Any]) -> None:
    html = (FOLDER / case["section_file"]).read_text()
    other = case["balance_sheet_row_not_cash"]
    assert f"{other['label']}<" in html and other["raw_value"] in html
    assert "현금및현금성자산" not in html.replace(" ", "")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_extractor_never_returns_a_wrong_amount(case: dict[str, Any]) -> None:
    result = run(case)
    if isinstance(result, CashValue):
        assert case["expected"]["outcome"] == "value"
        assert result.amount_krw == Decimal(case["expected"]["amount_krw"])
    else:
        assert isinstance(result, CashNeedsReview) and not hasattr(result, "amount_krw")


@pytest.mark.parametrize("case", REVIEW_CASES, ids=lambda case: case["id"])
def test_cash_and_due_from_banks_is_not_used_as_cash(case: dict[str, Any]) -> None:
    # CASH-002: an amount that could not be confirmed is never filled with another figure.
    result = run(case)
    assert isinstance(result, CashNeedsReview)
    assert result.reason == case["expected"]["reason"]
