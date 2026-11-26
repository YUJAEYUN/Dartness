"""Bounded parsers for observed DART body options and flat errata tables; no JS execution."""

import re
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from urllib.parse import parse_qs


def _decode(payload: bytes) -> str:
    if len(payload) > 2 * 1024 * 1024:
        raise ValueError("correction_page_too_large")
    try:
        return payload.decode("utf-8")
    except UnicodeError as error:
        raise ValueError("unsupported_correction_encoding") from error


def _compact(text: str) -> str:
    return "".join(text.split())


@dataclass(frozen=True)
class BodyEntry:
    receipt: str
    filed_on: date
    report_kind: str
    is_correction: bool
    label: str


class _Family(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.count = 0
        self.active = False
        self.option: dict[str, str | None] | None = None
        self.parts: list[str] = []
        self.companies: list[str] = []
        self.entries: list[BodyEntry] = []
        self.selected: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("select", "option", "span") and len(dict(attrs)) != len(attrs):
            raise ValueError("duplicate_body_attributes")
        data = dict(attrs)
        if tag == "span":
            match = re.match(r"openCorpInfoNew\('([0-9]{8})',", data.get("onclick") or "")
            if match:
                self.companies.append(match[1])
        if tag == "select":
            if self.active:
                raise ValueError("nested_body_history")
            if data.get("id") == "family":
                self.count += 1
                self.active = True
        elif tag == "option" and self.active:
            if self.option is not None:
                raise ValueError("body_option_boundary")
            self.option, self.parts = data, []

    def handle_data(self, data: str) -> None:
        if self.option is not None:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "option" and self.active:
            if self.option is None:
                raise ValueError("body_option_boundary")
            data = self.option
            raw = data.get("value") or ""
            if raw != "null":
                params = parse_qs(raw, keep_blank_values=True)
                if set(params) != {"rcpNo"} or len(params["rcpNo"]) != 1:
                    raise ValueError("body_receipt_required")
                receipt = params["rcpNo"][0]
                if not re.fullmatch(r"[0-9]{14}", receipt):
                    raise ValueError("body_receipt_required")
                label = _compact("".join(self.parts))
                kind = data.get("title")
                match = re.fullmatch(
                    r"([0-9]{4})\.([0-9]{2})\.([0-9]{2})(\[정정\])?사업보고서", label
                )
                if match is None or kind != "사업보고서":
                    raise ValueError("unsupported_body_label")
                filed = date(int(match[1]), int(match[2]), int(match[3]))
                self.entries.append(BodyEntry(receipt, filed, kind, match[4] is not None, label))
                if "selected" in data:
                    self.selected.append(receipt)
            self.option = None
        elif tag == "select" and self.active:
            if self.option is not None:
                raise ValueError("body_option_boundary")
            self.active = False


def read_body_history(payload: bytes, corp_code: str, receipt: str) -> tuple[BodyEntry, ...]:
    parser = _Family()
    parser.feed(_decode(payload))
    parser.close()
    if parser.count != 1 or parser.active or not parser.entries:
        raise ValueError("body_history_required")
    if parser.companies != [corp_code]:
        raise ValueError("viewer_company_mismatch")
    if parser.selected != [receipt]:
        raise ValueError("selected_body_mismatch")
    if len({entry.receipt for entry in parser.entries}) != len(parser.entries):
        raise ValueError("duplicate_body_receipt")
    return tuple(parser.entries)


class _ErrataTables(HTMLParser):
    def __init__(self, native: bool) -> None:
        super().__init__(convert_charrefs=True)
        self.native = native
        self.tables: list[list[list[str]]] = []
        self.table: list[list[str]] | None = None
        self.row: list[str] | None = None
        self.parts: list[str] | None = None
        self.cell_tag = ""
        self.heading: list[str] | None = None
        self.headings: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        if (tag == "p" and data.get("class") == "correction") or (self.native and tag == "title"):
            if self.heading is not None:
                raise ValueError("nested_errata_heading")
            self.heading = []
        elif tag == "table":
            if self.table is not None:
                raise ValueError("nested_errata_table")
            self.table = []
            self.tables.append(self.table)
        elif tag == "tr":
            if self.table is None or self.row is not None:
                raise ValueError("errata_row_boundary")
            self.row = []
        elif tag in ("td", "th"):
            if any(key in ("colspan", "rowspan") and value != "1" for key, value in attrs):
                raise ValueError("merged_errata_cell")
            if self.row is None or self.parts is not None:
                raise ValueError("errata_cell_boundary")
            self.parts, self.cell_tag = [], tag
        elif tag == "br" and self.parts is not None:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self.parts is not None:
            self.parts.append(data)
        if self.heading is not None:
            self.heading.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("p", "title") and self.heading is not None:
            self.headings.append(_compact("".join(self.heading)))
            self.heading = None
        elif tag in ("td", "th"):
            if self.parts is None or self.row is None or tag != self.cell_tag:
                raise ValueError("errata_cell_boundary")
            self.row.append(" ".join("".join(self.parts).split()))
            self.parts = None
        elif tag == "tr":
            if self.row is None or self.table is None or self.parts is not None:
                raise ValueError("errata_cell_boundary")
            self.table.append(self.row)
            self.row = None
        elif tag == "table":
            if self.table is None or self.row is not None:
                raise ValueError("errata_table_boundary")
            self.table = None


@dataclass(frozen=True)
class ErrataObservation:
    corrected_on: date
    first_submitted_on: date
    report_kind: str
    changes: tuple[tuple[str, ...], ...]
    first_submission_locator: str


def _korean_date(text: str) -> date:
    match = re.fullmatch(r"([0-9]{4})년([0-9]{2})월([0-9]{2})일", _compact(text))
    if match is None:
        raise ValueError("explicit_errata_date_required")
    return date(int(match[1]), int(match[2]), int(match[3]))


def read_errata(payload: bytes, *, native: bool = False) -> ErrataObservation:
    parser = _ErrataTables(native)
    parser.feed(_decode(payload))
    parser.close()
    if parser.headings != ["정정신고(보고)"] or parser.heading is not None:
        raise ValueError("errata_heading_required")
    if parser.table is not None or parser.row is not None or parser.parts is not None:
        raise ValueError("incomplete_errata_table")
    rows = [
        (i, j, row) for i, table in enumerate(parser.tables, 1) for j, row in enumerate(table, 1)
    ]
    targets = [
        row[1] for _, _, row in rows if len(row) == 2 and _compact(row[0]) == "1.정정대상공시서류:"
    ]
    first = [
        (i, j, row[1])
        for i, j, row in rows
        if len(row) == 2 and _compact(row[0]) == "2.정정대상공시서류의최초제출일:"
    ]
    dates = [
        row[0]
        for _, _, row in rows
        if len(row) == 1 and re.fullmatch(r"[0-9]{4}년[0-9]{2}월[0-9]{2}일", _compact(row[0]))
    ]
    header = ("항목", "정정요구ㆍ명령관련여부", "정정사유", "정정전", "정정후")
    changes = [
        table for table in parser.tables if table and tuple(map(_compact, table[0])) == header
    ]
    if len(targets) != 1 or len(first) != 1 or len(dates) != 1 or len(changes) != 1:
        raise ValueError("missing_or_ambiguous_errata_fields")
    table = changes[0]
    if len(table) < 2 or any(len(row) != 5 or any(not cell for cell in row) for row in table[1:]):
        raise ValueError("incomplete_errata_changes")
    i, j, text = first[0]
    return ErrataObservation(
        _korean_date(dates[0]),
        _korean_date(text),
        targets[0],
        tuple(tuple(row) for row in table[1:]),
        f"table[{i}]/tr[{j}]/td[2]",
    )
