"""Synthetic registry/profile/list integration, not a live listing-membership evaluation."""

import hashlib
import io
import json
import zipfile
from datetime import UTC, date, datetime, timedelta

import pytest

from dartness.dart_smoke import CollectionError
from dartness.disclosure_list import ListRequest
from dartness.listed_universe import collect_listed_filings, collect_universe
from dartness.query_contract import QueryRun, SnapshotRequest

EXECUTED = datetime(2026, 11, 25, 0, tzinfo=UTC)
NOW = EXECUTED + timedelta(minutes=1)
REGISTRATIONS = [
    ("00000001", "100001", "20261124"),
    ("00000002", "200002", "20261124"),
    ("00000003", "300003", "20261124"),
]


def archive(rows: list[tuple[str, str, str]]) -> bytes:
    xml = (
        "<result>"
        + "".join(
            f"<list><corp_code>{code}</corp_code><corp_name>이전 이름</corp_name>"
            f"<stock_code>{stock}</stock_code><modify_date>{modified}</modify_date></list>"
            for code, stock, modified in rows
        )
        + "</result>"
    )
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w") as file:
        file.writestr("CORPCODE.xml", xml.encode())
    return result.getvalue()


def profile(market: str, stock: str) -> bytes:
    return json.dumps(
        {
            "status": "000",
            "corp_name": "현재 이름",
            "corp_cls": market,
            "stock_code": stock,
            "ceo_nm": "not retained",
            "adres": "not retained",
        }
    ).encode()


def filing(code: str, index: int) -> dict[str, object]:
    return {
        "corp_code": code,
        "corp_name": "과거 이름",
        "corp_cls": "E",
        "stock_code": "",
        "rcept_no": f"20261124{index:06d}",
        "rcept_dt": "20261124",
        "report_nm": "합성 공시",
    }


def listing(rows: list[dict[str, object]]) -> bytes:
    return json.dumps(
        {
            "status": "000",
            "page_no": 1,
            "page_count": 100,
            "total_count": len(rows),
            "total_page": int(bool(rows)),
            "list": rows,
        }
    ).encode()


class FakeDart:
    def __init__(self) -> None:
        self.registry = archive(REGISTRATIONS)
        self.profiles = {
            "00000001": profile("Y", "100001"),
            "00000002": profile("K", "200002"),
            "00000003": profile("N", "300003"),
        }
        self.filings = listing([filing("00000001", 1), filing("00000099", 2)])
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, endpoint: str, params: dict[str, str]) -> bytes:
        self.calls.append((endpoint, params.copy()))
        if endpoint == "corpCode.xml":
            return self.registry
        if endpoint == "company.json":
            return self.profiles[params["corp_code"]]
        if endpoint == "list.json":
            return self.filings
        raise AssertionError("unexpected endpoint")


def search() -> ListRequest:
    return ListRequest(date(2026, 11, 1), date(2026, 11, 25), disclosure_type="D")


def test_current_membership_preserves_prior_market_filings_and_no_filings_companies() -> None:
    fetch = FakeDart()
    result = collect_listed_filings(
        EXECUTED, search(), max_requests=5, fetch=fetch, clock=lambda: NOW
    )
    assert [(c.corp_code, c.market) for c in result.universe.companies] == [
        ("00000001", "Y"),
        ("00000002", "K"),
        ("00000003", "N"),
    ]
    assert [f.corp_code for f in result.items] == ["00000001"]
    assert (
        result.items[0].corp_cls == "E"
    )  # Historical evidence is not rewritten to today's market.
    assert result.no_filings == ("00000002", "00000003")
    assert result.outside_filings_count == 1
    assert result.requests == len(fetch.calls) == 5
    params = fetch.calls[-1][1]
    assert "corp_code" not in params and "corp_cls" not in params
    assert params["pblntf_ty"] == "D"
    assert params["last_reprt_at"] == "N"


def test_hashes_dates_and_current_name_are_preserved_without_unneeded_profile_fields() -> None:
    fetch = FakeDart()
    result = collect_universe(EXECUTED, max_requests=4, fetch=fetch, clock=lambda: NOW)
    assert result.registry_sha256 == hashlib.sha256(fetch.registry).hexdigest()
    assert (
        dict(result.profile_sha256)["00000001"]
        == hashlib.sha256(fetch.profiles["00000001"]).hexdigest()
    )
    assert result.execution_date == date(2026, 11, 25)
    assert result.observed_from == result.observed_until == NOW
    assert result.companies[0].registry_modified_dates == (date(2026, 11, 24),)
    assert result.companies[0].name == "현재 이름"
    assert "not retained" not in repr(result)


def test_same_corporation_is_queried_once_and_other_current_market_is_excluded() -> None:
    fetch = FakeDart()
    fetch.registry = archive(
        REGISTRATIONS
        + [
            ("00000001", "10000K", "20261123"),
            ("00000004", "400004", "20261124"),
            ("00000005", "", "20261124"),
        ]
    )
    fetch.profiles["00000004"] = profile("E", "")
    result = collect_universe(EXECUTED, max_requests=5, fetch=fetch, clock=lambda: NOW)
    assert len(result.companies) == 3
    assert result.excluded_other_corps == ("00000004",)
    assert result.companies[0].registry_stock_codes == ("100001", "10000K")
    assert [p for e, p in fetch.calls if e == "company.json"].count({"corp_code": "00000001"}) == 1
    assert result.requests == 5


def test_as_of_financial_date_does_not_change_current_universe_date() -> None:
    run = QueryRun(SnapshotRequest("cash", "as_of", 6, date(2025, 12, 31)), EXECUTED)
    result = collect_listed_filings(
        run.executed_at, search(), max_requests=5, fetch=FakeDart(), clock=lambda: NOW
    )
    assert result.universe.execution_date == date(2026, 11, 25)
    assert result.executed_at == run.executed_at


def test_korean_day_is_used_even_when_utc_date_is_previous_day() -> None:
    started = datetime(2026, 11, 24, 15, tzinfo=UTC)
    result = collect_universe(started, max_requests=4, fetch=FakeDart(), clock=lambda: started)
    assert result.execution_date == date(2026, 11, 25)


@pytest.mark.parametrize(
    "payload", [b"not zip", archive([]), archive([("00000001", "", "20261124")])]
)
def test_invalid_or_empty_registry_never_becomes_complete(payload: bytes) -> None:
    fetch = FakeDart()
    fetch.registry = payload
    with pytest.raises(CollectionError):
        collect_universe(EXECUTED, max_requests=10, fetch=fetch, clock=lambda: NOW)


@pytest.mark.parametrize(
    "row",
    [
        ("00000004", "100001", "20261124"),  # A stock cannot silently identify two corporations.
        ("00000004", "400004", "20261126"),
        ("00000004", "400004", "20260230"),
        ("wrong", "400004", "20261124"),
    ],
)
def test_conflicting_or_invalid_registry_rows_fail(row: tuple[str, str, str]) -> None:
    fetch = FakeDart()
    fetch.registry = archive(REGISTRATIONS + [row])
    with pytest.raises(CollectionError):
        collect_universe(EXECUTED, max_requests=10, fetch=fetch, clock=lambda: NOW)
    assert len(fetch.calls) == 1


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"[]",
        b'{"status":"020","message":"private message"}',
        profile("Z", "300003"),
        profile("N", "999999"),
        profile("E", ""),
        json.dumps(
            {
                "status": "000",
                "corp_cls": "N",
                "corp_name": "x",
                "stock_code": "300003",
                "corp_code": "00000999",
            }
        ).encode(),
    ],
)
def test_failed_or_inconsistent_profile_does_not_return_partial_population(body: bytes) -> None:
    fetch = FakeDart()
    fetch.profiles["00000003"] = body
    with pytest.raises(CollectionError) as error:
        collect_universe(EXECUTED, max_requests=4, fetch=fetch, clock=lambda: NOW)
    assert "private message" not in str(error.value)


def test_all_empty_listings_keep_all_current_companies() -> None:
    fetch = FakeDart()
    fetch.filings = b'{"status":"013"}'
    result = collect_listed_filings(
        EXECUTED, search(), max_requests=5, fetch=fetch, clock=lambda: NOW
    )
    assert len(result.universe.companies) == 3
    assert result.items == ()
    assert result.no_filings == ("00000001", "00000002", "00000003")


@pytest.mark.parametrize("budget,expected_calls", [(1, 1), (3, 1), (4, 4)])
def test_one_budget_covers_registry_profiles_and_listing(budget: int, expected_calls: int) -> None:
    fetch = FakeDart()
    with pytest.raises(CollectionError, match="budget"):
        collect_listed_filings(
            EXECUTED, search(), max_requests=budget, fetch=fetch, clock=lambda: NOW
        )
    assert len(fetch.calls) == expected_calls


def test_listing_failure_after_population_is_not_a_partial_success() -> None:
    fetch = FakeDart()
    fetch.filings = b'{"status":"020"}'
    with pytest.raises(CollectionError, match="rate_limit"):
        collect_listed_filings(EXECUTED, search(), max_requests=5, fetch=fetch, clock=lambda: NOW)


@pytest.mark.parametrize(
    "observed", [NOW.replace(tzinfo=None), NOW - timedelta(days=1), EXECUTED - timedelta(seconds=1)]
)
def test_invalid_or_reversed_observation_clock_fails_before_io(observed: datetime) -> None:
    fetch = FakeDart()
    with pytest.raises(CollectionError):
        collect_universe(EXECUTED, max_requests=4, fetch=fetch, clock=lambda: observed)
    assert fetch.calls == []


def test_midnight_during_population_stops_before_next_profile() -> None:
    fetch = FakeDart()
    times = iter([NOW, NOW, datetime(2026, 11, 25, 15, tzinfo=UTC)])
    with pytest.raises(CollectionError, match="date_changed"):
        collect_universe(EXECUTED, max_requests=4, fetch=fetch, clock=lambda: next(times))
    assert len(fetch.calls) == 2


def test_midnight_after_listing_rejects_the_result() -> None:
    fetch = FakeDart()
    times = iter([NOW] * 6 + [datetime(2026, 11, 25, 15, tzinfo=UTC)])
    with pytest.raises(CollectionError, match="date_changed"):
        collect_listed_filings(
            EXECUTED, search(), max_requests=5, fetch=fetch, clock=lambda: next(times)
        )
    assert len(fetch.calls) == 5


def test_future_search_or_company_filter_does_not_become_full_population() -> None:
    for value in [
        ListRequest(search().start, date(2026, 11, 26)),
        ListRequest(search().start, search().end, corp_cls="Y"),
    ]:
        fetch = FakeDart()
        with pytest.raises(ValueError):
            collect_listed_filings(EXECUTED, value, max_requests=5, fetch=fetch, clock=lambda: NOW)
        assert fetch.calls == []


def test_naive_execution_time_is_not_assigned_a_server_timezone() -> None:
    with pytest.raises(ValueError):
        collect_universe(
            EXECUTED.replace(tzinfo=None), max_requests=4, fetch=FakeDart(), clock=lambda: NOW
        )
