"""Connect supplied real report periods to the existing snapshot/date/candidate contracts."""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from decimal import Decimal

from dartness.cash_contract import CashBasis, CashQuery, CashScope
from dartness.cash_report import inspect_cash_report
from dartness.cash_report_candidates import (
    ReportCashCandidates,
    StoredCashReport,
    read_cash_candidates,
)
from dartness.cash_report_result import CashReportResult
from dartness.disclosure_candidate import (
    CandidateKey,
    CandidateRequest,
    CandidateSelection,
    select_candidate,
)
from dartness.query_contract import QueryRun


@dataclass(frozen=True)
class CashSnapshotResult:
    request: CandidateRequest
    minimum_krw: Decimal
    sources: tuple[ReportCashCandidates, ...]
    selection: CandidateSelection
    report: CashReportResult | None
    reason: str | None

    @property
    def status(self) -> str:
        return self.report.status if self.report is not None else "needs_review"

    def to_dict(self) -> dict[str, object]:
        run = self.request.run
        return {
            "run_scope": "provided_reports_only",
            "latest_correction_verified": False,
            "metadata_origin": "supplied_disclosure_records",
            "basis_origin": "supplied_upstream",
            "status": self.status,
            "reason": self.reason,
            "query_type": "cash",
            "corp_code": self.request.key.corp_code,
            "basis": self.request.key.basis,
            "mode": run.request.mode,
            "max_age_months": run.request.max_age_months,
            "include_review_requested": run.request.include_review,
            "requested_as_of": run.anchor_date.isoformat(),
            "earliest_date": run.earliest_date.isoformat(),
            "executed_at": run.executed_at.isoformat(),
            "minimum_krw": str(self.minimum_krw),
            "candidate_selection_status": self.selection.status,
            "candidate_selection_reason": self.selection.reason,
            "sources": [source.to_dict() for source in self.sources],
            "candidates": [
                {
                    "corp_code": candidate.key.corp_code,
                    "query_type": candidate.key.query_type,
                    "item_key": candidate.key.item_key,
                    "basis": candidate.key.basis,
                    "currency": candidate.key.currency,
                    "actual_date": candidate.actual_date.isoformat(),
                    "document_id": candidate.source.document_id,
                    "published_on": candidate.source.published_on.isoformat(),
                    "source_url": candidate.source.source_url,
                    "document_sha256": candidate.source.document_sha256,
                    "locator": candidate.source.locator,
                    "context": candidate.source.context,
                }
                for candidate in self.selection.candidates
            ],
            "selected_report": self.report.to_dict() if self.report else None,
        }


def query_cash_reports(
    run: QueryRun,
    corp_code: str,
    basis: CashBasis,
    minimum_krw: Decimal,
    reports: Iterable[StoredCashReport],
) -> CashSnapshotResult:
    """Do not replace ambiguous/corrupt/newer inputs with a convenient older report."""
    if not isinstance(run, QueryRun) or run.request.query_type != "cash":
        raise ValueError("cash_query_run_required")
    if basis not in ("separate", "individual", "consolidated"):
        raise ValueError("explicit_cash_basis_required")
    if not isinstance(minimum_krw, Decimal) or not minimum_krw.is_finite() or minimum_krw < 0:
        raise ValueError("nonnegative_exact_minimum_required")
    key = CandidateKey(corp_code, "cash", "cash-and-cash-equivalents", basis, "KRW")
    request = CandidateRequest(run, key)
    sources = []
    for report in reports:
        if not isinstance(report, StoredCashReport):
            raise ValueError("stored_cash_report_required")
        if report.disclosure.corp_code != corp_code:
            raise ValueError("request_company_mismatch")
        if report.disclosure.filed_on > run.execution_date:
            sources.append(ReportCashCandidates(report, (), excluded_after_cutoff=True))
        else:
            sources.append(read_cash_candidates(report, key, basis, run.executed_at))
    selection = select_candidate(request, (c for source in sources for c in source.candidates))
    selected_report = None
    reason: str | None = selection.reason
    if any(source.failure is not None for source in sources):
        reason = "source_incomplete"
    elif selection.candidate is not None:
        unresolved = any(
            not source.excluded_after_cutoff
            and (
                "정정" in source.report.disclosure.report_name
                or "정" in source.report.disclosure.remarks
            )
            for source in sources
        )
        if unresolved:
            reason = "correction_unresolved"
        else:
            chosen = selection.candidate
            stored = next(source.report for source in sources if chosen in source.candidates)
            scope: CashScope = "consolidated" if basis == "consolidated" else "standalone"
            selected_report = inspect_cash_report(
                stored.disclosure,
                CashQuery(corp_code, chosen.actual_date, scope),
                basis,
                minimum_krw,
                stored.archive,
                run.executed_at,
            )
            selected_report = replace(selected_report, request_run=run)
    return CashSnapshotResult(
        request, minimum_krw, tuple(sources), selection, selected_report, reason
    )
