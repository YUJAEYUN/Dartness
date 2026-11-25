"""Resolve a DART table URL and cross-check its rendered cash value, without executing JS."""

import hashlib
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from html.parser import HTMLParser
from typing import NoReturn
from urllib.parse import parse_qs, urlencode, urlsplit

from dartness.cash_contract import CashBasis, CashValue
from dartness.cash_table import extract_cash_table

_MAX_PAGE = 2 * 1024 * 1024
_FIELDS = ("rcpNo", "dcmNo", "eleId", "offset", "length", "dtd")


@dataclass(frozen=True)
class CashViewerLink:
    url: str
    value: CashValue
    main_sha256: str
    section_sha256: str

    def __post_init__(self) -> None:
        params = _viewer_params(self.url)
        if urlsplit(self.url).path != "/report/viewer.do":
            raise ValueError("table_viewer_url_required")
        if params["rcpNo"] != [self.value.evidence.receipt_number]:
            raise ValueError("viewer_receipt_mismatch")
        if any(
            not re.fullmatch(r"[0-9a-f]{64}", digest)
            for digest in (self.main_sha256, self.section_sha256)
        ):
            raise ValueError("viewer_response_hash_required")

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "verified_table_section",
            "url": self.url,
            "main_response_sha256": self.main_sha256,
            "section_response_sha256": self.section_sha256,
            "verification": "same_receipt_company_basis_date_unit_amount",
        }


def _decode(payload: bytes) -> str:
    if len(payload) > _MAX_PAGE:
        raise ValueError("viewer_page_too_large")
    try:
        return payload.decode("utf-8")
    except UnicodeError as error:
        raise ValueError("unsupported_viewer_encoding") from error


def balance_viewer_url(main: bytes, receipt: str, corp_code: str, basis: CashBasis) -> str:
    """Read only the observed literal node assignments; reject ambiguous/changed formats."""
    if not re.fullmatch(r"[0-9]{14}", receipt) or not re.fullmatch(r"[0-9]{8}", corp_code):
        raise ValueError("viewer_identity_required")
    if basis not in ("separate", "individual", "consolidated"):
        raise ValueError("viewer_basis_required")
    text = _decode(main)
    companies = re.findall(r"openCorpInfoNew\('([0-9]{8})'", text)
    if companies != [corp_code]:
        raise ValueError("viewer_company_mismatch")
    candidates: list[dict[str, str]] = []
    title = "연결재무상태표" if basis == "consolidated" else "재무상태표"
    # No eval/JS execution. A variable declaration delimits each observed TOC node.
    for block in re.split(r"\bvar node[0-9]+\s*=\s*\{\}\s*;", text)[1:]:
        pairs = re.findall(r'node[0-9]+\[\'(\w+)\'\]\s*=\s*"([^"\r\n]*)"\s*;', block)
        fields = dict(pairs)
        label = re.sub(r"^[0-9.\-\s]+", "", fields.get("text", ""))
        if "".join(label.split()) != title:
            continue
        if len(fields) != len(pairs) or any(key not in fields for key in _FIELDS):
            raise ValueError("invalid_viewer_node")
        if fields["rcpNo"] != receipt:
            raise ValueError("viewer_receipt_mismatch")
        if any(not re.fullmatch(r"[0-9]{1,10}", fields[key]) for key in _FIELDS[1:-1]):
            raise ValueError("invalid_viewer_location")
        if int(fields["length"]) <= 0 or fields["dtd"] != "dart4.xsd":
            raise ValueError("unsupported_viewer_location")
        candidates.append(fields)
    if len(candidates) != 1:
        raise ValueError("missing_or_ambiguous_viewer_balance_sheet")
    return "https://dart.fss.or.kr/report/viewer.do?" + urlencode(
        {key: candidates[0][key] for key in _FIELDS}
    )


class _Tables(HTMLParser):
    """Keep just complete top-level tables; page chrome is not financial input."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.tables: list[str] = []
        self.parts: list[str] | None = None
        self.heading: list[str] | None = None
        self.titles: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "p" and dict(attrs).get("class") == "table-group-xbrl":
            if self.heading is not None:
                raise ValueError("nested_viewer_heading")
            self.heading = []
        if tag == "table":
            if self.parts is not None:
                raise ValueError("nested_viewer_table")
            self.parts = []
        if self.parts is not None:
            start = self.get_starttag_text()
            if start is None:
                raise ValueError("missing_viewer_start_tag")
            self.parts.append(start)

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self.heading is not None:
            self.titles.append("".join(self.heading))
            self.heading = None
        if self.parts is not None:
            self.parts.append(f"</{tag}>")
        if tag == "table":
            if self.parts is None:
                raise ValueError("unmatched_viewer_table")
            self.tables.append("".join(self.parts))
            self.parts = None

    def handle_data(self, data: str) -> None:
        if self.heading is not None:
            self.heading.append(data)
        if self.parts is not None:
            self.parts.append(data)

    def handle_entityref(self, name: str) -> None:
        self.handle_data(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.handle_data(f"&#{name};")


def verify_cash_viewer(
    value: CashValue,
    main: bytes,
    fetch: Callable[[str], bytes],
    checked_at: datetime,
) -> CashViewerLink:
    receipt = value.evidence.receipt_number
    if receipt is None:
        raise ValueError("viewer_receipt_required")
    url = balance_viewer_url(main, receipt, value.query.corp_code, value.basis)
    payload = fetch(url)
    text = _decode(payload)
    tables = _Tables()
    tables.feed(text)
    tables.close()
    expected_title = "연결재무상태표" if value.basis == "consolidated" else "재무상태표"
    titles = ["".join(re.sub(r"^[0-9.\-\s]+", "", title).split()) for title in tables.titles]
    if titles != [expected_title] or tables.heading is not None:
        raise ValueError("viewer_section_basis_mismatch")
    if tables.parts is not None or len(tables.tables) != 2:
        raise ValueError("incomplete_viewer_balance_sheet")
    # Reuse the existing strict period/unit/row/column checks, preserving full-source hash.
    evidence = replace(value.evidence, source_url=url)
    rendered = extract_cash_table(
        value.query, "\n".join(tables.tables), value.basis, evidence, checked_at
    )
    if not isinstance(rendered, CashValue) or (
        rendered.amount_krw != value.amount_krw
        or rendered.raw_amount != value.raw_amount
        or rendered.as_of != value.as_of
    ):
        raise ValueError("viewer_cash_value_mismatch")
    return CashViewerLink(
        url, value, hashlib.sha256(main).hexdigest(), hashlib.sha256(payload).hexdigest()
    )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: object, fp: object, code: int, msg: str, headers: object, newurl: str
    ) -> NoReturn:
        raise ValueError("viewer_redirect_rejected")


def _viewer_params(url: str) -> dict[str, list[str]]:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "dart.fss.or.kr"
        or parsed.path not in ("/dsaf001/main.do", "/report/viewer.do")
        or parsed.fragment
    ):
        raise ValueError("official_viewer_url_required")
    params = parse_qs(parsed.query, keep_blank_values=True)
    expected = {"rcpNo"} if parsed.path == "/dsaf001/main.do" else set(_FIELDS)
    if set(params) != expected or any(len(values) != 1 for values in params.values()):
        raise ValueError("invalid_viewer_query")
    if not re.fullmatch(r"[0-9]{14}", params["rcpNo"][0]):
        raise ValueError("invalid_viewer_receipt")
    if parsed.path == "/report/viewer.do" and (
        any(not re.fullmatch(r"[0-9]{1,10}", params[key][0]) for key in _FIELDS[1:-1])
        or params["dtd"] != ["dart4.xsd"]
        or int(params["length"][0]) <= 0
    ):
        raise ValueError("invalid_viewer_location")
    return params


def fetch_dart_viewer(url: str) -> bytes:
    _viewer_params(url)
    request = urllib.request.Request(url, headers={"User-Agent": "Dartness evidence check"})
    try:
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=30) as response:
            payload: object = response.read(_MAX_PAGE + 1)
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ValueError("viewer_transport_error") from None
    if not isinstance(payload, bytes):
        raise ValueError("invalid_viewer_response")
    _decode(payload)
    return payload
