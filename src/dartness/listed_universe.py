"""Observe current OpenDART-listed corporations and connect their filings.

See docs/specs/listed-universe.md. This is not historical membership or fact extraction.
"""

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime

from dartness.dart_smoke import CollectionError, Fetch, _api_status, _xml, read_archive
from dartness.disclosure_list import Disclosure, ListRequest, collect_list
from dartness.query_contract import SEOUL

type Clock = Callable[[], datetime]


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ListedCompany:
    corp_code: str
    name: str
    market: str
    stock_code: str
    registry_stock_codes: tuple[str, ...]
    registry_modified_dates: tuple[date, ...]


@dataclass(frozen=True)
class UniverseSnapshot:
    execution_date: date
    observed_from: datetime
    observed_until: datetime
    registry_sha256: str
    profile_sha256: tuple[tuple[str, str], ...]
    companies: tuple[ListedCompany, ...]
    excluded_other_corps: tuple[str, ...]
    requests: int
    registry_source: str = "https://opendart.fss.or.kr/api/corpCode.xml"
    profile_source: str = "https://opendart.fss.or.kr/api/company.json"


@dataclass(frozen=True)
class ListedFilings:
    executed_at: datetime
    universe: UniverseSnapshot
    search: ListRequest
    items: tuple[Disclosure, ...]
    no_filings: tuple[str, ...]
    outside_filings_count: int
    requests: int
    finished_at: datetime


def _execution_day(executed_at: datetime) -> date:
    if not isinstance(executed_at, datetime) or executed_at.utcoffset() is None:
        raise ValueError("explicit_execution_time_required")
    try:
        return executed_at.astimezone(SEOUL).date()
    except (OverflowError, ValueError):
        raise ValueError("invalid_execution_time") from None


def _observe(executed_at: datetime, clock: Clock, previous: datetime | None = None) -> datetime:
    value = clock()
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise CollectionError("invalid_observation_clock")
    try:
        observed = value.astimezone(UTC)
        day = observed.astimezone(SEOUL).date()
    except (OverflowError, ValueError):
        raise CollectionError("invalid_observation_clock") from None
    if day != _execution_day(executed_at):
        raise CollectionError("universe_date_changed")
    if observed < executed_at or (previous is not None and observed < previous):
        raise CollectionError("observation_clock_reversed")
    return observed


def _text(value: object, pattern: str = "") -> str:
    if not isinstance(value, str) or not value.strip():
        raise CollectionError("invalid_universe_field")
    value = value.strip()
    if pattern and not re.fullmatch(pattern, value):
        raise CollectionError("invalid_universe_field")
    return value


def _registry(payload: bytes, day: date) -> dict[str, set[tuple[str, date]]]:
    files = read_archive(payload)
    xml_files = [body for name, body in files.items() if name.lower().endswith(".xml")]
    if len(xml_files) != 1 or len(files) != 1:
        raise CollectionError("invalid_registry_archive")
    root = _xml(xml_files[0])
    rows = root.findall("list")
    if root.tag != "result" or not rows:
        raise CollectionError("empty_registry")
    candidates: dict[str, set[tuple[str, date]]] = {}
    owners: dict[str, str] = {}
    for row in rows:
        code = _text(row.findtext("corp_code"), r"[0-9]{8}")
        stock = row.findtext("stock_code", "").strip()
        if not stock:
            continue
        stock = _text(stock, r"[0-9A-Z]{6}")
        modified = _text(row.findtext("modify_date"), r"[0-9]{8}")
        try:
            changed_on = date.fromisoformat(f"{modified[:4]}-{modified[4:6]}-{modified[6:]}")
        except ValueError:
            raise CollectionError("invalid_registry_date") from None
        if changed_on > day:
            raise CollectionError("future_registry_date")
        if stock in owners and owners[stock] != code:
            raise CollectionError("ambiguous_registry_stock")
        owners[stock] = code
        candidates.setdefault(code, set()).add((stock, changed_on))
    if not candidates:
        raise CollectionError("empty_listed_candidates")
    return candidates


def _profile(payload: bytes, code: str, stocks: set[str]) -> tuple[str, str, str]:
    try:
        result: object = json.loads(payload)
    except (ValueError, UnicodeError):
        raise CollectionError("invalid_company_json") from None
    if not isinstance(result, dict):
        raise CollectionError("invalid_company_response")
    _api_status(result.get("status"))
    if "corp_code" in result and result["corp_code"] != code:
        raise CollectionError("company_code_mismatch")
    market = _text(result.get("corp_cls"), r"[YKNE]")
    if market == "E":
        return market, "", ""
    name = _text(result.get("corp_name"))
    stock = _text(result.get("stock_code"), r"[0-9A-Z]{6}")
    if stock not in stocks:
        raise CollectionError("company_registry_mismatch")
    return market, name, stock


def collect_universe(
    executed_at: datetime, *, max_requests: int, fetch: Fetch, clock: Clock = _now
) -> UniverseSnapshot:
    if type(max_requests) is not int or max_requests < 1:
        raise ValueError("invalid_universe_request")
    execution_date = _execution_day(executed_at)
    started = _observe(executed_at, clock)
    payload = fetch("corpCode.xml", {})
    calls = 1
    candidates = _registry(payload, execution_date)
    if 1 + len(candidates) > max_requests:
        raise CollectionError("universe_request_budget")
    companies, excluded, hashes = [], [], []
    previous_time = started
    for code, registrations in sorted(candidates.items()):
        previous_time = _observe(executed_at, clock, previous_time)
        stocks = {stock for stock, _ in registrations}
        body = fetch("company.json", {"corp_code": code})
        calls += 1
        hashes.append((code, hashlib.sha256(body).hexdigest()))
        market, name, stock = _profile(body, code, stocks)
        if market == "E":
            excluded.append(code)
        else:
            companies.append(
                ListedCompany(
                    code,
                    name,
                    market,
                    stock,
                    tuple(sorted(stocks)),
                    tuple(sorted({modified for _, modified in registrations})),
                )
            )
    finished = _observe(executed_at, clock, previous_time)
    if {company.market for company in companies} != {"Y", "K", "N"}:
        raise CollectionError("incomplete_market_coverage")
    return UniverseSnapshot(
        execution_date,
        started,
        finished,
        hashlib.sha256(payload).hexdigest(),
        tuple(hashes),
        tuple(companies),
        tuple(excluded),
        calls,
    )


def collect_listed_filings(
    executed_at: datetime,
    search: ListRequest,
    *,
    max_requests: int,
    fetch: Fetch,
    clock: Clock = _now,
) -> ListedFilings:
    if not isinstance(search, ListRequest):
        raise ValueError("invalid_listed_search")
    if search.end > _execution_day(executed_at) or search.corp_code or search.corp_cls:
        raise ValueError("invalid_listed_search_scope")
    universe = collect_universe(executed_at, max_requests=max_requests, fetch=fetch, clock=clock)
    remaining = max_requests - universe.requests
    if remaining < 1:
        raise CollectionError("listing_request_budget")
    previous_time = universe.observed_until

    def dated_fetch(endpoint: str, params: dict[str, str]) -> bytes:
        nonlocal previous_time
        previous_time = _observe(executed_at, clock, previous_time)
        return fetch(endpoint, params)

    listing = collect_list(search, max_requests=remaining, fetch=dated_fetch)
    finished = _observe(executed_at, clock, previous_time)
    codes = {company.corp_code for company in universe.companies}
    matched = tuple(item for item in listing.items if item.corp_code in codes)
    active = {item.corp_code for item in matched}
    return ListedFilings(
        executed_at,
        universe,
        search,
        matched,
        tuple(sorted(codes - active)),
        len(listing.items) - len(matched),
        universe.requests + listing.requests,
        finished,
    )
