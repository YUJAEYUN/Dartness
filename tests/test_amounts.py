import json
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from dartness.amounts import AmountInput, AmountNeedsReview, NormalizedAmount, normalize_krw_amount


@pytest.mark.parametrize(
    ("raw", "unit", "expected"),
    [
        ("560", "억원", "56000000000"),
        ("56,000,000", "천원", "56000000000"),
        ("56,000", "백만원", "56000000000"),
        ("56,000,000,000", "원", "56000000000"),
        ("0.125", "백만원", "125000"),
        ("-2.5", "천원", "-2500"),
        ("+1,234.50", "원", "1234.50"),
        ("0", "억원", "0"),
        (" 560 ", " 억원 ", "56000000000"),
    ],
)
def test_known_units_convert_exactly_and_preserve_source(
    raw: str, unit: str, expected: str
) -> None:
    source = AmountInput(raw, unit)
    result = normalize_krw_amount(source)
    assert isinstance(result, NormalizedAmount)
    assert result.status == "normalized"
    assert result.amount_krw == Decimal(expected)
    assert result.source == source


@pytest.mark.parametrize("unit", [None, "", " ", "USD", "천USD", "단위: 천원", "만원"])
def test_missing_or_unsupported_unit_never_produces_an_amount(unit: str | None) -> None:
    source = AmountInput("560", unit)
    result = normalize_krw_amount(source)
    assert isinstance(result, AmountNeedsReview)
    assert result.status == "needs_review"
    assert result.reason == (
        "missing_unit" if unit is None or not unit.strip() else "unsupported_unit"
    )
    assert result.source == source
    assert not hasattr(result, "amount_krw")


@pytest.mark.parametrize(
    "raw", ["", "-", "1,23", "12,34,567", "(560)", "1e3", "NaN", "Infinity", "５６０", "560원"]
)
def test_invalid_numbers_are_not_treated_as_zero(raw: str) -> None:
    result = normalize_krw_amount(AmountInput(raw, "천원"))
    assert isinstance(result, AmountNeedsReview)
    assert result.reason == "invalid_number"


def test_conversion_does_not_round_under_a_small_decimal_context() -> None:
    with localcontext() as context:
        context.prec = 3
        result = normalize_krw_amount(AmountInput("123456789012345678901234567890.125", "천원"))
    assert isinstance(result, NormalizedAmount)
    assert result.amount_krw == Decimal("123456789012345678901234567890125")


def test_documented_examples_match_actual_behavior() -> None:
    document = (Path(__file__).parents[1] / "docs" / "amounts.md").read_text()
    example = document.split("```json\n", 1)[1].split("```", 1)[0]
    rows: list[dict[str, str | None]] = json.loads(example)
    assert len(rows) >= 6
    for row in rows:
        raw = row["raw_value"]
        unit = row["unit"]
        assert isinstance(raw, str)
        assert unit is None or isinstance(unit, str)
        result = normalize_krw_amount(AmountInput(raw, unit))
        if "expected_krw" in row:
            expected = row["expected_krw"]
            assert isinstance(expected, str)
            assert isinstance(result, NormalizedAmount)
            assert result.amount_krw == Decimal(expected)
        else:
            assert isinstance(result, AmountNeedsReview)
            assert result.reason == row["expected_reason"]
