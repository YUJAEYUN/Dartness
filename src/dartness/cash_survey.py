"""Apply the existing cash query to every provided universe member without hiding omissions."""

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from dartness.cash_contract import CashBasis, CashScope, CashValue
from dartness.cash_report_candidates import StoredCashReport
from dartness.cash_viewer import verify_cash_viewer
from dartness.cash_workbook import write_cash_matches_workbook
from dartness.filing_history import FilingHistory
from dartness.latest_cash import (
    BodyObservation,
    CorrectionPair,
    LatestCashResult,
    query_latest_cash,
)
from dartness.listed_universe import ListedCompany, UniverseSnapshot
from dartness.query_contract import SEOUL, QueryRun


@dataclass(frozen=True)
class CashSurveySources:
    basis: CashBasis
    history: FilingHistory
    reports: tuple[StoredCashReport, ...]
    bodies: tuple[BodyObservation, ...]
    pairs: tuple[CorrectionPair, ...] = ()
    table_section: bytes | None = None


@dataclass(frozen=True)
class CashSourceFailure:
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("source_failure_reason_required")


@dataclass(frozen=True)
class CashSurveyEntry:
    company: ListedCompany
    result: LatestCashResult | None = None
    failure: str | None = None
    skipped: Literal["source_bundle_missing", "company_limit_reached"] | None = None

    def __post_init__(self) -> None:
        if self.failure is not None and not self.failure.strip():
            raise ValueError("company_failure_reason_required")
        if self.skipped not in (None, "source_bundle_missing", "company_limit_reached"):
            raise ValueError("supported_company_skip_required")
        if sum(value is not None for value in (self.result, self.failure, self.skipped)) != 1:
            raise ValueError("exactly_one_company_outcome_required")
        if self.result is not None and self.result.request.key.corp_code != self.company.corp_code:
            raise ValueError("survey_result_company_mismatch")

    @property
    def status(self) -> str:
        if self.result is not None:
            return self.result.status
        return "not_processed" if self.skipped else "needs_review"

    @property
    def reason(self) -> str | None:
        return self.skipped or self.failure or (self.result.reason if self.result else None)

    def to_dict(self) -> dict[str, object]:
        return {
            "corp_code": self.company.corp_code,
            "current_name": self.company.name,
            "market": self.company.market,
            "stock_code": self.company.stock_code,
            "registry_stock_codes": list(self.company.registry_stock_codes),
            "registry_modified_dates": [
                d.isoformat() for d in self.company.registry_modified_dates
            ],
            "status": self.status,
            "reason": self.reason,
            "query_result": self.result.to_dict() if self.result else None,
        }


def _validate_universe(run: QueryRun, universe: UniverseSnapshot) -> None:
    if not isinstance(run, QueryRun) or not isinstance(universe, UniverseSnapshot):
        raise ValueError("typed_universe_and_run_required")
    if universe.execution_date != run.execution_date:
        raise ValueError("survey_universe_date_mismatch")
    times = (universe.observed_from, universe.observed_until)
    if any(
        not isinstance(t, datetime)
        or t.utcoffset() is None
        or t.astimezone(SEOUL).date() != run.execution_date
        for t in times
    ):
        raise ValueError("survey_universe_observation_date_mismatch")
    if not universe.observed_from <= universe.observed_until <= run.executed_at:
        raise ValueError("survey_universe_observation_order")
    if (
        universe.registry_source != "https://opendart.fss.or.kr/api/corpCode.xml"
        or universe.profile_source != "https://opendart.fss.or.kr/api/company.json"
    ):
        raise ValueError("official_universe_source_required")
    companies = universe.companies
    codes = [c.corp_code for c in companies]
    stocks = [c.stock_code for c in companies]
    excluded = universe.excluded_other_corps
    if (
        not companies
        or len(set(codes)) != len(codes)
        or len(set(stocks)) != len(stocks)
        or len(set(excluded)) != len(excluded)
        or set(codes) & set(excluded)
    ):
        raise ValueError("invalid_survey_universe_identity")
    if {c.market for c in companies} != {"Y", "K", "N"}:
        raise ValueError("survey_universe_market_coverage")
    for c in companies:
        if (
            not re.fullmatch(r"[0-9]{8}", c.corp_code)
            or not c.name.strip()
            or not re.fullmatch(r"[0-9A-Z]{6}", c.stock_code)
            or c.stock_code not in c.registry_stock_codes
            or not c.registry_modified_dates
            or any(d > run.execution_date for d in c.registry_modified_dates)
        ):
            raise ValueError("invalid_survey_company")
    profiles = dict(universe.profile_sha256)
    if (
        len(profiles) != len(universe.profile_sha256)
        or set(profiles) != set(codes) | set(excluded)
        or any(not re.fullmatch(r"[0-9]{8}", code) for code in profiles)
        or any(not re.fullmatch(r"[0-9a-f]{64}", digest) for digest in profiles.values())
        or not re.fullmatch(r"[0-9a-f]{64}", universe.registry_sha256)
        or type(universe.requests) is not int
        or universe.requests != 1 + len(profiles)
    ):
        raise ValueError("invalid_survey_universe_provenance")


@dataclass(frozen=True)
class CashSurveyResult:
    run: QueryRun
    universe: UniverseSnapshot
    scope: CashScope
    minimum_krw: Decimal
    max_companies: int
    entries: tuple[CashSurveyEntry, ...]

    def __post_init__(self) -> None:
        _validate_universe(self.run, self.universe)
        if self.run.request.query_type != "cash" or self.scope not in (
            "standalone",
            "consolidated",
        ):
            raise ValueError("cash_survey_request_required")
        if (
            not isinstance(self.minimum_krw, Decimal)
            or not self.minimum_krw.is_finite()
            or self.minimum_krw < 0
        ):
            raise ValueError("nonnegative_exact_minimum_required")
        if type(self.max_companies) is not int or self.max_companies < 1:
            raise ValueError("positive_company_limit_required")
        if sum(e.status != "not_processed" for e in self.entries) > self.max_companies:
            raise ValueError("survey_company_limit_exceeded")
        if {e.company for e in self.entries} != set(self.universe.companies) or len(
            self.entries
        ) != len(self.universe.companies):
            raise ValueError("survey_must_preserve_all_targets_once")
        for entry in self.entries:
            if entry.result is not None and (
                entry.result.request.run != self.run
                or entry.result.minimum_krw != self.minimum_krw
                or entry.result.request.key.basis
                not in (
                    ("separate", "individual") if self.scope == "standalone" else ("consolidated",)
                )
            ):
                raise ValueError("survey_result_request_mismatch")

    @property
    def counts(self) -> dict[str, int]:
        counter = Counter(entry.status for entry in self.entries)
        return {
            status: counter[status]
            for status in ("document_match", "document_non_match", "needs_review", "not_processed")
        }

    @property
    def all_targets_processed(self) -> bool:
        return self.counts["not_processed"] == 0

    @property
    def all_values_verified(self) -> bool:
        return self.all_targets_processed and self.counts["needs_review"] == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "run_scope": "provided_universe_and_captured_reports",
            "query_type": "cash",
            "universe_origin": "provided_opendart_snapshot_metadata",
            "executed_at": self.run.executed_at.isoformat(),
            "mode": self.run.request.mode,
            "requested_as_of": self.run.anchor_date.isoformat(),
            "max_age_months": self.run.request.max_age_months,
            "include_review_requested": self.run.request.include_review,
            "scope": self.scope,
            "minimum_krw": str(self.minimum_krw),
            "max_companies": self.max_companies,
            "target_count": len(self.entries),
            "counts": self.counts,
            "all_targets_processed": self.all_targets_processed,
            "all_values_verified": self.all_values_verified,
            "universe": {
                "execution_date": self.universe.execution_date.isoformat(),
                "observed_from": self.universe.observed_from.isoformat(),
                "observed_until": self.universe.observed_until.isoformat(),
                "registry_sha256": self.universe.registry_sha256,
                "registry_source": self.universe.registry_source,
                "profile_source": self.universe.profile_source,
                "requests": self.universe.requests,
                "profile_sha256": list(self.universe.profile_sha256),
                "excluded_other_corps": list(self.universe.excluded_other_corps),
            },
            "companies": [entry.to_dict() for entry in self.entries],
        }


def _attach_table_link(result: LatestCashResult, source: CashSurveySources) -> LatestCashResult:
    report = result.report
    if report is None:
        return result
    failure: str | None = "table_section_not_supplied"
    payload = source.table_section
    if payload is not None and isinstance(report.value, CashValue):
        try:
            if not isinstance(payload, bytes):
                raise ValueError("table_section_bytes_required")
            mains = tuple(
                b.payload for b in source.bodies if b.receipt == report.disclosure.receipt
            )
            if len(mains) != 1:
                raise ValueError("selected_table_body_required")
            link = verify_cash_viewer(
                report.value, mains[0], lambda url: payload, result.request.run.executed_at
            )
            report = replace(report, viewer_link=link)
            failure = None
        except ValueError as error:
            failure = str(error)
    return replace(result, report=replace(report, viewer_link_failure=failure))


def query_cash_survey(
    run: QueryRun,
    universe: UniverseSnapshot,
    scope: CashScope,
    minimum_krw: Decimal,
    sources: Mapping[str, CashSurveySources | CashSourceFailure],
    *,
    max_companies: int,
) -> CashSurveyResult:
    if (
        not isinstance(run, QueryRun)
        or run.request.query_type != "cash"
        or scope not in ("standalone", "consolidated")
    ):
        raise ValueError("cash_survey_request_required")
    if not isinstance(minimum_krw, Decimal) or not minimum_krw.is_finite() or minimum_krw < 0:
        raise ValueError("nonnegative_exact_minimum_required")
    if type(max_companies) is not int or max_companies < 1:
        raise ValueError("positive_company_limit_required")
    _validate_universe(run, universe)
    if set(sources) - {company.corp_code for company in universe.companies}:
        raise ValueError("unexpected_company_sources")
    allowed = ("separate", "individual") if scope == "standalone" else ("consolidated",)
    entries, attempted = [], 0
    for company in sorted(universe.companies, key=lambda c: c.corp_code):
        source = sources.get(company.corp_code)
        if source is None:
            entry = CashSurveyEntry(company, skipped="source_bundle_missing")
        elif attempted >= max_companies:
            entry = CashSurveyEntry(company, skipped="company_limit_reached")
        else:
            attempted += 1
            if isinstance(source, CashSourceFailure):
                entry = CashSurveyEntry(company, failure=source.reason)
            elif not isinstance(source, CashSurveySources):
                raise ValueError("typed_survey_sources_required")
            elif source.basis not in allowed:
                entry = CashSurveyEntry(company, failure="basis_scope_mismatch")
            else:
                result = query_latest_cash(
                    run,
                    company.corp_code,
                    source.basis,
                    minimum_krw,
                    source.history,
                    source.reports,
                    source.bodies,
                    source.pairs,
                )
                entry = CashSurveyEntry(company, result=_attach_table_link(result, source))
        entries.append(entry)
    return CashSurveyResult(run, universe, scope, minimum_krw, max_companies, tuple(entries))


def write_cash_survey_workbook(result: CashSurveyResult, output: Path) -> None:
    result = replace(result)
    counts = result.counts
    rows = tuple(
        (entry.company.name, entry.result.report)
        for entry in result.entries
        if entry.result is not None
        and entry.result.report is not None
        and entry.status == "document_match"
    )
    summary = (
        f"대상 {len(result.entries)} · 충족 {counts['document_match']} · "
        f"미충족 {counts['document_non_match']} · 확인 필요 {counts['needs_review']} · "
        f"미처리 {counts['not_processed']} · 개발용(전수 검증 미완료)"
    )
    messages = {
        "source_bundle_missing": "조회할 공시 자료가 준비되지 않았습니다.",
        "company_limit_reached": "이번 실행의 처리 한도에 도달했습니다.",
        "basis_scope_mismatch": "요청한 재무 범위와 준비된 자료의 범위가 다릅니다.",
        "archive_hash_mismatch": "저장된 원문 파일이 수집 기록과 다릅니다.",
    }
    review_rows = None
    if result.run.request.include_review:
        review_rows = tuple(
            (
                entry.company.name,
                "미처리" if entry.skipped else "확인 필요",
                messages.get(
                    entry.reason or "",
                    "공시 원문의 금액·날짜·단위·정정 근거를 확인해야 합니다.",
                ),
            )
            for entry in result.entries
            if entry.status in ("not_processed", "needs_review")
        )
    write_cash_matches_workbook(
        rows,
        output,
        run=result.run,
        minimum_krw=result.minimum_krw,
        summary=summary,
        review_rows=review_rows,
    )
