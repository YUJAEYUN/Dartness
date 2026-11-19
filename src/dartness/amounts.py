"""Normalize explicitly identified KRW units; never infer missing units."""

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

# A unit represents a power of ten in KRW, not a currency conversion rate.
_KRW_EXPONENTS = {"원": 0, "천원": 3, "백만원": 6, "억원": 8}
_NUMBER = re.compile(r"[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?")


@dataclass(frozen=True)
class AmountInput:
    raw_value: str
    unit: str | None


@dataclass(frozen=True)
class NormalizedAmount:
    source: AmountInput
    amount_krw: Decimal
    status: Literal["normalized"] = field(default="normalized", init=False)


@dataclass(frozen=True)
class AmountNeedsReview:
    source: AmountInput
    reason: Literal["missing_unit", "unsupported_unit", "invalid_number"]
    status: Literal["needs_review"] = field(default="needs_review", init=False)


type AmountResult = NormalizedAmount | AmountNeedsReview


def normalize_krw_amount(source: AmountInput) -> AmountResult:
    """Return an exact KRW value or an explicit review reason with the source intact.

    The caller must identify the applicable unit from the disclosure first.
    A normalized result does not establish that extraction or evidence is correct.
    """
    unit = source.unit.strip() if source.unit is not None else ""
    if not unit:
        return AmountNeedsReview(source, "missing_unit")
    exponent = _KRW_EXPONENTS.get(unit)
    if exponent is None:
        return AmountNeedsReview(source, "unsupported_unit")
    raw_value = source.raw_value.strip()
    if _NUMBER.fullmatch(raw_value) is None:
        return AmountNeedsReview(source, "invalid_number")
    value = Decimal(raw_value.replace(",", ""))
    # Tuple construction shifts the decimal point without context rounding.
    parts = value.as_tuple()
    assert isinstance(parts.exponent, int)  # Grammar excludes infinity and NaN.
    amount_krw = Decimal((parts.sign, parts.digits, parts.exponent + exponent))
    return NormalizedAmount(source, amount_krw)
