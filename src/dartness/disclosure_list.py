"""Collect OpenDART listing pages, not financial facts (docs/specs/disclosure-list.md)."""

import calendar
import json
import re
from dataclasses import dataclass
from datetime import date, timedelta

from dartness.dart_smoke import CollectionError, Fetch, _api_status


@dataclass(frozen=True)
class ListRequest:
    start: date
    end: date
    corp_code: str = ""
    corp_cls: str = ""
    disclosure_type: str = ""

    def __post_init__(self) -> None:
        if type(self.start) is not date or type(self.end) is not date or self.start > self.end:
            raise ValueError("invalid_listing_dates")
        if not isinstance(self.corp_code, str) or (
            self.corp_code and not re.fullmatch(r"[0-9]{8}", self.corp_code)
        ):
            raise ValueError("invalid_corp_code")
        if self.corp_cls not in ("", "Y", "K", "N", "E"):
            raise ValueError("invalid_corp_class")
        if self.disclosure_type not in ("", *"ABCDEFGHIJ"):
            raise ValueError("invalid_disclosure_type")


def month_windows(start: date, end: date) -> tuple[tuple[date, date], ...]:
    ListRequest(start, end)
    windows = []
    while True:
        stop = min(
            end, date(start.year, start.month, calendar.monthrange(start.year, start.month)[1])
        )
        windows.append((start, stop))
        if stop == end:
            return tuple(windows)
        start = stop + timedelta(days=1)


@dataclass(frozen=True)
class Disclosure:
    receipt: str
    corp_code: str
    corp_name: str
    corp_cls: str
    stock_code: str
    report_name: str
    filed_on: date
    filer_name: str
    remarks: str

    @property
    def source_url(self) -> str:
        return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={self.receipt}"


@dataclass(frozen=True)
class ListResult:
    request: ListRequest
    requests: int
    items: tuple[Disclosure, ...]


def _text(value: object, *, pattern: str = "", empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise CollectionError("invalid_list_row")
    if pattern and not re.fullmatch(pattern, value):
        raise CollectionError("invalid_list_row")
    return value


def _row(value: object, request: ListRequest, start: date, end: date) -> Disclosure:
    if not isinstance(value, dict):
        raise CollectionError("invalid_list_row")
    filed = _text(value.get("rcept_dt"), pattern=r"[0-9]{8}")
    try:
        filed_on = date.fromisoformat(f"{filed[:4]}-{filed[4:6]}-{filed[6:]}")
    except ValueError:
        raise CollectionError("invalid_list_row") from None
    row = Disclosure(
        _text(value.get("rcept_no"), pattern=r"[0-9]{14}"),
        _text(value.get("corp_code"), pattern=r"[0-9]{8}"),
        _text(value.get("corp_name")),
        _text(value.get("corp_cls"), pattern=r"[YKNE]"),
        _text(value.get("stock_code", ""), pattern=r"(?:[0-9A-Z]{6})?", empty=True),
        _text(value.get("report_nm")),
        filed_on,
        _text(value.get("flr_nm", ""), empty=True),
        _text(value.get("rm", ""), empty=True),
    )
    if (
        not start <= row.filed_on <= end
        or (request.corp_code and row.corp_code != request.corp_code)
        or (request.corp_cls and row.corp_cls != request.corp_cls)
    ):
        raise CollectionError("listing_scope_mismatch")
    return row


def _integer(value: object) -> int:
    if type(value) is not int or value < 0:
        raise CollectionError("invalid_listing_metadata")
    return value


def _page(payload: bytes, page: int) -> tuple[int, int, list[object]]:
    try:
        result: object = json.loads(payload)
    except (ValueError, UnicodeError):
        raise CollectionError("invalid_listing_json") from None
    if not isinstance(result, dict):
        raise CollectionError("invalid_listing_response")
    status = result.get("status")
    if status == "013":
        if page != 1 or result.get("list") not in (None, []):
            raise CollectionError("inconsistent_listing")
        if result.get("total_count", 0) != 0 or result.get("total_page", 0) != 0:
            raise CollectionError("inconsistent_listing")
        return 0, 0, []
    _api_status(status)
    total, pages = _integer(result.get("total_count")), _integer(result.get("total_page"))
    if (
        type(result.get("page_no")) is not int
        or result["page_no"] != page
        or type(result.get("page_count")) is not int
        or result["page_count"] != 100
        or pages != (total + 99) // 100
    ):
        raise CollectionError("invalid_listing_metadata")
    rows = result.get("list")
    expected = min(100, max(0, total - (page - 1) * 100))
    if not isinstance(rows, list) or len(rows) != expected:
        raise CollectionError("incomplete_listing_page")
    return total, pages, rows


def collect_list(request: ListRequest, *, max_requests: int, fetch: Fetch) -> ListResult:
    """Return checked listings only; failed windows never return partial data."""
    if type(max_requests) is not int or max_requests < 1:
        raise ValueError("invalid_request_budget")
    windows = month_windows(request.start, request.end)
    if len(windows) > max_requests:
        raise CollectionError("listing_request_budget")
    calls = 0
    items: dict[str, Disclosure] = {}
    for start, end in windows:
        page = 1
        expected: tuple[int, int] | None = None
        window_receipts: set[str] = set()
        while True:
            if calls >= max_requests:
                raise CollectionError("listing_request_budget")
            params = {
                "bgn_de": f"{start.year:04d}{start.month:02d}{start.day:02d}",
                "end_de": f"{end.year:04d}{end.month:02d}{end.day:02d}",
                "page_no": str(page),
                "page_count": "100",
                "sort": "date",
                "sort_mth": "asc",
                "last_reprt_at": "N",
            }
            for key, filter_value in (
                ("corp_code", request.corp_code),
                ("corp_cls", request.corp_cls),
                ("pblntf_ty", request.disclosure_type),
            ):
                if filter_value:
                    params[key] = filter_value
            calls += 1
            total, pages, rows = _page(fetch("list.json", params), page)
            if expected is not None and expected != (total, pages):
                raise CollectionError("listing_changed_during_collection")
            expected = (total, pages)
            for value in rows:
                row = _row(value, request, start, end)
                previous = items.get(row.receipt)
                if previous is not None and previous != row:
                    raise CollectionError("conflicting_listing_receipt")
                items[row.receipt] = row
                window_receipts.add(row.receipt)
            if page >= pages:
                if len(window_receipts) != total:
                    raise CollectionError("duplicate_or_missing_listing")
                break
            page += 1
    return ListResult(
        request, calls, tuple(sorted(items.values(), key=lambda r: (r.filed_on, r.receipt)))
    )
