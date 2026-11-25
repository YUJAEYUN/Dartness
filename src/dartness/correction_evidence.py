"""Check prepared correction metadata, not source semantics or version selection."""

import re
from dataclasses import dataclass
from datetime import date
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from dartness.disclosure_candidate import CandidateRequest, CandidateSource, DisclosureCandidate
from dartness.disclosure_list import Disclosure


@dataclass(frozen=True)
class ReportVersion:
    candidate: DisclosureCandidate
    disclosure: Disclosure
    report_kind: str
    period_start: date
    period_end: date

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, DisclosureCandidate) or not isinstance(
            self.disclosure, Disclosure
        ):
            raise ValueError("candidate and collected disclosure required")
        c, d = self.candidate, self.disclosure
        if (c.source.document_id, c.key.corp_code, c.source.published_on) != (
            d.receipt,
            d.corp_code,
            d.filed_on,
        ):
            raise ValueError("collected disclosure must match candidate identity")
        if not isinstance(self.report_kind, str) or not self.report_kind.strip():
            raise ValueError("explicit report kind required")
        if type(self.period_start) is not date or type(self.period_end) is not date:
            raise ValueError("explicit report period required")
        if not self.period_start <= c.actual_date <= self.period_end:
            raise ValueError("candidate date must lie within report period")


@dataclass(frozen=True)
class ViewerRelation:
    original_receipt: str
    correction_receipt: str
    source_url: str
    response_sha256: str
    locator: str
    context: str

    def __post_init__(self) -> None:
        for receipt in (self.original_receipt, self.correction_receipt):
            if not isinstance(receipt, str) or not re.fullmatch(r"[0-9]{14}", receipt):
                raise ValueError("fourteen-digit relation receipts required")
        if self.original_receipt == self.correction_receipt:
            raise ValueError("distinct relation receipts required")
        if not isinstance(self.source_url, str):
            raise ValueError("DART viewer URL required")
        try:
            url = urlsplit(self.source_url)
            valid = (
                url.scheme == "https"
                and url.hostname == "dart.fss.or.kr"
                and url.path == "/dsaf001/main.do"
                and url.username is None
                and url.password is None
                and url.port in (None, 443)
                and not url.fragment
                and parse_qs(url.query, keep_blank_values=True)
                == {"rcpNo": [self.original_receipt]}
            )
        except ValueError as error:
            raise ValueError("DART viewer URL required") from error
        if not valid:
            raise ValueError("DART original viewer URL required")
        if not isinstance(self.response_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.response_sha256
        ):
            raise ValueError("viewer response SHA-256 required")
        if any(not isinstance(v, str) or not v.strip() for v in (self.locator, self.context)):
            raise ValueError("viewer location and context required")


@dataclass(frozen=True)
class CorrectionEvidence:
    first_submitted_on: date
    errata_source: CandidateSource
    viewer: ViewerRelation

    def __post_init__(self) -> None:
        if type(self.first_submitted_on) is not date:
            raise ValueError("explicit first submission date required")
        if not isinstance(self.errata_source, CandidateSource) or not isinstance(
            self.viewer, ViewerRelation
        ):
            raise ValueError("full-document errata and viewer evidence required")


@dataclass(frozen=True)
class CorrectionAssessment:
    request: CandidateRequest
    original: ReportVersion
    correction: ReportVersion
    evidence: CorrectionEvidence | None
    status: Literal["metadata_consistent", "needs_review"]
    reason: Literal["missing_evidence", "after_cutoff", "unclear_order"] | None


def assess_correction(
    request: CandidateRequest,
    original: ReportVersion,
    correction: ReportVersion,
    evidence: CorrectionEvidence | None,
) -> CorrectionAssessment:
    """Retain evidence without returning an automatically selected version or amount."""
    if not isinstance(request, CandidateRequest) or any(
        not isinstance(v, ReportVersion) for v in (original, correction)
    ):
        raise ValueError("request and two report versions required")
    a, b = original.candidate, correction.candidate
    if a.key != request.key or b.key != request.key or a.actual_date != b.actual_date:
        raise ValueError("versions must match the complete target and actual date")
    if (original.report_kind, original.period_start, original.period_end) != (
        correction.report_kind,
        correction.period_start,
        correction.period_end,
    ):
        raise ValueError("same report kind and period required")
    if a.source.document_id == b.source.document_id:
        raise ValueError("distinct original and correction required")
    if evidence is not None:
        if not isinstance(evidence, CorrectionEvidence):
            raise ValueError("CorrectionEvidence required")
        source, viewer = evidence.errata_source, evidence.viewer
        if (source.document_id, source.published_on, source.document_sha256, source.source_url) != (
            b.source.document_id,
            b.source.published_on,
            b.source.document_sha256,
            b.source.source_url,
        ):
            raise ValueError("errata must reference the correction full document")
        if evidence.first_submitted_on != a.source.published_on:
            raise ValueError("errata first submission must match original publication")
        if (viewer.original_receipt, viewer.correction_receipt) != (
            a.source.document_id,
            b.source.document_id,
        ):
            raise ValueError("explicit viewer relation must match both receipts")
    reason: Literal["missing_evidence", "after_cutoff", "unclear_order"] | None = None
    if max(a.source.published_on, b.source.published_on) > request.run.execution_date:
        reason = "after_cutoff"
    elif a.source.published_on >= b.source.published_on:
        reason = "unclear_order"
    elif evidence is None:
        reason = "missing_evidence"
    return CorrectionAssessment(
        request,
        original,
        correction,
        evidence,
        "metadata_consistent" if reason is None else "needs_review",
        reason,
    )
