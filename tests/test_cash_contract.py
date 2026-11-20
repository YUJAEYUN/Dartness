"""Contract checks using source-derived development values and synthetic invalid inputs."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from dartness.amounts import AmountInput
from dartness.cash_contract import (
    CashBasis,
    CashEvidence,
    CashNeedsReview,
    CashQuery,
    CashValue,
    ReviewReason,
)

# Casts below deliberately bypass static types to test invalid runtime inputs.
FIXTURE = Path(__file__).parent / "fixtures/cash/helixmith-2025/expected-draft.json"
SOURCE = json.loads(FIXTURE.read_text())


def evidence() -> CashEvidence:
    expected = SOURCE["expected"]["balance_sheet"]
    return CashEvidence(
        SOURCE["source_url"],
        SOURCE["source_sha256"],
        f"{expected['section']} / {expected['row']} / {expected['column']}",
        "제30기 2025.12.31 현재, 연결 재무상태표, 단위: 원",
    )


def value() -> CashValue:
    original = SOURCE["expected"]["balance_sheet"]
    return CashValue(
        CashQuery("00359395", date(2025, 12, 31), "consolidated"),
        "consolidated",
        date(2025, 12, 31),
        AmountInput(original["raw_value"], original["unit"]),
        Decimal(original["krw"]),
        evidence(),
    )


def test_source_derived_consolidated_contract() -> None:
    result = value()
    assert result.amount_krw == Decimal("31827123947")
    assert result.query.scope == "consolidated"
    assert result.query.contract_version == "cash-v1"
    assert result.evidence.document_sha256 == SOURCE["source_sha256"]


def test_default_scope_refuses_consolidated_substitution() -> None:
    query = CashQuery("00359395", date(2025, 12, 31))
    assert query.scope == "standalone"
    with pytest.raises(ValueError, match="basis"):
        replace(value(), query=query)


@pytest.mark.parametrize("basis", ["separate", "individual"])
def test_standalone_accepts_both_legal_statement_forms(basis: CashBasis) -> None:
    # Synthetic: these are boundary examples, not separate or individual source evidence.
    result = replace(value(), query=CashQuery("00359395", date(2025, 12, 31)), basis=basis)
    assert result.basis == basis


@pytest.mark.parametrize("as_of", [date(2024, 12, 31), "2025-12-31"])
def test_rejects_other_period_and_unparsed_date(as_of: object) -> None:
    with pytest.raises(ValueError, match="date"):
        replace(value(), as_of=cast(date, as_of))


@pytest.mark.parametrize("raw", [AmountInput("31,827,123,947", None), AmountInput("-", "원")])
def test_unusable_original_cannot_be_value(raw: AmountInput) -> None:
    with pytest.raises(ValueError, match="normalization"):
        replace(value(), raw_amount=raw)


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("31827124"), Decimal("NaN"), 31827123947])
def test_refuses_placeholder_wrong_unit_scale_and_inexact_type(amount: object) -> None:
    with pytest.raises(ValueError):
        replace(value(), amount_krw=cast(Decimal, amount))


def test_explicit_zero_differs_from_missing() -> None:
    # Synthetic source zero is representable; missing values never take this path.
    assert (
        replace(value(), raw_amount=AmountInput("0", "원"), amount_krw=Decimal(0)).amount_krw == 0
    )


@pytest.mark.parametrize(
    "reason",
    [
        "api_missing",
        "no_financial_statements",
        "period_unavailable",
        "extraction_failed",
        "basis_unavailable",
        "transport_error",
    ],
)
def test_review_preserves_reason_without_amount(reason: ReviewReason) -> None:
    result = CashNeedsReview(
        value().query,
        "api_missing",
        datetime(2026, 11, 20, tzinfo=UTC),
        "합성 API 응답",
        "원문 확인 전",
        "원문을 확인합니다",
    )
    result = replace(result, reason=reason)
    assert result.reason == reason
    assert "amount_krw" not in asdict(result)
    assert result.evidence is None


@pytest.mark.parametrize(
    "changes",
    [
        {"reason": "unknown"},
        {"checked_at": datetime(2026, 11, 20)},
        {"detail": " "},
        {"next_action": ""},
    ],
)
def test_rejects_unactionable_review(changes: dict[str, object]) -> None:
    result = CashNeedsReview(
        value().query,
        "extraction_failed",
        datetime(2026, 11, 20, tzinfo=UTC),
        "개발용 변형 표",
        "단위 없음",
        "원문 단위를 확인합니다",
        evidence(),
    )
    with pytest.raises(ValueError):
        cast(Callable[..., CashNeedsReview], replace)(result, **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"source_url": "https://kind.krx.co.kr.evil.test/a"},
        {"source_url": "javascript:alert(1)"},
        {"document_sha256": "missing"},
        {"locator": ""},
        {"receipt_number": "20260320005559X"},
        {"context": ""},
    ],
)
def test_rejects_missing_or_unsafe_evidence(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        cast(Callable[..., CashEvidence], replace)(evidence(), **changes)


@pytest.mark.parametrize("changes", [{"corp_code": "084990"}, {"scope": "other"}, {"as_of": None}])
def test_query_has_explicit_identity_date_and_scope(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        cast(Callable[..., CashQuery], replace)(value().query, **changes)


def test_separate_source_case_keeps_own_value_and_evidence() -> None:
    folder = FIXTURE.parent
    case = json.loads((folder / "separate-contract-v1.json").read_text())
    context = (folder / case["context_file"]).read_bytes()
    assert hashlib.sha256(context).hexdigest() == case["context_sha256"]
    result = CashValue(
        CashQuery("00359395", date.fromisoformat(case["as_of"])),
        "separate",
        date.fromisoformat(case["as_of"]),
        AmountInput(case["raw_value"], case["unit"]),
        Decimal(case["amount_krw"]),
        CashEvidence(case["source_url"], case["source_sha256"], case["locator"], context.decode()),
    )
    assert result.amount_krw == Decimal("31653154838")
    assert result.amount_krw != value().amount_krw
    assert result.query.scope == "standalone"
