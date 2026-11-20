"""Read cash from a preselected, simple balance-sheet HTML section."""

import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from html.parser import HTMLParser

from dartness.amounts import AmountInput, NormalizedAmount, normalize_krw_amount
from dartness.cash_contract import (
    CashBasis,
    CashEvidence,
    CashNeedsReview,
    CashQuery,
    CashResult,
    CashValue,
    ReviewReason,
)


@dataclass(frozen=True)
class _Cell:
    text: str
    header: bool


class _Tables(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[_Cell]]] = []
        self.table: list[list[_Cell]] | None = None
        self.row: list[_Cell] | None = None
        self.parts: list[str] | None = None
        self.cell_tag = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            raise ValueError("실행 코드·스타일이 포함된 구간은 지원하지 않습니다")
        if tag == "table":
            if self.table is not None or len(self.tables) >= 2:
                raise ValueError("중첩 표나 두 개를 넘는 표는 지원하지 않습니다")
            self.table = []
            self.tables.append(self.table)
        elif tag == "tr":
            if self.table is None or self.row is not None:
                raise ValueError("행의 경계가 불명확합니다")
            self.row = []
        elif tag in ("td", "th"):
            if self.row is None or self.parts is not None:
                raise ValueError("셀의 경계가 불명확합니다")
            if any(k in ("rowspan", "colspan") and v != "1" for k, v in attrs):
                raise ValueError("병합 셀은 지원하지 않습니다")
            self.parts, self.cell_tag = [], tag

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th"):
            if self.parts is None or self.row is None or tag != self.cell_tag:
                raise ValueError("셀의 끝이 불명확합니다")
            self.row.append(_Cell("".join(self.parts).strip(), tag == "th"))
            self.parts = None
        elif tag == "tr":
            if self.row is None or self.table is None or self.parts is not None:
                raise ValueError("행의 끝이 불명확합니다")
            self.table.append(self.row)
            self.row = None
        elif tag == "table":
            if self.table is None or self.row is not None:
                raise ValueError("표의 끝이 불명확합니다")
            self.table = None

    def handle_data(self, data: str) -> None:
        if self.parts is not None:
            self.parts.append(data)


def _compact(text: str) -> str:
    return "".join(text.split())


def _read_section(html: str) -> tuple[list[list[_Cell]], list[list[_Cell]]]:
    if len(html.encode("utf-8")) > 256 * 1024:
        raise ValueError("지원하는 구간 크기를 넘었습니다")
    parser = _Tables()
    parser.feed(html)
    parser.close()
    if parser.table is not None or len(parser.tables) != 2:
        raise ValueError("완전한 기간·단위 표와 금액 표가 필요합니다")
    return parser.tables[0], parser.tables[1]


def _periods_and_unit(context: list[list[_Cell]]) -> tuple[dict[str, date], str]:
    periods: dict[str, date] = {}
    units: list[str] = []
    for row in context:
        for cell in row:
            text = _compact(cell.text)
            match = re.fullmatch(r"(제[0-9]+기)([0-9]{4})\.([0-9]{2})\.([0-9]{2})현재", text)
            if match:
                if match[1] in periods:
                    raise ValueError("기간 이름이 중복됩니다")
                periods[match[1]] = date(int(match[2]), int(match[3]), int(match[4]))
            unit = re.fullmatch(r"\(단위:([^()]+)\)", text)
            if unit:
                units.append(unit[1])
    if not periods or len(units) != 1:
        raise ValueError("명시한 기간과 단일 적용 단위를 확인할 수 없습니다")
    return periods, units[0]


def extract_cash_table(
    query: CashQuery,
    html_section: str,
    basis: CashBasis,
    evidence: CashEvidence,
    checked_at: datetime,
) -> CashResult:
    """Extract within a caller-selected section; selection metadata is not verified here."""

    def review(reason: ReviewReason, detail: str) -> CashNeedsReview:
        return CashNeedsReview(
            query,
            reason,
            checked_at,
            evidence.locator,
            detail,
            "원문 범위·기간·단위와 표 구조를 확인합니다",
            evidence,
        )

    if not isinstance(checked_at, datetime) or checked_at.utcoffset() is None:
        raise ValueError("timezone-aware check time required")
    allowed = ("separate", "individual") if query.scope == "standalone" else ("consolidated",)
    if basis not in allowed:
        return review("basis_unavailable", "선정 구간의 재무 범위가 요청과 다릅니다")
    try:
        context, rows = _read_section(html_section)
        title = "연결재무상태표" if basis == "consolidated" else "재무상태표"
        if not context or len(context[0]) != 1 or _compact(context[0][0].text) != title:
            raise ValueError("선정한 재무 범위와 표 제목이 다릅니다")
        periods, unit = _periods_and_unit(context)
        labels = [label for label, period in periods.items() if period == query.as_of]
        if not labels:
            return review("period_unavailable", "명시된 기간에 요청한 기준일이 없습니다")
        if len(labels) != 1 or not rows or not all(cell.header for cell in rows[0]):
            raise ValueError("기간이나 머리글이 모호합니다")
        header = [_compact(cell.text) for cell in rows[0]]
        if len(header) < 2 or header[0] or len(set(header)) != len(header):
            raise ValueError("머리글 구조가 모호하거나 중복됩니다")
        if any(label not in periods for label in header[1:]) or labels[0] not in header:
            raise ValueError("기간과 머리글 열을 대응할 수 없습니다")
        column = header.index(labels[0])
        targets = [
            (i, row)
            for i, row in enumerate(rows, 1)
            if row and _compact(row[0].text) == "현금및현금성자산"
        ]
        if len(targets) != 1:
            raise ValueError("현금 행이 없거나 중복됩니다")
        row_number, row = targets[0]
        if len(row) != len(header) or any(cell.header for cell in row):
            raise ValueError("현금 행과 머리글의 열 구조가 다릅니다")
        source = AmountInput(row[column].text, unit)
        normalized = normalize_krw_amount(source)
        if not isinstance(normalized, NormalizedAmount):
            raise ValueError("현금 금액이나 적용 단위를 해석할 수 없습니다")
        result_evidence = replace(
            evidence,
            locator=f"{evidence.locator} / table[2]/tr[{row_number}]/td[{column + 1}]",
            context="\n".join(cell.text for line in context for cell in line)
            + f"\n입력 범위: {basis}; 선택 열: {rows[0][column].text}",
        )
        return CashValue(query, basis, query.as_of, source, normalized.amount_krw, result_evidence)
    except ValueError as error:
        return review("extraction_failed", str(error))
