"""Real development source metadata with synthetic list rows; mutations are modified cases."""

import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from test_correction_case import candidate, request

from dartness.correction_evidence import (
    CorrectionEvidence,
    ReportVersion,
    ViewerRelation,
    assess_correction,
)
from dartness.disclosure_candidate import select_candidate
from dartness.disclosure_list import Disclosure

RESEARCH = json.loads(Path("docs/research/hd-construction-correction.json").read_text())


def version(which: str) -> ReportVersion:
    c = candidate(which, "separate")
    d = Disclosure(
        c.source.document_id,
        c.key.corp_code,
        "HD건설기계",
        "Y",
        "267270",
        "사업보고서" if which == "original" else "[기재정정]사업보고서",
        c.source.published_on,
        "HD건설기계",
        "",
    )
    return ReportVersion(c, d, "사업보고서", date(2025, 1, 1), date(2025, 12, 31))


def evidence() -> CorrectionEvidence:
    r = RESEARCH["sources"]["original_viewer"]
    return CorrectionEvidence(
        date(2026, 3, 18),
        replace(
            version("correction").candidate.source,
            locator="PDF physical page 5 / 정정표",
            context="사업보고서 / 최초제출일 2026년 03월 18일",
        ),
        ViewerRelation(
            "20260318001192",
            "20260602000456",
            r["url"],
            r["response_sha256"],
            "본문 선택 목록",
            "원본 20260318001192 / 정정 20260602000456",
        ),
    )


def test_real_development_pair_keeps_distinct_hash_scopes_without_selecting() -> None:
    wanted = request(datetime(2026, 11, 25, tzinfo=UTC), "separate")
    a, b, proof = version("original"), version("correction"), evidence()
    result = assess_correction(wanted, a, b, proof)
    assert result.status == "metadata_consistent" and result.reason is None
    assert result.evidence is proof and result.original is a and result.correction is b
    assert proof.errata_source.document_sha256 != proof.viewer.response_sha256
    assert proof.viewer.response_sha256 == RESEARCH["sources"]["original_viewer"]["response_sha256"]
    old = select_candidate(wanted, [a.candidate, b.candidate])
    assert old.status == "needs_review" and old.reason == "ambiguous_candidate"
    assert old.candidate is None

    def mutate(value: object, field: str) -> None:
        setattr(value, field, date(2020, 1, 1))

    with pytest.raises(FrozenInstanceError):
        mutate(proof, "first_submitted_on")


@pytest.mark.parametrize("index", range(3))
def test_modified_list_identity_cannot_attach_to_source(index: int) -> None:
    a = version("original")
    changed = [
        replace(a.disclosure, receipt="20260318001193"),
        replace(a.disclosure, corp_code="00000001"),
        replace(a.disclosure, filed_on=date(2026, 3, 19)),
    ][index]
    with pytest.raises(ValueError, match="identity"):
        replace(a, disclosure=changed)


@pytest.mark.parametrize("index", range(3))
def test_modified_report_scope_cannot_link(index: int) -> None:
    wanted = request(datetime(2026, 11, 25, tzinfo=UTC), "separate")
    b = version("correction")
    changed = [
        replace(b, report_kind="반기보고서"),
        replace(b, period_start=date(2025, 2, 1)),
        replace(b, period_end=date(2026, 1, 1)),
    ][index]
    with pytest.raises(ValueError, match="same report"):
        assess_correction(wanted, version("original"), changed, evidence())


def test_other_target_cannot_be_used_even_when_receipts_match() -> None:
    wanted = request(datetime(2026, 11, 25, tzinfo=UTC), "consolidated")
    with pytest.raises(ValueError, match="complete target"):
        assess_correction(wanted, version("original"), version("correction"), evidence())


def test_modified_first_date_does_not_use_corrected_cover_date_as_publication() -> None:
    wanted = request(datetime(2026, 11, 25, tzinfo=UTC), "separate")
    with pytest.raises(ValueError, match="first submission"):
        assess_correction(
            wanted,
            version("original"),
            version("correction"),
            replace(evidence(), first_submitted_on=date(2026, 6, 2)),
        )


@pytest.mark.parametrize("index", range(3))
def test_modified_errata_document_is_rejected(index: int) -> None:
    proof = evidence()
    source = proof.errata_source
    changed = [
        replace(source, document_sha256="a" * 64),
        replace(source, document_id="20260602000457"),
        replace(source, published_on=date(2026, 3, 18)),
    ][index]
    with pytest.raises(ValueError, match="correction full document"):
        assess_correction(
            request(datetime(2026, 11, 25, tzinfo=UTC), "separate"),
            version("original"),
            version("correction"),
            replace(proof, errata_source=changed),
        )


def test_modified_explicit_viewer_receipt_cannot_link_other_correction() -> None:
    proof = evidence()
    with pytest.raises(ValueError, match="both receipts"):
        assess_correction(
            request(datetime(2026, 11, 25, tzinfo=UTC), "separate"),
            version("original"),
            version("correction"),
            replace(proof, viewer=replace(proof.viewer, correction_receipt="20260602000457")),
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/dsaf001/main.do?rcpNo=20260318001192",
        "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260602000456",
        "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260318001192&token=unexpected",
        "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260318001192&token=",
    ],
)
def test_viewer_url_must_identify_original_without_extra_parameters(url: str) -> None:
    with pytest.raises(ValueError, match="viewer URL"):
        replace(evidence().viewer, source_url=url)


def test_missing_relation_evidence_is_not_inferred_from_titles_or_equal_values() -> None:
    result = assess_correction(
        request(datetime(2026, 11, 25, tzinfo=UTC), "separate"),
        version("original"),
        version("correction"),
        None,
    )
    assert result.status == "needs_review" and result.reason == "missing_evidence"


def test_correction_after_cutoff_remains_unusable_even_with_prepared_relation() -> None:
    result = assess_correction(
        request(datetime(2026, 5, 1, tzinfo=UTC), "separate"),
        version("original"),
        version("correction"),
        evidence(),
    )
    assert result.status == "needs_review" and result.reason == "after_cutoff"


def test_same_day_order_is_not_inferred_from_receipt_numbers() -> None:
    a, b = version("original"), version("correction")
    c = replace(b.candidate, source=replace(b.candidate.source, published_on=a.disclosure.filed_on))
    b = replace(b, candidate=c, disclosure=replace(b.disclosure, filed_on=a.disclosure.filed_on))
    result = assess_correction(request(datetime(2026, 11, 25, tzinfo=UTC), "separate"), a, b, None)
    assert result.status == "needs_review" and result.reason == "unclear_order"
