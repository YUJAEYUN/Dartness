"""Whole native real-dev reports bound against preexisting PDF/XBRL cash answers."""

import gzip
import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from test_correction_evidence import version

from dartness.cash_contract import CashBasis
from dartness.cash_report_candidates import StoredCashReport
from dartness.correction_binding import CorrectionWebInputs, bind_native_correction
from dartness.disclosure_candidate import CandidateKey, CandidateRequest, select_candidate
from dartness.query_contract import QueryRun, SnapshotRequest

FIXTURE = Path(__file__).parent / "fixtures/corrections/hd-native-2025"
ORIGIN = json.loads((FIXTURE / "origin.json").read_text())
WEB = Path(__file__).parent / "fixtures/corrections/hd-viewer-observation"
WEB_ORIGIN = json.loads((WEB / "origin.json").read_text())
INPUTS = CorrectionWebInputs(
    gzip.decompress((WEB / "original_viewer.html.gz").read_bytes()),
    gzip.decompress((WEB / "correction_viewer.html.gz").read_bytes()),
    gzip.decompress((WEB / "correction_errata.html.gz").read_bytes()),
    WEB_ORIGIN["sources"]["correction_errata"]["url"],
    datetime.fromisoformat(WEB_ORIGIN["observed_at"]),
)
A = StoredCashReport(version("original").disclosure, (FIXTURE / "original.zip").read_bytes())
B = StoredCashReport(version("correction").disclosure, (FIXTURE / "correction.zip").read_bytes())


def wanted(basis: CashBasis = "separate", when: datetime | None = None) -> CandidateRequest:
    run = QueryRun(
        SnapshotRequest("cash", "as_of", 0, date(2025, 12, 31)),
        when or datetime(2026, 11, 26, tzinfo=UTC),
    )
    return CandidateRequest(
        run, CandidateKey("01205842", "cash", "cash-and-cash-equivalents", basis, "KRW")
    )


@pytest.mark.parametrize(
    "basis,amount", [("separate", "69787650000"), ("consolidated", "337873166000")]
)
def test_real_native_sources_bind_period_errata_and_cells_without_selecting_latest(
    basis: CashBasis, amount: str
) -> None:
    for source, record in zip((A, B), ORIGIN["reports"], strict=True):
        assert hashlib.sha256(source.archive).hexdigest() == record["archive_sha256"]
    result = bind_native_correction(wanted(basis), date(2025, 12, 31), A, B, INPUTS)
    assert result.failure is None and result.status == "amounts_equal"
    assert result.comparison is not None
    assert result.comparison.original is not None and result.comparison.correction is not None
    assert (
        result.comparison.original.amount_krw
        == result.comparison.correction.amount_krw
        == Decimal(amount)
    )
    assert result.relation is not None and result.relation.status == "metadata_consistent"
    assert result.relation.original.period_start == date(2025, 1, 1)
    assert result.relation.correction.period_end == date(2025, 12, 31)
    assert result.relation.evidence is not None
    assert (
        result.relation.evidence.errata_source.document_sha256
        == ORIGIN["reports"][1]["main_document_sha256"]
    )
    assert (
        result.relation.evidence.viewer.response_sha256
        != result.relation.evidence.errata_source.document_sha256
    )
    assert result.original is not None and result.correction is not None
    assert result.original.document_sha256 == ORIGIN["reports"][0]["main_document_sha256"]
    assert result.correction.document_sha256 == ORIGIN["reports"][1]["main_document_sha256"]
    audit = result.to_dict()
    assert audit["full_document_binding_verified"] is True
    assert audit["latest_correction_verified"] is False and audit["selected_receipt"] is None
    old = select_candidate(
        wanted(basis), [result.relation.original.candidate, result.relation.correction.candidate]
    )
    assert old.reason == "ambiguous_candidate" and old.candidate is None


def test_future_correction_is_not_compared_as_an_available_value() -> None:
    result = bind_native_correction(
        wanted(when=datetime(2026, 5, 1, tzinfo=UTC)), date(2025, 12, 31), A, B, INPUTS
    )
    assert result.status == "needs_review" and result.failure == "after_cutoff"
    assert result.comparison is None


def test_wrong_main_or_corporation_cannot_attach_a_web_relation() -> None:
    with pytest.raises(ValueError, match="company_mismatch"):
        bind_native_correction(
            wanted(),
            date(2025, 12, 31),
            replace(A, disclosure=replace(A.disclosure, corp_code="00000001")),
            B,
            INPUTS,
        )
    result = bind_native_correction(
        wanted(), date(2025, 12, 31), A, replace(B, archive=A.archive), INPUTS
    )
    assert result.status == "needs_review" and result.comparison is None
    assert result.failure == "main_document_missing"


def small_native(cover: str) -> bytes:
    return (
        '<DOCUMENT><DOCUMENT-NAME ACODE="11011">사업보고서</DOCUMENT-NAME><BODY>'
        + cover
        + "</BODY></DOCUMENT>"
    ).encode()


COVER = (
    '<COVER><TU AUNIT="PERIODFROM" AUNITVALUE="20250101">2025년 01월 01일</TU>'
    '<TU AUNIT="PERIODTO" AUNITVALUE="20251231">2025년 12월 31일</TU></COVER>'
)


def test_synthetic_cover_requires_visible_and_attribute_dates_to_agree() -> None:
    from dartness.native_report import read_native_metadata

    meta = read_native_metadata(small_native(COVER))
    assert meta.period_start == date(2025, 1, 1) and meta.correction is None
    with pytest.raises(ValueError, match="native_period_text_mismatch"):
        read_native_metadata(small_native(COVER.replace('VALUE="20250101"', 'VALUE="20250102"')))
    with pytest.raises(ValueError, match="missing_or_ambiguous"):
        read_native_metadata(small_native(COVER + COVER))
    with pytest.raises(ValueError, match="outside_body"):
        read_native_metadata(small_native("") + COVER.encode())


def test_invalid_observation_time_is_not_interpreted_in_host_timezone() -> None:
    with pytest.raises(ValueError, match="aware_web_observation_time"):
        replace(INPUTS, observed_at=datetime(2026, 11, 23))


def modified_archive(source: StoredCashReport, before: bytes, after: bytes) -> StoredCashReport:
    import io
    import zipfile

    from dartness.dart_smoke import read_archive

    members = read_archive(source.archive)
    name = source.disclosure.receipt + ".xml"
    assert before in members[name]
    members[name] = members[name].replace(before, after)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, body in members.items():
            archive.writestr(filename, body)
    return replace(source, archive=stream.getvalue())


def test_modified_native_errata_cannot_be_replaced_by_matching_web_text() -> None:
    changed = modified_archive(B, "2026년 03월 18일".encode(), "2026년 03월 19일".encode())
    result = bind_native_correction(wanted(), date(2025, 12, 31), A, changed, INPUTS)
    assert result.failure == "native_web_errata_mismatch"
    assert result.comparison is None and result.to_dict()["full_document_binding_verified"] is False


def test_modified_cash_difference_is_reported_without_selecting_or_judging_company_error() -> None:
    changed = modified_archive(B, b"69,787,650", b"69,787,651")
    result = bind_native_correction(wanted(), date(2025, 12, 31), A, changed, INPUTS)
    assert result.status == "amounts_differ" and result.failure is None
    assert result.comparison is not None and result.comparison.correction is not None
    assert result.comparison.correction.amount_krw == Decimal("69787651000")
    assert result.to_dict()["latest_correction_verified"] is False
    assert result.to_dict()["selected_receipt"] is None


def test_comparative_column_does_not_silently_weaken_existing_version_period_contract() -> None:
    run = QueryRun(
        SnapshotRequest("cash", "as_of", 0, date(2024, 12, 31)), wanted().run.executed_at
    )
    request = CandidateRequest(run, wanted().key)
    result = bind_native_correction(request, date(2024, 12, 31), A, B, INPUTS)
    assert result.failure == "comparative_period_not_supported_by_version_v1"
    assert result.status == "needs_review" and result.comparison is None
