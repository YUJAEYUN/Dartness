"""Connect the complete current universe to a bounded cash-source pilot; no implicit live run."""

import json
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from dartness.cash_contract import CashBasis, CashScope
from dartness.cash_report_candidates import StoredCashReport
from dartness.cash_survey import (
    CashSourceFailure,
    CashSurveyResult,
    CashSurveySources,
    query_cash_survey,
)
from dartness.cash_viewer import balance_viewer_url
from dartness.collection_bundle import load_history
from dartness.dart_history import collect_history
from dartness.dart_receipts import collect_receipts
from dartness.dart_smoke import CollectionError, Fetch
from dartness.disclosure_list import ListRequest
from dartness.latest_cash import BodyObservation, query_latest_cash
from dartness.listed_universe import Clock, ListedCompany, collect_universe
from dartness.query_contract import QueryRun, SnapshotRequest


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class UniverseCashPlan:
    request: SnapshotRequest
    scope: CashScope
    minimum_krw: Decimal
    history_start: date
    max_api_requests: int
    max_web_requests: int
    max_companies: int
    max_reports_per_company: int
    basis_by_corp: tuple[tuple[str, CashBasis], ...] = ()
    target_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.request.query_type != "cash" or self.scope not in ("standalone", "consolidated"):
            raise ValueError("cash_plan_required")
        if (
            not isinstance(self.minimum_krw, Decimal)
            or not self.minimum_krw.is_finite()
            or self.minimum_krw < 0
            or type(self.history_start) is not date
        ):
            raise ValueError("exact_cash_amount_and_history_start_required")
        for value, upper in (
            (self.max_api_requests, 5000),
            (self.max_web_requests, 100),
            (self.max_companies, 10),
            (self.max_reports_per_company, 8),
        ):
            if type(value) is not int or not 1 <= value <= upper:
                raise ValueError("invalid_universe_cash_budget")
        if (
            len(set(self.target_codes)) != len(self.target_codes)
            or any(not re.fullmatch(r"[0-9]{8}", code) for code in self.target_codes)
            or len(self.target_codes) > self.max_companies
        ):
            raise ValueError("invalid_explicit_targets")
        bases = dict(self.basis_by_corp)
        if len(bases) != len(self.basis_by_corp) or any(
            not re.fullmatch(r"[0-9]{8}", code)
            or basis not in ("separate", "individual", "consolidated")
            for code, basis in self.basis_by_corp
        ):
            raise ValueError("invalid_confirmed_bases")


@dataclass
class _Budget:
    fetch: Fetch
    web: Callable[[str], bytes]
    api_limit: int
    web_limit: int
    api_calls: int = 0
    web_calls: int = 0

    def api(self, endpoint: str, params: dict[str, str]) -> bytes:
        if self.api_calls >= self.api_limit:
            raise CollectionError("universe_cash_api_budget")
        self.api_calls += 1
        return self.fetch(endpoint, params)

    def page(self, url: str) -> bytes:
        if self.web_calls >= self.web_limit:
            raise ValueError("universe_cash_web_budget")
        self.web_calls += 1
        return self.web(url)


@dataclass(frozen=True)
class UniverseCashResult:
    survey: CashSurveyResult
    selected_codes: tuple[str, ...]
    api_requests: int
    web_requests: int
    collected_sources: tuple[tuple[str, CashSurveySources], ...] = field(repr=False)
    table_failures: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "run_scope": "current_opendart_universe_with_bounded_source_collection",
            "selected_codes": list(self.selected_codes),
            "api_requests": self.api_requests,
            "web_requests": self.web_requests,
            "table_failures": dict(self.table_failures),
            "survey": self.survey.to_dict(),
        }


def _collect_sources(
    company: ListedCompany,
    basis: CashBasis,
    plan: UniverseCashPlan,
    budget: _Budget,
    clock: Clock,
    execution_date: date,
) -> tuple[CashSurveySources, str | None]:
    initial = QueryRun(plan.request, clock())
    if initial.execution_date != execution_date:
        raise ValueError("universe_cash_execution_day_changed")
    if plan.history_start > initial.execution_date:
        raise ValueError("history_start_after_execution")
    manifest, files = collect_history(
        budget.api, ListRequest(plan.history_start, initial.execution_date, company.corp_code)
    )
    with tempfile.TemporaryDirectory(prefix="dartness-cash-source-") as temp:
        root = Path(temp)
        for name, payload in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False))
        history, rows = load_history(root, clock())
    periodic = tuple(
        r
        for r in rows
        if any(kind in r.report_name for kind in ("사업보고서", "반기보고서", "분기보고서"))
    )
    if not periodic:
        raise ValueError("no_periodic_sources_in_captured_history")
    if len(periodic) > plan.max_reports_per_company:
        raise ValueError("company_report_budget_exceeded")
    reports: list[StoredCashReport] = []
    for offset in range(0, len(periodic), 2):
        chunk = periodic[offset : offset + 2]
        _, archives = collect_receipts(budget.api, [r.receipt for r in chunk])
        reports.extend(StoredCashReport(r, archives[f"{r.receipt}/document.zip"]) for r in chunk)
    bodies = tuple(BodyObservation(r.receipt, budget.page(r.source_url), clock()) for r in periodic)
    provisional = QueryRun(plan.request, clock())
    choice = query_latest_cash(
        provisional, company.corp_code, basis, plan.minimum_krw, history, tuple(reports), bodies
    )
    table = None
    failure = None
    if choice.report is not None:
        try:
            main = next(b.payload for b in bodies if b.receipt == choice.report.disclosure.receipt)
            table = budget.page(
                balance_viewer_url(main, choice.report.disclosure.receipt, company.corp_code, basis)
            )
        except ValueError as error:
            failure = str(error)
    return CashSurveySources(basis, history, tuple(reports), bodies, table_section=table), failure


def collect_universe_cash(
    plan: UniverseCashPlan,
    *,
    fetch: Fetch,
    web: Callable[[str], bytes],
    clock: Clock = _now,
) -> UniverseCashResult:
    """Caller explicitly supplies providers and budgets; constructing a plan performs no I/O."""
    plan = replace(plan)
    initial = QueryRun(plan.request, clock())
    if plan.history_start > initial.execution_date:
        raise ValueError("history_start_after_execution")
    budget = _Budget(fetch, web, plan.max_api_requests, plan.max_web_requests)
    universe = collect_universe(
        initial.executed_at, max_requests=plan.max_api_requests, fetch=budget.api, clock=clock
    )
    codes = {c.corp_code for c in universe.companies}
    bases = dict(plan.basis_by_corp)
    if (set(plan.target_codes) | set(bases)) - codes:
        raise ValueError("target_or_basis_company_outside_current_universe")
    selected = (
        tuple(sorted(plan.target_codes))
        if plan.target_codes
        else tuple(sorted(codes)[: plan.max_companies])
    )
    allowed = ("separate", "individual") if plan.scope == "standalone" else ("consolidated",)
    sources: dict[str, CashSurveySources | CashSourceFailure] = {}
    table_failures: list[tuple[str, str]] = []
    for company in sorted(universe.companies, key=lambda c: c.corp_code):
        if company.corp_code not in selected:
            continue
        basis = bases.get(company.corp_code)
        if basis is None or basis not in allowed:
            sources[company.corp_code] = CashSourceFailure(
                "basis_not_confirmed_for_requested_scope"
            )
            continue
        try:
            source, failure = _collect_sources(
                company, basis, plan, budget, clock, initial.execution_date
            )
            sources[company.corp_code] = source
            if failure:
                table_failures.append((company.corp_code, failure))
        except (ValueError, CollectionError) as error:
            sources[company.corp_code] = CashSourceFailure(str(error))
    run = QueryRun(plan.request, clock())
    if run.execution_date != initial.execution_date:
        raise ValueError("universe_cash_execution_day_changed")
    survey = query_cash_survey(
        run, universe, plan.scope, plan.minimum_krw, sources, max_companies=len(selected)
    )
    survey = replace(
        survey,
        entries=tuple(
            replace(e, skipped="company_limit_reached")
            if e.company.corp_code not in selected
            else e
            for e in survey.entries
        ),
    )
    return UniverseCashResult(
        survey,
        selected,
        budget.api_calls,
        budget.web_calls,
        tuple((c, s) for c, s in sources.items() if isinstance(s, CashSurveySources)),
        tuple(table_failures),
    )
