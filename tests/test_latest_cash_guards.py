"""Synthetic invalid inputs exercise the existing latest-source contract, not new gold."""

import io
import zipfile
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from test_latest_cash import CORP, body, history_for, request, synthetic

from dartness.cash_report_candidates import StoredCashReport
from dartness.latest_cash import query_latest_cash


def archive_with(source: StoredCashReport, before: bytes, after: bytes) -> StoredCashReport:
    name = source.disclosure.receipt + ".xml"
    with zipfile.ZipFile(io.BytesIO(source.archive)) as original:
        raw = original.read(name)
    assert raw.count(before) == 1
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(name, raw.replace(before, after))
    return replace(source, archive=output.getvalue())


@pytest.mark.parametrize(
    "defect,reason",
    [
        ("missing_main", "main_document_missing"),
        ("period_after_filing", "report_period_after_publication"),
        ("listing_period", "listing_native_report_period_mismatch"),
        ("listing_metadata", "source_listing_metadata_mismatch"),
        ("no_requested_date", "period_unavailable"),
        ("duplicate_body", "selected_body_observation_required"),
        ("naive_body_time", "body_observation_execution_day_required"),
        ("old_body_day", "body_observation_execution_day_required"),
        ("body_correction_marker", "body_native_correction_mismatch"),
        ("column_after_period", "financial_column_after_report_period"),
    ],
)
def test_invalid_latest_inputs_never_produce_an_amount(defect: str, reason: str) -> None:
    source = synthetic(True)
    run = request()
    listing = source.disclosure
    proofs = (body(source),)
    if defect == "missing_main":
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("other.xml", b"<DOCUMENT/>")
        source = replace(source, archive=output.getvalue())
    elif defect == "period_after_filing":
        listing = replace(listing, filed_on=date(2026, 9, 1))
        source = replace(source, disclosure=listing)
    elif defect == "listing_period":
        listing = replace(listing, report_name="분기보고서 (2026.03)")
        source = replace(source, disclosure=listing)
    elif defect == "listing_metadata":
        source = replace(source, disclosure=replace(listing, corp_name="다른 표시 이름"))
    elif defect == "no_requested_date":
        run = request(date(2024, 12, 31))
    elif defect == "duplicate_body":
        proofs = (proofs[0], proofs[0])
    elif defect == "naive_body_time":
        proofs = (replace(proofs[0], observed_at=datetime(2026, 11, 26)),)
    elif defect == "old_body_day":
        proofs = (replace(proofs[0], observed_at=datetime(2026, 11, 25, tzinfo=UTC)),)
    elif defect == "body_correction_marker":
        proofs = (
            replace(
                proofs[0],
                payload=proofs[0].payload.replace(
                    "2026.11.16 분기보고서".encode(), "2026.11.16 [정정]분기보고서".encode()
                ),
            ),
        )
    elif defect == "column_after_period":
        source = archive_with(source, b"2026.09.30", b"2026.12.31")
    result = query_latest_cash(
        run, CORP, "separate", Decimal(0), history_for((listing,)), (source,), proofs
    )
    assert result.status == "needs_review"
    assert result.reason == reason
    assert result.report is None
    audit = result.to_dict()
    assert audit["selected_receipt"] is None
    assert audit["selected_report"] is None
    assert audit["latest_correction_verified"] is False
    assert audit["minimum_krw"] == "0"


@pytest.mark.parametrize("minimum", [Decimal(-1), Decimal("NaN"), Decimal("Infinity")])
def test_invalid_minimum_is_rejected_before_source_selection(minimum: Decimal) -> None:
    source = synthetic(True)
    with pytest.raises(ValueError, match="^nonnegative_exact_minimum_required$"):
        query_latest_cash(
            request(),
            CORP,
            "separate",
            minimum,
            history_for((source.disclosure,)),
            (source,),
            (body(source),),
        )
