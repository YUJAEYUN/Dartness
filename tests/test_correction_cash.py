"""Real-dev fixed cell answers; list rows are synthetic and changed inputs are modified."""

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from test_correction_case import CASE, candidate, request
from test_correction_evidence import evidence, version

from dartness.amounts import AmountInput
from dartness.cash_contract import CashBasis, CashEvidence, CashQuery, CashValue
from dartness.correction_cash import CorrectionCashComparison
from dartness.correction_evidence import CorrectionAssessment, assess_correction
from dartness.disclosure_candidate import select_candidate


def relation(basis: str = "separate") -> CorrectionAssessment:
    versions = []
    for name in ("original", "correction"):
        v = version(name)
        versions.append(replace(v, candidate=candidate(name, basis)))
    return assess_correction(
        request(datetime(2026, 11, 25, tzinfo=UTC), basis), versions[0], versions[1], evidence()
    )


def cash(name: str, basis: CashBasis = "separate") -> CashValue:
    c = candidate(name, basis)
    e = CASE["expected"]["current_cash"][basis]
    return CashValue(
        CashQuery(
            "01205842",
            date(2025, 12, 31),
            "consolidated" if basis == "consolidated" else "standalone",
        ),
        basis,
        c.actual_date,
        AmountInput(e["pdf_raw_thousand_krw"], "천원"),
        Decimal(e["amount_krw"]),
        CashEvidence(
            c.source.source_url,
            c.source.document_sha256,
            c.source.locator,
            c.source.context,
            c.source.document_id,
        ),
    )


@pytest.mark.parametrize(
    "basis,expected",
    [
        ("separate", "69787650000"),
        ("consolidated", "337873166000"),
    ],
)
def test_real_development_cells_are_equal_without_selecting_a_report(
    basis: CashBasis, expected: str
) -> None:
    link = relation(basis)
    result = CorrectionCashComparison(link, cash("original", basis), cash("correction", basis))
    assert result.status == "amounts_equal" and result.reason is None
    assert result.original is not None and result.correction is not None
    assert result.original.amount_krw == result.correction.amount_krw == Decimal(expected)
    assert result.original.evidence.receipt_number == "20260318001192"
    assert result.correction.evidence.receipt_number == "20260602000456"
    assert result.original.evidence.document_sha256 != result.correction.evidence.document_sha256
    old = select_candidate(link.request, [link.original.candidate, link.correction.candidate])
    assert old.candidate is None and old.reason == "ambiguous_candidate"


def test_modified_different_units_compare_exact_normalized_amounts() -> None:
    b = cash("correction")
    b = replace(b, raw_amount=AmountInput("69787650000", "원"))
    result = CorrectionCashComparison(relation(), cash("original"), b)
    assert result.status == "amounts_equal"
    assert result.correction is not None and result.correction.raw_amount.unit == "원"
    assert result.original is not None and result.original.raw_amount.unit == "천원"


def test_modified_one_won_difference_is_retained_without_warning_or_tolerance_policy() -> None:
    b = replace(
        cash("correction"),
        raw_amount=AmountInput("69787650001", "원"),
        amount_krw=Decimal("69787650001"),
    )
    result = CorrectionCashComparison(relation(), cash("original"), b)
    assert result.status == "amounts_differ" and result.reason is None
    assert result.correction is b and result.correction.amount_krw == Decimal("69787650001")


@pytest.mark.parametrize("missing", ["original", "correction", "both"])
def test_missing_cells_never_become_zero_or_equal(missing: str) -> None:
    result = CorrectionCashComparison(
        relation(),
        None if missing in ("original", "both") else cash("original"),
        None if missing in ("correction", "both") else cash("correction"),
    )
    assert result.status == "needs_review" and result.reason == "missing_value"


def test_incomplete_relation_is_rechecked_even_if_status_was_forged() -> None:
    link = relation()
    link = replace(link, evidence=None, status="metadata_consistent", reason=None)
    result = CorrectionCashComparison(link, cash("original"), cash("correction"))
    assert result.status == "needs_review" and result.reason == "relation_needs_review"
    assert result.relation.status == "needs_review"
    assert result.relation.reason == "missing_evidence"


def test_relation_after_cutoff_cannot_be_used_for_comparison() -> None:
    link = relation()
    link = replace(link, request=request(datetime(2026, 5, 1, tzinfo=UTC), "separate"))
    result = CorrectionCashComparison(link, cash("original"), cash("correction"))
    assert result.status == "needs_review" and result.reason == "relation_needs_review"
    assert result.relation.reason == "after_cutoff"


def test_equal_numbers_from_swapped_documents_are_rejected() -> None:
    with pytest.raises(ValueError, match="candidate cell"):
        CorrectionCashComparison(relation(), cash("correction"), cash("original"))


@pytest.mark.parametrize("index", range(5))
def test_modified_cell_source_cannot_be_mixed(index: int) -> None:
    b = cash("correction")
    e = b.evidence
    modified = [
        replace(e, receipt_number="20260602000457"),
        replace(e, document_sha256="a" * 64),
        replace(e, locator="another row"),
        replace(e, context="another context"),
        replace(e, receipt_number=None),
    ][index]
    with pytest.raises(ValueError, match="candidate cell"):
        CorrectionCashComparison(relation(), cash("original"), replace(b, evidence=modified))


@pytest.mark.parametrize("index", range(3))
def test_modified_scope_date_and_company_are_rejected(index: int) -> None:
    b = cash("correction")
    changed = [
        cash("correction", "consolidated"),
        replace(b, query=replace(b.query, corp_code="00000001")),
        replace(b, query=replace(b.query, as_of=date(2024, 12, 31)), as_of=date(2024, 12, 31)),
    ][index]
    with pytest.raises(ValueError, match="candidate scope"):
        CorrectionCashComparison(relation(), cash("original"), changed)


def test_other_snapshot_item_is_not_silently_processed_as_cash() -> None:
    link = relation()
    key = replace(link.request.key, query_type="us-bonds", item_key="treasury")
    # Build the other query through its own supported request, not a cash request.
    from dartness.query_contract import QueryRun, SnapshotRequest

    wanted = replace(
        link.request,
        key=key,
        run=QueryRun(
            SnapshotRequest("us-bonds", "as_of", 0, date(2025, 12, 31)),
            datetime(2026, 11, 25, tzinfo=UTC),
        ),
    )
    a = replace(link.original, candidate=replace(link.original.candidate, key=key))
    b = replace(link.correction, candidate=replace(link.correction.candidate, key=key))
    other = assess_correction(wanted, a, b, link.evidence)
    with pytest.raises(ValueError, match="only the KRW cash"):
        CorrectionCashComparison(other, None, None)
