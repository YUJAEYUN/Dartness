"""Synthetic official-schema listing cases; not live DART or financial extraction evidence."""

import json
from datetime import date

import pytest

from dartness.dart_smoke import CollectionError
from dartness.disclosure_list import ListRequest, collect_list, month_windows


def row(index: int = 1, *, filed: str = "20260115") -> dict[str, object]:
    return {
        "rcept_no": f"{filed}{index:06d}",
        "rcept_dt": filed,
        "corp_code": "00123456",
        "corp_name": "합성 사례",
        "corp_cls": "Y",
        "stock_code": "123456",
        "report_nm": "[기재정정] 합성 보고서",
        "flr_nm": "제출인",
        "rm": "정정",
    }


def page(rows: list[dict[str, object]], *, number: int = 1, total: int | None = None) -> bytes:
    count = len(rows) if total is None else total
    return json.dumps(
        {
            "status": "000",
            "page_no": number,
            "page_count": 100,
            "total_count": count,
            "total_page": (count + 99) // 100,
            "list": rows,
        }
    ).encode()


def request() -> ListRequest:
    return ListRequest(date(2026, 1, 1), date(2026, 1, 31))


def test_months_include_leap_day_and_have_no_gap_or_overlap() -> None:
    assert month_windows(date(2024, 1, 30), date(2024, 3, 2)) == (
        (date(2024, 1, 30), date(2024, 1, 31)),
        (date(2024, 2, 1), date(2024, 2, 29)),
        (date(2024, 3, 1), date(2024, 3, 2)),
    )
    assert month_windows(date.max, date.max) == ((date.max, date.max),)


def test_filters_corrections_and_all_pages_are_preserved() -> None:
    calls: list[dict[str, str]] = []

    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        assert endpoint == "list.json"
        calls.append(params.copy())
        number = int(params["page_no"])
        return (
            page([row(i) for i in range(1, 101)], total=101)
            if number == 1
            else page([row(101)], number=2, total=101)
        )

    result = collect_list(
        ListRequest(request().start, request().end, "00123456", "Y", "E"),
        max_requests=2,
        fetch=fetch,
    )
    assert result.requests == 2
    assert len(result.items) == 101
    assert result.items[0].receipt == "20260115000001"
    assert result.items[-1].receipt == "20260115000101"
    assert result.items[0].report_name == "[기재정정] 합성 보고서"
    assert (
        result.items[0].source_url == "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260115000001"
    )
    for params in calls:
        assert params["last_reprt_at"] == "N"
        assert params["page_count"] == "100"
        assert params["corp_code"] == "00123456"
        assert params["corp_cls"] == "Y"
        assert params["pblntf_ty"] == "E"
        assert params["sort_mth"] == "asc"
        assert "crtfc_key" not in params


def test_long_range_without_company_uses_months_and_empty_is_not_an_error() -> None:
    calls = []

    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        calls.append(params.copy())
        return b'{"status":"013"}'

    result = collect_list(
        ListRequest(date(2025, 12, 31), date(2026, 4, 1)), max_requests=5, fetch=fetch
    )
    assert result.items == ()
    assert result.requests == 5
    assert [(p["bgn_de"], p["end_de"]) for p in calls] == [
        ("20251231", "20251231"),
        ("20260101", "20260131"),
        ("20260201", "20260228"),
        ("20260301", "20260331"),
        ("20260401", "20260401"),
    ]
    assert all("corp_code" not in p for p in calls)


def test_small_year_is_padded_and_maximum_date_does_not_overflow() -> None:
    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        assert len(params["bgn_de"]) == len(params["end_de"]) == 8
        return b'{"status":"013"}'

    assert collect_list(ListRequest(date.min, date.min), max_requests=1, fetch=fetch).items == ()
    assert collect_list(ListRequest(date.max, date.max), max_requests=1, fetch=fetch).items == ()


@pytest.mark.parametrize("code", ["010", "020", "800", "999"])
def test_api_errors_are_not_empty_success_and_do_not_repeat_messages(code: str) -> None:
    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        return json.dumps({"status": code, "message": "private-upstream-message"}).encode()

    with pytest.raises(CollectionError) as caught:
        collect_list(request(), max_requests=1, fetch=fetch)
    assert "private-upstream" not in str(caught.value)


@pytest.mark.parametrize(
    "payload", [b"not json", b"[]", b"{}", b'{"status":"000","total_count":1}']
)
def test_malformed_response_never_returns_success(payload: bytes) -> None:
    with pytest.raises(CollectionError):
        collect_list(request(), max_requests=1, fetch=lambda endpoint, params: payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("rcept_no", "https://bad.invalid/"),
        ("corp_code", "wrong"),
        ("rcept_dt", "20260230"),
        ("rcept_dt", "20260201"),
        ("corp_cls", "wrong"),
        ("report_nm", ""),
    ],
)
def test_invalid_rows_or_wrong_scope_fail(field: str, value: str) -> None:
    item = {**row(), field: value}
    with pytest.raises(CollectionError):
        collect_list(request(), max_requests=1, fetch=lambda endpoint, params: page([item]))


@pytest.mark.parametrize("field,value", [("corp_code", "00111111"), ("corp_cls", "K")])
def test_company_and_market_mismatch_fail(field: str, value: str) -> None:
    item = {**row(), field: value}
    with pytest.raises(CollectionError, match="scope"):
        collect_list(
            ListRequest(request().start, request().end, "00123456", "Y"),
            max_requests=1,
            fetch=lambda endpoint, params: page([item]),
        )


def test_duplicate_receipt_does_not_hide_missing_entry() -> None:
    with pytest.raises(CollectionError, match="duplicate_or_missing"):
        collect_list(request(), max_requests=1, fetch=lambda endpoint, params: page([row(), row()]))


def test_conflicting_receipt_is_not_arbitrarily_selected() -> None:
    with pytest.raises(CollectionError, match="conflicting"):
        collect_list(
            request(),
            max_requests=1,
            fetch=lambda endpoint, params: page([row(), {**row(), "report_nm": "different"}]),
        )


@pytest.mark.parametrize("failure", ["changed", "missing", "wrong_page", "no_data", "network"])
def test_second_page_failure_does_not_return_first_page(failure: str) -> None:
    calls = 0

    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 1:
            return page([row(i) for i in range(100)], total=101)
        if failure == "network":
            raise CollectionError("network_error")
        if failure == "no_data":
            return b'{"status":"013"}'
        if failure == "changed":
            return page([row(101), row(102)], number=2, total=102)
        if failure == "wrong_page":
            return page([row(101)], total=1)
        return page([], number=2, total=101)

    with pytest.raises(CollectionError):
        collect_list(request(), max_requests=2, fetch=fetch)
    assert calls == 2


def test_budget_stops_before_extra_io_and_does_not_return_partial_data() -> None:
    calls = 0

    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        nonlocal calls
        calls += 1
        return page([row(i) for i in range(100)], total=101)

    with pytest.raises(CollectionError, match="budget"):
        collect_list(request(), max_requests=1, fetch=fetch)
    assert calls == 1
    with pytest.raises(CollectionError, match="budget"):
        collect_list(ListRequest(date(2026, 1, 1), date(2026, 3, 1)), max_requests=1, fetch=fetch)
    assert calls == 1


def test_later_month_failure_does_not_return_previous_month() -> None:
    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        if params["bgn_de"] == "20260101":
            return page([row()])
        raise CollectionError("rate_limit")

    with pytest.raises(CollectionError, match="rate_limit"):
        collect_list(ListRequest(date(2026, 1, 1), date(2026, 2, 1)), max_requests=2, fetch=fetch)


def test_invalid_request_is_rejected_before_io() -> None:
    with pytest.raises(ValueError):
        ListRequest(date(2026, 2, 1), date(2026, 1, 1))
    with pytest.raises(ValueError):
        ListRequest(request().start, request().end, "bad")
    with pytest.raises(ValueError):
        collect_list(request(), max_requests=0, fetch=lambda endpoint, params: b"unused")


@pytest.mark.parametrize(
    "field,value",
    [
        ("page_no", 2),
        ("page_count", 99),
        ("total_page", 2),
        ("total_count", -1),
        ("total_count", "1"),
        ("total_page", True),
    ],
)
def test_invalid_metadata_is_not_silently_coerced(field: str, value: object) -> None:
    response: dict[str, object] = {
        "status": "000",
        "page_no": 1,
        "page_count": 100,
        "total_count": 1,
        "total_page": 1,
        "list": [row()],
    }
    response[field] = value
    with pytest.raises(CollectionError):
        collect_list(
            request(), max_requests=1, fetch=lambda endpoint, params: json.dumps(response).encode()
        )


def test_no_data_cannot_contradict_its_nonempty_payload() -> None:
    payload = json.dumps({"status": "013", "list": [row()]}).encode()
    with pytest.raises(CollectionError, match="inconsistent"):
        collect_list(request(), max_requests=1, fetch=lambda endpoint, params: payload)


@pytest.mark.parametrize("stock,market", [("12345K", "Y"), ("", "E")])
def test_six_character_stock_identifiers_and_unlisted_rows_are_preserved(
    stock: str, market: str
) -> None:
    item = {**row(), "stock_code": stock, "corp_cls": market}
    result = collect_list(request(), max_requests=1, fetch=lambda endpoint, params: page([item]))
    assert result.items[0].stock_code == stock
    assert result.items[0].corp_cls == market


def test_successful_zero_count_has_an_empty_result() -> None:
    result = collect_list(request(), max_requests=1, fetch=lambda endpoint, params: page([]))
    assert result.items == ()
    assert result.requests == 1
