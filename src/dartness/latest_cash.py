"""Select the latest validated periodic source at the requested financial date."""

import hashlib
import re
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from dartness.cash_contract import CashBasis, CashQuery, CashScope, CashValue
from dartness.cash_report import inspect_cash_report
from dartness.cash_report_candidates import (
    ReportCashCandidates,
    StoredCashReport,
    read_cash_candidates,
)
from dartness.cash_report_result import CashReportResult
from dartness.correction_binding import CorrectionWebInputs, bind_native_correction
from dartness.correction_html import read_body_history
from dartness.dart_smoke import CollectionError, read_archive
from dartness.disclosure_candidate import CandidateKey, CandidateRequest, DisclosureCandidate
from dartness.disclosure_list import Disclosure
from dartness.filing_history import FilingHistory
from dartness.native_report import PERIODIC_KINDS, NativeReportMetadata, read_native_metadata
from dartness.query_contract import QueryRun, SelectedDate, select_date


@dataclass(frozen=True)
class BodyObservation:
    receipt: str
    payload: bytes
    observed_at: datetime


@dataclass(frozen=True)
class CorrectionPair:
    original_receipt: str
    correction_receipt: str
    web: CorrectionWebInputs


@dataclass(frozen=True)
class LatestCashResult:
    request: CandidateRequest
    history: FilingHistory
    sources: tuple[ReportCashCandidates, ...]
    report: CashReportResult | None
    reason: str | None
    validity: dict[str, object] | None

    @property
    def status(self) -> str:
        return self.report.status if self.report else "needs_review"

    def to_dict(self) -> dict[str, object]:
        return {
            "run_scope": "captured_history_periodic_reports",
            "status": self.status,
            "reason": self.reason,
            "selection_policy": "latest_valid_publication_at_selected_financial_date",
            "history": self.history.to_dict(),
            "sources": [source.to_dict() for source in self.sources],
            "validity": self.validity,
            "latest_correction_verified": self.report is not None,
            "selected_receipt": self.report.disclosure.receipt if self.report else None,
            "selected_report": self.report.to_dict() if self.report else None,
        }


def _metadata(report: StoredCashReport) -> NativeReportMetadata:
    files = read_archive(report.archive)
    name = report.disclosure.receipt + ".xml"
    if name not in files:
        raise ValueError("main_document_missing")
    meta = read_native_metadata(files[name], periodic=True)
    if meta.period_end > report.disclosure.filed_on:
        raise ValueError("report_period_after_publication")
    kind = PERIODIC_KINDS[meta.report_code]
    title = re.fullmatch(
        r"(?:\[기재정정\])?" + kind + r" \(([0-9]{4})\.([0-9]{2})\)",
        report.disclosure.report_name,
    )
    if title is None or (int(title[1]), int(title[2])) != (
        meta.period_end.year,
        meta.period_end.month,
    ):
        raise ValueError("listing_native_report_period_mismatch")
    return meta


def _periodic_rows(items: tuple[Disclosure, ...]) -> tuple[Disclosure, ...]:
    if any(
        any(word in row.report_name for word in ("철회", "정정명령", "제출요구")) for row in items
    ):
        raise ValueError("withdrawal_or_order_requires_review")
    rows = tuple(
        row for row in items if any(kind in row.report_name for kind in PERIODIC_KINDS.values())
    )
    if any(
        re.fullmatch(
            r"(?:\[기재정정\])?(?:사업|반기|분기)보고서 \([0-9]{4}\.[0-9]{2}\)", row.report_name
        )
        is None
        for row in rows
    ):
        raise ValueError("unsupported_periodic_filing")
    return rows


def _validity(
    request: CandidateRequest,
    chosen: DisclosureCandidate,
    reports: dict[str, StoredCashReport],
    metadata: dict[str, NativeReportMetadata],
    bodies: tuple[BodyObservation, ...],
    pairs: tuple[CorrectionPair, ...],
) -> dict[str, object]:
    receipt = chosen.source.document_id.removesuffix(".xml")
    stored, meta = reports[receipt], metadata[receipt]
    family = tuple(
        report
        for key, report in reports.items()
        if (metadata[key].report_code, metadata[key].period_start, metadata[key].period_end)
        == (meta.report_code, meta.period_start, meta.period_end)
    )
    proofs = tuple(body for body in bodies if body.receipt == receipt)
    if len(proofs) != 1:
        raise ValueError("selected_body_observation_required")
    proof = proofs[0]
    if (
        not isinstance(proof.observed_at, datetime)
        or proof.observed_at.utcoffset() is None
        or proof.observed_at > request.run.executed_at
        or proof.observed_at.astimezone(ZoneInfo("Asia/Seoul")).date() != request.run.execution_date
    ):
        raise ValueError("body_observation_execution_day_required")
    entries = read_body_history(
        proof.payload, request.key.corp_code, receipt, report_kind=PERIODIC_KINDS[meta.report_code]
    )
    expected = {(r.disclosure.receipt, r.disclosure.filed_on) for r in family}
    if {(e.receipt, e.filed_on) for e in entries} != expected:
        raise ValueError("body_listing_history_mismatch")
    if any(e.is_correction != (metadata[e.receipt].correction is not None) for e in entries):
        raise ValueError("body_native_correction_mismatch")
    if stored.disclosure.filed_on != max(e.filed_on for e in entries):
        raise ValueError("selected_version_not_latest_in_family")
    audit: dict[str, object] = {
        "scope": "selected_periodic_family_in_captured_history",
        "body_response_sha256": hashlib.sha256(proof.payload).hexdigest(),
        "body_observed_at": proof.observed_at.isoformat(),
        "family_receipts": [e.receipt for e in entries],
    }
    if len(family) == 1:
        if (
            meta.correction is not None
            or "정" in stored.disclosure.remarks
            or "정정" in stored.disclosure.report_name
        ):
            raise ValueError("correction_unresolved")
        return audit
    if len(family) != 2 or meta.report_code != "11011" or meta.correction is None:
        raise ValueError("unsupported_correction_family")
    originals = tuple(r for r in family if metadata[r.disclosure.receipt].correction is None)
    if len(originals) != 1:
        raise ValueError("original_version_required")
    original = originals[0]
    links = tuple(
        p
        for p in pairs
        if (p.original_receipt, p.correction_receipt) == (original.disclosure.receipt, receipt)
    )
    if len(links) != 1:
        raise ValueError("correction_pair_evidence_required")
    binding = bind_native_correction(request, chosen.actual_date, original, stored, links[0].web)
    if binding.status not in ("amounts_equal", "amounts_differ") or binding.observation is None:
        raise ValueError("correction_binding_unresolved:" + str(binding.failure))
    if {(e.receipt, e.filed_on) for e in binding.observation.correction_history} != expected:
        raise ValueError("correction_family_history_mismatch")
    if "정" in stored.disclosure.remarks:
        raise ValueError("further_correction_unresolved")
    audit["correction_binding"] = binding.to_dict()
    return audit


def query_latest_cash(
    run: QueryRun,
    corp_code: str,
    basis: CashBasis,
    minimum_krw: Decimal,
    history: FilingHistory,
    reports: tuple[StoredCashReport, ...],
    bodies: tuple[BodyObservation, ...],
    pairs: tuple[CorrectionPair, ...] = (),
) -> LatestCashResult:
    if run.request.query_type != "cash" or basis not in ("separate", "individual", "consolidated"):
        raise ValueError("explicit_cash_run_and_basis_required")
    if not isinstance(minimum_krw, Decimal) or not minimum_krw.is_finite() or minimum_krw < 0:
        raise ValueError("nonnegative_exact_minimum_required")
    request = CandidateRequest(
        run, CandidateKey(corp_code, "cash", "cash-and-cash-equivalents", basis, "KRW")
    )
    sources: list[ReportCashCandidates] = []
    report = None
    validity = None
    reason = None
    try:
        if history.request.corp_code != corp_code:
            raise ValueError("history_company_mismatch")
        listed = _periodic_rows(history.replay(run.executed_at).items)
        archives = {source.disclosure.receipt: source for source in reports}
        if len(archives) != len(reports) or set(archives) != {row.receipt for row in listed}:
            raise ValueError("periodic_source_set_incomplete_or_duplicate")
        if any(archives[row.receipt].disclosure != row for row in listed):
            raise ValueError("source_listing_metadata_mismatch")
        metadata = {receipt: _metadata(source) for receipt, source in archives.items()}
        for receipt, source in archives.items():
            candidates = read_cash_candidates(
                source,
                request.key,
                basis,
                run.executed_at,
                report_code=metadata[receipt].report_code,
            )
            sources.append(candidates)
            if candidates.failure:
                raise ValueError("source_incomplete:" + candidates.failure)
            if any(c.actual_date > metadata[receipt].period_end for c in candidates.candidates):
                raise ValueError("financial_column_after_report_period")
        all_candidates = tuple(c for source in sources for c in source.candidates)
        selected_date = select_date(run, (c.actual_date for c in all_candidates))
        if not isinstance(selected_date, SelectedDate):
            raise ValueError("period_unavailable")
        eligible = tuple(c for c in all_candidates if c.actual_date == selected_date.actual_date)
        latest_day = max(c.source.published_on for c in eligible)
        latest = tuple(dict.fromkeys(c for c in eligible if c.source.published_on == latest_day))
        if len(latest) != 1:
            raise ValueError("same_day_publication_ambiguous")
        chosen = latest[0]
        validity = _validity(request, chosen, archives, metadata, bodies, pairs)
        receipt = chosen.source.document_id.removesuffix(".xml")
        selected = archives[receipt]
        scope: CashScope = "consolidated" if basis == "consolidated" else "standalone"
        result = inspect_cash_report(
            selected.disclosure,
            CashQuery(corp_code, chosen.actual_date, scope),
            basis,
            minimum_krw,
            selected.archive,
            run.executed_at,
            report_code=metadata[receipt].report_code,
        )
        if not isinstance(result.value, CashValue) or result.failure:
            raise ValueError("selected_source_unavailable")
        report = replace(result, request_run=run)
    except (ValueError, CollectionError) as error:
        reason = str(error)
    return LatestCashResult(request, history, tuple(sources), report, reason, validity)
