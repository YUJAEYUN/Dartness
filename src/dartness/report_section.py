"""Find a supported explicit DART balance-sheet group without rewriting its bytes."""

import hashlib
from dataclasses import dataclass
from html.parser import HTMLParser

from dartness.cash_contract import CashBasis


@dataclass(frozen=True)
class ReportSection:
    text: str
    locator: str
    sha256: str


class _Groups(HTMLParser):
    def __init__(self, text: str, group: str) -> None:
        super().__init__(convert_charrefs=True)
        self.text, self.group = text, group
        self.lines = [0]
        # HTMLParser counts LF only, not every Unicode line separator.
        for line in text.split("\n")[:-1]:
            self.lines.append(self.lines[-1] + len(line) + 1)
        self.document_count = self.document_ends = 0
        self.document_open = False
        self.company_codes: list[str | None] = []
        self.report_codes: list[str | None] = []
        self.active: tuple[int, str] | None = None
        self.group_depth = 0
        self.sections: list[ReportSection] = []

    def _offset(self) -> int:
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("document", "company-name", "document-name", "table-group"):
            if len({key for key, _ in attrs}) != len(attrs):
                raise ValueError("duplicate_identity_attributes")
        data = dict(attrs)
        if tag == "document":
            if self.document_open or self.document_count:
                raise ValueError("multiple_document_roots")
            self.document_count += 1
            self.document_open = True
        elif tag in ("company-name", "document-name", "table-group") and not self.document_open:
            raise ValueError("identity_or_group_outside_document")
        elif tag == "company-name":
            self.company_codes.append(data.get("aregcik"))
        elif tag == "document-name":
            self.report_codes.append(data.get("acode"))
        elif tag == "table-group":
            if self.group_depth:
                raise ValueError("nested_report_group")
            self.group_depth = 1
            if data.get("aclass") == self.group:
                line, column = self.getpos()
                self.active = (self._offset(), f"TABLE-GROUP[{self.group}] / line {line}:{column}")

    def handle_endtag(self, tag: str) -> None:
        if tag == "document":
            if not self.document_open or self.group_depth:
                raise ValueError("unfinished_document_root")
            self.document_ends += 1
            self.document_open = False
        elif tag == "table-group":
            if self.group_depth != 1:
                raise ValueError("unmatched_report_group")
            if self.active is not None:
                start, locator = self.active
                end = self.text.find(">", self._offset()) + 1
                if end == 0:
                    raise ValueError("unfinished_report_group")
                text = self.text[start:end]
                self.sections.append(
                    ReportSection(text, locator, hashlib.sha256(text.encode()).hexdigest())
                )
            self.active, self.group_depth = None, 0


def find_balance_section(
    document: bytes, corp_code: str, basis: CashBasis, *, report_code: str = "11011"
) -> ReportSection:
    """Explicit BS_S/BS_C groups for the requested periodic code; annual is the legacy default."""
    if report_code not in ("11011", "11012", "11013"):
        raise ValueError("unsupported_report_kind")
    if basis not in ("separate", "individual", "consolidated"):
        raise ValueError("unsupported_basis")
    if len(document) > 32 * 1024 * 1024:
        raise ValueError("document_too_large")
    if b"<!DOCTYPE" in document.upper() or b"<!ENTITY" in document.upper():
        raise ValueError("unsafe_document_declaration")
    try:
        text = document.decode("utf-8")
    except UnicodeError as error:
        raise ValueError("unsupported_document_encoding") from error
    group = "{XBRL}BS_C" if basis == "consolidated" else "{XBRL}BS_S"
    parser = _Groups(text, group)
    parser.feed(text)
    parser.close()
    if parser.document_count != 1 or parser.document_ends != 1 or parser.group_depth:
        raise ValueError("incomplete_or_multiple_document")
    if parser.company_codes != [corp_code]:
        raise ValueError("document_company_mismatch")
    if parser.report_codes != [report_code]:
        raise ValueError("unsupported_report_kind")
    if len(parser.sections) != 1:
        raise ValueError("missing_or_ambiguous_balance_group")
    section = parser.sections[0]
    if len(section.text.encode()) > 256 * 1024:
        raise ValueError("balance_group_too_large")
    return section
