"""Bind actual whole native documents and web evidence; compare cells without choosing latest."""

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import cast
from zoneinfo import ZoneInfo

from dartness.cash_contract import CashBasis, CashQuery, CashScope, CashValue
from dartness.cash_report import inspect_cash_report
from dartness.cash_report_candidates import StoredCashReport
from dartness.cash_report_result import CashReportResult
from dartness.correction_cash import CorrectionCashComparison
from dartness.correction_evidence import (
    CorrectionAssessment,
    CorrectionEvidence,
    ReportVersion,
    assess_correction,
)
from dartness.correction_html import read_errata
from dartness.correction_observation import CorrectionWebObservation, observe_correction_web
from dartness.dart_smoke import CollectionError, read_archive
from dartness.disclosure_candidate import (
    CandidateKey,
    CandidateRequest,
    CandidateSource,
    DisclosureCandidate,
)
from dartness.native_report import NativeReportMetadata, read_native_metadata
from dartness.query_contract import SelectedDate


@dataclass(frozen=True)
class CorrectionWebInputs:
    original_main: bytes
    correction_main: bytes
    errata_html: bytes
    errata_url: str
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.observed_at, datetime) or self.observed_at.utcoffset() is None:
            raise ValueError("aware_web_observation_time_required")


@dataclass(frozen=True)
class NativeCorrectionBinding:
    request: CandidateRequest
    actual_date: date
    sources: tuple[StoredCashReport, StoredCashReport]
    original: CashReportResult | None
    correction: CashReportResult | None
    metadata: tuple[NativeReportMetadata, ...]
    observation: CorrectionWebObservation | None
    relation: CorrectionAssessment | None
    comparison: CorrectionCashComparison | None
    failure: str | None

    @property
    def status(self) -> str:
        return self.comparison.status if self.comparison else "needs_review"

    def to_dict(self) -> dict[str, object]:
        return {
            "run_scope": "specified_correction_pair_only",
            "status": self.status,
            "failure": self.failure,
            "requested_as_of": self.request.run.anchor_date.isoformat(),
            "actual_as_of": self.actual_date.isoformat(),
            "basis": self.request.key.basis,
            "corp_code": self.request.key.corp_code,
            "currency": self.request.key.currency,
            "executed_at": self.request.run.executed_at.isoformat(),
            "sources": [
                {
                    "receipt": source.disclosure.receipt,
                    "main_filename": source.disclosure.receipt + ".xml",
                    "published_on": source.disclosure.filed_on.isoformat(),
                    "source_url": source.disclosure.source_url,
                    "archive_sha256": hashlib.sha256(source.archive).hexdigest(),
                }
                for source in self.sources
            ],
            "native_metadata": [meta.to_dict() for meta in self.metadata],
            "original": self.original.to_dict() if self.original else None,
            "correction": self.correction.to_dict() if self.correction else None,
            "web_observation": self.observation.to_dict() if self.observation else None,
            "relation_status": self.relation.status if self.relation else None,
            "relation_reason": self.relation.reason if self.relation else None,
            "comparison_reason": self.comparison.reason if self.comparison else None,
            "full_document_binding_verified": self.comparison is not None
            and self.comparison.status != "needs_review",
            "latest_correction_verified": False,
            "selected_receipt": None,
        }


def _version(
    report: CashReportResult, meta: NativeReportMetadata, key: CandidateKey
) -> ReportVersion:
    value = report.value
    if not isinstance(value, CashValue):
        raise ValueError("native_cash_value_unavailable")
    evidence = value.evidence
    source = CandidateSource(
        report.disclosure.receipt,
        report.disclosure.filed_on,
        evidence.source_url,
        evidence.document_sha256,
        evidence.locator,
        evidence.context,
    )
    return ReportVersion(
        DisclosureCandidate(key, value.as_of, source),
        report.disclosure,
        "사업보고서",
        meta.period_start,
        meta.period_end,
    )


def bind_native_correction(
    request: CandidateRequest,
    actual_date: date,
    original: StoredCashReport,
    correction: StoredCashReport,
    web: CorrectionWebInputs,
) -> NativeCorrectionBinding:
    if not isinstance(request, CandidateRequest) or request.key != CandidateKey(
        request.key.corp_code, "cash", "cash-and-cash-equivalents", request.key.basis, "KRW"
    ):
        raise ValueError("cash_correction_request_required")
    if any(
        source.disclosure.corp_code != request.key.corp_code for source in (original, correction)
    ):
        raise ValueError("request_company_mismatch")
    if request.key.basis not in ("separate", "individual", "consolidated"):
        raise ValueError("supported_native_basis_required")
    SelectedDate(request.run, actual_date)
    a = b = None
    metadata: tuple[NativeReportMetadata, ...] = ()
    observation = None
    relation = None
    comparison = None
    failure: str | None = None
    try:
        if (
            max(source.disclosure.filed_on for source in (original, correction))
            > request.run.execution_date
        ):
            raise ValueError("after_cutoff")
        if web.observed_at.astimezone(ZoneInfo("Asia/Seoul")).date() > request.run.execution_date:
            raise ValueError("observation_after_run")
        observation = observe_correction_web(
            original.disclosure,
            correction.disclosure,
            web.original_main,
            web.correction_main,
            web.errata_html,
            web.observed_at,
            errata_url=web.errata_url,
        )
        documents = []
        for source in (original, correction):
            members = read_archive(source.archive)
            filename = source.disclosure.receipt + ".xml"
            if filename not in members:
                raise ValueError("main_document_missing")
            documents.append(members[filename])
        metadata = tuple(read_native_metadata(document) for document in documents)
        ma, mb = metadata
        if ma.correction is not None or mb.correction is None:
            raise ValueError("native_correction_pair_shape")
        if not all(meta.period_start <= actual_date <= meta.period_end for meta in metadata):
            raise ValueError("comparative_period_not_supported_by_version_v1")
        native_errata = read_errata(mb.correction.text.encode(), native=True)
        observed = observation.errata
        if (
            native_errata.corrected_on,
            native_errata.first_submitted_on,
            native_errata.report_kind,
            native_errata.changes,
        ) != (
            observed.corrected_on,
            observed.first_submitted_on,
            observed.report_kind,
            observed.changes,
        ):
            raise ValueError("native_web_errata_mismatch")
        basis = cast(CashBasis, request.key.basis)
        scope: CashScope = "consolidated" if basis == "consolidated" else "standalone"
        query = CashQuery(request.key.corp_code, actual_date, scope)
        a = inspect_cash_report(
            original.disclosure, query, basis, Decimal(0), original.archive, request.run.executed_at
        )
        b = inspect_cash_report(
            correction.disclosure,
            query,
            basis,
            Decimal(0),
            correction.archive,
            request.run.executed_at,
        )
        va, vb = _version(a, ma, request.key), _version(b, mb, request.key)
        errata_source = CandidateSource(
            correction.disclosure.receipt,
            correction.disclosure.filed_on,
            correction.disclosure.source_url,
            hashlib.sha256(documents[1]).hexdigest(),
            mb.correction.locator + " / " + native_errata.first_submission_locator,
            f"{native_errata.report_kind} / 최초 제출일 {native_errata.first_submitted_on}\n"
            + "\n".join(" | ".join(row) for row in native_errata.changes),
        )
        proof = CorrectionEvidence(
            native_errata.first_submitted_on, errata_source, observation.viewer_relation
        )
        relation = assess_correction(request, va, vb, proof)
        comparison = CorrectionCashComparison(
            relation,
            a.value if isinstance(a.value, CashValue) else None,
            b.value if isinstance(b.value, CashValue) else None,
        )
        failure = comparison.reason
    except (CollectionError, ValueError) as error:
        failure = str(error)
    return NativeCorrectionBinding(
        request,
        actual_date,
        (original, correction),
        a,
        b,
        metadata,
        observation,
        relation,
        comparison,
        failure,
    )
