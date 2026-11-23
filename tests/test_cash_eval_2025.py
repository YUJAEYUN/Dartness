"""Held-out DART 2025 annual reports (issue #31): provenance and the no-wrong-amount guarantee.

Answers were read from the originals before the extractor ran and matched OpenDART figures.
These tests do not fix how many cases succeed, so improving the extractor keeps them green.
"""

import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from dartness.amounts import AmountInput, NormalizedAmount, normalize_krw_amount
from dartness.cash_contract import CashEvidence, CashNeedsReview, CashQuery, CashValue
from dartness.cash_table import extract_cash_table

FOLDER = Path(__file__).parent / "fixtures/cash/dart-2025-eval"
RECORD = json.loads((FOLDER / "cases.json").read_text())
CASES: list[dict[str, Any]] = RECORD["cases"]


def section(case: dict[str, Any]) -> str:
    return (FOLDER / str(case["section_file"])).read_text()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_recorded_answer_matches_source_text_and_api(case: dict[str, Any]) -> None:
    data = (FOLDER / case["section_file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == case["section_sha256"]
    expected = case["expected"]
    html = data.decode()
    assert expected["raw_value"] in html and f"(단위 : {expected['unit']})" in html
    normalized = normalize_krw_amount(AmountInput(expected["raw_value"], expected["unit"]))
    assert isinstance(normalized, NormalizedAmount)
    assert normalized.amount_krw == Decimal(expected["amount_krw"])
    assert Decimal(case["api_cross_check"]["thstrm_amount"]) == normalized.amount_krw


CONDITIONS: dict[str, Callable[[str], str]] = {
    "original": lambda html: html,
    # Modified input: only DART's <TE> cell tag is renamed, to separate format support
    # from other failure causes. Not a claim that the original can be read this way.
    "te-renamed": lambda html: re.sub(r"(</?)TE\b", r"\1TD", html),
}


@pytest.mark.parametrize("condition", sorted(CONDITIONS))
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_extractor_never_returns_a_wrong_amount(case: dict[str, Any], condition: str) -> None:
    evidence = CashEvidence(
        case["source_url"], case["document_sha256"], case["section_locator"], "DART 원문 XML"
    )
    query = CashQuery(case["corp_code"], date.fromisoformat(case["as_of"]), case["scope"])
    html = CONDITIONS[condition](section(case))
    result = extract_cash_table(
        query, html, case["basis"], evidence, datetime(2026, 11, 23, tzinfo=UTC)
    )
    if isinstance(result, CashValue):
        assert result.amount_krw == Decimal(case["expected"]["amount_krw"])
        assert result.basis == case["basis"] and result.as_of == query.as_of
    else:
        assert isinstance(result, CashNeedsReview) and not hasattr(result, "amount_krw")
