"""Read explicit native annual-report cover dates and a bounded correction section."""

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser

from dartness.report_section import ReportSection


@dataclass(frozen=True)
class NativeReportMetadata:
    period_start: date
    period_end: date
    cover: ReportSection
    correction: ReportSection | None

    def to_dict(self) -> dict[str, object]:
        return {
            "report_kind": "사업보고서",
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "cover_locator": self.cover.locator,
            "cover_sha256": self.cover.sha256,
            "correction_locator": self.correction.locator if self.correction else None,
            "correction_sha256": self.correction.sha256 if self.correction else None,
        }


class _Metadata(HTMLParser):
    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=True)
        self.text = text
        self.lines = [0]
        for line in text.split("\n")[:-1]:
            self.lines.append(self.lines[-1] + len(line) + 1)
        self.active: tuple[str, int, str] | None = None
        self.sections: dict[str, list[ReportSection]] = {"cover": [], "correction": []}
        self.period: tuple[str, str, list[str]] | None = None
        self.dates: dict[str, list[date]] = {"PERIODFROM": [], "PERIODTO": []}
        self.kinds: list[str | None] = []
        self.names: list[str] = []
        self.name_parts: list[str] | None = None
        self.document_count = 0
        self.document_open = False
        self.body_open = False

    def _position(self) -> int:
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        if tag in ("cover", "correction", "document-name", "tu") and len(data) != len(attrs):
            raise ValueError("duplicate_native_metadata_attributes")
        if tag == "document":
            if self.document_open or self.document_count:
                raise ValueError("native_document_boundary")
            self.document_count += 1
            self.document_open = True
        elif tag == "body":
            if not self.document_open or self.body_open:
                raise ValueError("native_document_boundary")
            self.body_open = True
        elif tag == "document-name":
            if not self.document_open or self.name_parts is not None:
                raise ValueError("native_document_name_boundary")
            self.kinds.append(data.get("acode"))
            self.name_parts = []
        if tag in self.sections:
            if not self.body_open:
                raise ValueError("native_metadata_outside_body")
            if self.active is not None:
                raise ValueError("nested_native_metadata_section")
            line, column = self.getpos()
            self.active = (tag, self._position(), f"{tag.upper()} / line {line}:{column}")
        elif tag == "tu" and self.active and self.active[0] == "cover":
            unit = data.get("aunit")
            if unit in self.dates:
                if self.period is not None:
                    raise ValueError("nested_native_period")
                self.period = (unit, data.get("aunitvalue") or "", [])

    def handle_data(self, data: str) -> None:
        if self.name_parts is not None:
            self.name_parts.append(data)
        if self.period is not None:
            self.period[2].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "document-name":
            if self.name_parts is None:
                raise ValueError("native_document_name_boundary")
            self.names.append("".join("".join(self.name_parts).split()))
            self.name_parts = None
        elif tag == "body":
            if not self.body_open or self.active:
                raise ValueError("native_document_boundary")
            self.body_open = False
        elif tag == "document":
            if not self.document_open or self.body_open:
                raise ValueError("native_document_boundary")
            self.document_open = False
        elif tag == "tu" and self.period is not None:
            unit, declared, parts = self.period
            visible = re.fullmatch(
                r"([0-9]{4})년([0-9]{2})월([0-9]{2})일", "".join("".join(parts).split())
            )
            if visible is None or not re.fullmatch(r"[0-9]{8}", declared):
                raise ValueError("explicit_native_period_required")
            actual = date(int(visible[1]), int(visible[2]), int(visible[3]))
            if f"{actual.year:04}{actual.month:02}{actual.day:02}" != declared:
                raise ValueError("native_period_text_mismatch")
            self.dates[unit].append(actual)
            self.period = None
        elif tag in self.sections:
            if self.active is None or self.active[0] != tag or self.period is not None:
                raise ValueError("native_metadata_boundary")
            _, start, locator = self.active
            end = self.text.find(">", self._position()) + 1
            if not end:
                raise ValueError("native_metadata_boundary")
            text = self.text[start:end]
            self.sections[tag].append(
                ReportSection(text, locator, hashlib.sha256(text.encode()).hexdigest())
            )
            self.active = None


def read_native_metadata(document: bytes) -> NativeReportMetadata:
    """Financial/firm identity is separately checked by the existing full-report inspector."""
    if len(document) > 32 * 1024 * 1024:
        raise ValueError("native_document_too_large")
    if b"<!DOCTYPE" in document.upper() or b"<!ENTITY" in document.upper():
        raise ValueError("unsafe_native_declaration")
    try:
        text = document.decode("utf-8")
    except UnicodeError as error:
        raise ValueError("unsupported_native_encoding") from error
    parser = _Metadata(text)
    parser.feed(text)
    parser.close()
    if (
        parser.active
        or parser.period
        or parser.kinds != ["11011"]
        or parser.names != ["사업보고서"]
        or parser.name_parts is not None
        or parser.document_count != 1
        or parser.document_open
        or parser.body_open
    ):
        raise ValueError("incomplete_native_metadata")
    covers, corrections = parser.sections["cover"], parser.sections["correction"]
    if len(covers) != 1 or len(corrections) > 1 or any(len(v) != 1 for v in parser.dates.values()):
        raise ValueError("missing_or_ambiguous_native_metadata")
    start, end = parser.dates["PERIODFROM"][0], parser.dates["PERIODTO"][0]
    if start > end:
        raise ValueError("native_period_order")
    return NativeReportMetadata(start, end, covers[0], corrections[0] if corrections else None)
