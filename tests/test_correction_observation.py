"""Real-dev retained web responses and explicitly modified/synthetic failure cases."""

import gzip
import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from test_correction_evidence import version

from dartness.correction_observation import (
    CorrectionWebObservation,
    collect_correction_web,
    observe_correction_web,
)

FIXTURE = Path(__file__).parent / "fixtures/corrections/hd-viewer-observation"
ORIGIN = json.loads((FIXTURE / "origin.json").read_text())
ORIGINAL = gzip.decompress((FIXTURE / "original_viewer.html.gz").read_bytes())
CORRECTION = gzip.decompress((FIXTURE / "correction_viewer.html.gz").read_bytes())
ERRATA = gzip.decompress((FIXTURE / "correction_errata.html.gz").read_bytes())
OBSERVED_AT = datetime.fromisoformat(ORIGIN["observed_at"])
ERRATA_URL = ORIGIN["sources"]["correction_errata"]["url"]


def observe(
    original: bytes = ORIGINAL, correction: bytes = CORRECTION, errata: bytes = ERRATA
) -> CorrectionWebObservation:
    return observe_correction_web(
        version("original").disclosure,
        version("correction").disclosure,
        original,
        correction,
        errata,
        OBSERVED_AT,
        errata_url=ERRATA_URL,
    )


def test_real_pair_reads_body_relationship_and_literal_errata_without_selecting() -> None:
    result = observe()
    for name, payload in (
        ("original_viewer", ORIGINAL),
        ("correction_viewer", CORRECTION),
        ("correction_errata", ERRATA),
    ):
        assert hashlib.sha256(payload).hexdigest() == ORIGIN["sources"][name]["response_sha256"]
    assert result.corp_code == "01205842"
    assert {entry.receipt for entry in result.original_history} == {
        "20260318001192",
        "20260602000456",
    }
    assert len(result.original_history) == len(result.correction_history) == 2
    assert result.errata.first_submitted_on == date(2026, 3, 18)
    assert result.errata.corrected_on == date(2026, 6, 2)
    assert result.errata.report_kind == "사업보고서"
    assert len(result.errata.changes) == 1
    change = result.errata.changes[0]
    assert "연결대상기업의 개요(연결)" in change[0]
    assert change[1:] == ("-", "기재방식의 변경", "디테일 태깅", "블록 태깅")
    audit = result.to_dict()
    assert audit["latest_correction_verified"] is False
    assert audit["cash_impact_verified"] is False
    assert audit["full_document_binding_verified"] is False
    assert audit["observed_at"] == ORIGIN["observed_at"]
    assert audit["status"] == "web_evidence_observed"
    assert audit["selected_receipt"] is None
    assert result.viewer_relation.original_receipt == "20260318001192"
    assert (
        result.viewer_relation.response_sha256
        == ORIGIN["sources"]["original_viewer"]["response_sha256"]
    )


@pytest.mark.parametrize(
    "before,after,message",
    [
        (b"openCorpInfoNew('01205842'", b"openCorpInfoNew('00000001'", "company_mismatch"),
        (b'id="family"', b'id="only_attachments"', "body_history_required"),
        (b'rcpNo=20260602000456"', b'rcpNo=20260602000457"', "body_history_conflict"),
        (b"2026.03.18", b"2026.03.19", "body_history_conflict"),
        (b'selected title="', b'title="', "selected_body_mismatch"),
    ],
)
def test_modified_original_history_is_not_replaced_by_attachment_or_other_body(
    before: bytes, after: bytes, message: str
) -> None:
    changed = ORIGINAL.replace(before, after)
    assert changed != ORIGINAL
    with pytest.raises(ValueError, match=message):
        observe(original=changed)


def test_both_sides_must_show_the_same_body_history() -> None:
    changed = CORRECTION.replace(b"2026.03.18", b"2026.03.19")
    with pytest.raises(ValueError, match="body_history_conflict"):
        observe(correction=changed)


@pytest.mark.parametrize(
    "before,after,message",
    [
        ("2026년 03월 18일".encode(), "2026년 03월 19일".encode(), "first_submission_mismatch"),
        ("2026년 06월 02일".encode(), "2026년 06월 03일".encode(), "correction_date_mismatch"),
        ("사업보고서".encode(), "반기보고서".encode(), "report_kind_mismatch"),
        (b"class='correction'", b"class='other'", "errata_heading_required"),
        (b"</TD>", b"", "cell_boundary"),
        (b"<TD width='156'", b"<TD colspan='2' width='156'", "merged_errata_cell"),
    ],
)
def test_malformed_or_conflicting_errata_is_not_accepted(
    before: bytes, after: bytes, message: str
) -> None:
    changed = ERRATA.replace(before, after)
    assert changed != ERRATA
    with pytest.raises(ValueError, match=message):
        observe(errata=changed)


def test_error_page_and_oversized_page_are_rejected() -> None:
    with pytest.raises(ValueError, match="body_history_required"):
        observe(original=b"maintenance")
    with pytest.raises(ValueError, match="page_too_large"):
        observe(original=b"x" * (2 * 1024 * 1024 + 1))


def test_unaware_observation_time_and_wrong_company_metadata_are_input_errors() -> None:
    with pytest.raises(ValueError, match="aware_observation_time"):
        observe_correction_web(
            version("original").disclosure,
            version("correction").disclosure,
            ORIGINAL,
            CORRECTION,
            ERRATA,
            datetime(2026, 11, 23),
            errata_url=ERRATA_URL,
        )
    with pytest.raises(ValueError, match="same_company"):
        observe_correction_web(
            version("original").disclosure,
            replace(version("correction").disclosure, corp_code="00000001"),
            ORIGINAL,
            CORRECTION,
            ERRATA,
            datetime(2026, 11, 23, tzinfo=UTC),
            errata_url=ERRATA_URL,
        )


def test_three_request_collection_uses_the_observed_toc_url() -> None:
    pages = {
        version("original").disclosure.source_url: ORIGINAL,
        version("correction").disclosure.source_url: CORRECTION,
        ERRATA_URL: ERRATA,
    }
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return pages[url]

    result = collect_correction_web(
        version("original").disclosure, version("correction").disclosure, fetch, OBSERVED_AT
    )
    assert calls == list(pages)
    assert result.to_dict()["errata_url"] == ERRATA_URL
    assert result.to_dict()["latest_correction_verified"] is False


def test_errata_from_another_location_cannot_bind_to_this_correction() -> None:
    with pytest.raises(ValueError, match="errata_location_mismatch"):
        observe_correction_web(
            version("original").disclosure,
            version("correction").disclosure,
            ORIGINAL,
            CORRECTION,
            ERRATA,
            OBSERVED_AT,
            errata_url=ERRATA_URL.replace("11416776", "11416777"),
        )


def test_extra_body_version_is_preserved_and_never_called_the_latest() -> None:
    extra = (
        '<option value="rcpNo=20260701000001" title="사업보고서">'
        "2026.07.01 [정정] 사업보고서</option>"
    ).encode()
    original = ORIGINAL.replace('<option value="null">+본문선택+</option>'.encode(), extra)
    correction = CORRECTION.replace('<option value="null">+본문선택+</option>'.encode(), extra)
    assert original != ORIGINAL and correction != CORRECTION
    result = observe(original=original, correction=correction)
    assert len(result.original_history) == 3
    assert "20260701000001" in [entry.receipt for entry in result.original_history]
    assert result.to_dict()["selected_receipt"] is None
    assert result.to_dict()["latest_correction_verified"] is False


def test_duplicate_body_options_are_not_deduplicated_into_success() -> None:
    changed = ORIGINAL.replace(
        '<option value="null">+본문선택+</option>'.encode(),
        (
            '<option value="rcpNo=20260602000456" title="사업보고서">'
            "2026.06.02 [정정] 사업보고서</option>"
        ).encode(),
    )
    with pytest.raises(ValueError, match="duplicate_body_receipt"):
        observe(original=changed)


def test_transport_failure_stops_collection_without_returning_an_empty_success() -> None:
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        raise ValueError("viewer_transport_error")

    with pytest.raises(ValueError, match="viewer_transport_error"):
        collect_correction_web(
            version("original").disclosure, version("correction").disclosure, fetch, OBSERVED_AT
        )
    assert len(calls) == 1
