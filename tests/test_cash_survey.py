"""Synthetic rosters and source reports; no claim of an actual full-market survey."""

import hashlib
import io
import json
import zipfile
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook
from test_latest_cash import CORP, NOW, history_for, synthetic

from dartness.cash_contract import CashValue
from dartness.cash_report_candidates import StoredCashReport
from dartness.cash_survey import (
    CashSourceFailure,
    CashSurveySources,
    query_cash_survey,
    write_cash_survey_workbook,
)
from dartness.filing_history import HistoryResponse
from dartness.latest_cash import BodyObservation
from dartness.listed_universe import ListedCompany, UniverseSnapshot
from dartness.query_contract import QueryRun, SnapshotRequest


def roster() -> UniverseSnapshot:
    companies = tuple(
        ListedCompany(code, "현재명" + code, market, stock, (stock,), (date(2026, 1, 1),))
        for code, market, stock in [
            ("00000001", "Y", "000001"),
            ("00000002", "K", "000002"),
            ("01205842", "N", "267270"),
        ]
    )
    return UniverseSnapshot(
        NOW.date(),
        NOW - timedelta(minutes=3),
        NOW - timedelta(minutes=2),
        "a" * 64,
        tuple((c.corp_code, "b" * 64) for c in companies),
        companies,
        (),
        4,
    )


def run(latest: bool = False) -> QueryRun:
    return QueryRun(
        SnapshotRequest(
            "cash",
            "latest" if latest else "as_of",
            12 if latest else 0,
            None if latest else date(2025, 12, 31),
        ),
        NOW,
    )


def source(
    company: ListedCompany, amount: str = "600", unit: str = "원", half: bool = False
) -> CashSurveySources:
    base = synthetic(True, amount)
    receipt = "20261116" + company.corp_code[-6:]
    d = replace(
        base.disclosure,
        corp_code=company.corp_code,
        corp_cls=company.market,
        stock_code=company.stock_code,
        receipt=receipt,
        corp_name="공시명" + company.corp_code,
    )
    with zipfile.ZipFile(io.BytesIO(base.archive)) as archive:
        raw = archive.read(base.disclosure.receipt + ".xml")
    raw = raw.replace(CORP.encode(), company.corp_code.encode()).replace(
        "(단위:원)".encode(), f"(단위:{unit})".encode()
    )
    if half:
        raw = (
            raw.replace("분기보고서".encode(), "반기보고서".encode())
            .replace(b"11013", b"11012")
            .replace("3분기말".encode(), "반기말".encode())
            .replace(b"20260930", b"20260630")
            .replace("2026년09월30일".encode(), "2026년06월30일".encode())
            .replace(b"2026.09.30", b"2026.06.30")
        )
        d = replace(d, report_name="반기보고서 (2026.06)")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(receipt + ".xml", raw)
    h = history_for((base.disclosure,))
    responses = []
    for response in h.responses:
        payload = json.loads(response.payload)
        for row in payload.get("list", []):
            row.update(
                corp_code=d.corp_code,
                corp_name=d.corp_name,
                corp_cls=d.corp_cls,
                stock_code=d.stock_code,
                rcept_no=d.receipt,
                report_nm=d.report_name,
            )
        raw_response = json.dumps(payload).encode()
        params = {**dict(response.parameters), "corp_code": company.corp_code}
        responses.append(
            HistoryResponse(
                tuple(params.items()), raw_response, hashlib.sha256(raw_response).hexdigest()
            )
        )
    h = replace(
        h, request=replace(h.request, corp_code=company.corp_code), responses=tuple(responses)
    )
    kind = "반기보고서" if half else "분기보고서"
    main = (
        f"<span onclick=\"openCorpInfoNew('{company.corp_code}','x')\"></span>"
        f'<select id="family"><option value="rcpNo={receipt}" title="{kind}" selected>'
        f"2026.11.16 {kind}</option></select>"
    ).encode()
    return CashSurveySources(
        "separate",
        h,
        (StoredCashReport(d, buffer.getvalue()),),
        (BodyObservation(receipt, main, NOW),),
    )


def test_every_target_is_preserved_with_match_nonmatch_and_missing_source() -> None:
    u = roster()
    a, b, c = u.companies
    result = query_cash_survey(
        run(),
        u,
        "standalone",
        Decimal(500),
        {a.corp_code: source(a), b.corp_code: source(b, "400")},
        max_companies=3,
    )
    assert len(result.entries) == 3
    assert result.counts == {
        "document_match": 1,
        "document_non_match": 1,
        "needs_review": 0,
        "not_processed": 1,
    }
    assert result.entries[2].company == c and result.entries[2].skipped == "source_bundle_missing"
    assert result.all_targets_processed is False and result.all_values_verified is False
    assert result.to_dict()["target_count"] == 3


def test_company_limit_does_not_shrink_the_universe_or_turn_skips_into_nonmatches() -> None:
    u = roster()
    sources = {c.corp_code: source(c) for c in u.companies}
    result = query_cash_survey(run(), u, "standalone", Decimal(500), sources, max_companies=1)
    assert result.counts["document_match"] == 1 and result.counts["not_processed"] == 2
    assert len(result.entries) == 3 and all(
        e.skipped == "company_limit_reached" for e in result.entries[1:]
    )


def test_source_failure_is_review_and_cannot_be_reported_as_zero_or_nonmatch() -> None:
    u = roster()
    a, b, c = u.companies
    result = query_cash_survey(
        run(),
        u,
        "standalone",
        Decimal(500),
        {
            a.corp_code: CashSourceFailure("archive_hash_mismatch"),
            b.corp_code: source(b),
            c.corp_code: source(c, "400"),
        },
        max_companies=3,
    )
    assert result.counts == {
        "document_match": 1,
        "document_non_match": 1,
        "needs_review": 1,
        "not_processed": 0,
    }
    assert result.all_targets_processed and not result.all_values_verified
    entry = result.entries[0].to_dict()
    assert entry["reason"] == "archive_hash_mismatch" and entry["query_result"] is None


def test_all_verified_includes_nonmatching_values_without_adding_them_to_excel(
    tmp_path: Path,
) -> None:
    u = roster()
    a, b, c = u.companies
    result = query_cash_survey(
        run(),
        u,
        "standalone",
        Decimal(500),
        {
            a.corp_code: source(a, "500"),
            b.corp_code: source(b, "600"),
            c.corp_code: source(c, "400"),
        },
        max_companies=3,
    )
    assert result.all_values_verified and result.counts["document_match"] == 2
    path = tmp_path / "matches.xlsx"
    write_cash_survey_workbook(result, path)
    sheet = load_workbook(path).worksheets[0]
    assert sheet.max_row == 4 and sheet.max_column == 3
    assert [sheet.cell(r, 1).value for r in (3, 4)] == [a.name, b.name]
    assert "공시명" not in sheet["A3"].value
    assert sheet["B3"].value == 0.000005 and sheet["B4"].value == 0.000006
    assert "미처리 0" in sheet["A1"].value and "전수 검증 미완료" in sheet["A1"].value
    assert sheet.auto_filter.ref == "A2:C4" and sheet.freeze_panes == "A3"
    assert all(
        cell.font.sz == 10 and cell.alignment.horizontal == "left"
        for row in sheet
        for cell in row
        if cell.value is not None
    )
    assert sheet["A3"].hyperlink.target != sheet["A4"].hyperlink.target
    assert sheet["A4"].font.underline == "single"


def test_each_row_keeps_its_own_date_unit_scope_and_source_comment(tmp_path: Path) -> None:
    u = roster()
    a, b, c = u.companies
    first, second = source(a, "600"), source(b, "1", "천원", half=True)
    second = replace(second, basis="individual")
    result = query_cash_survey(
        run(True),
        u,
        "standalone",
        Decimal(500),
        {a.corp_code: first, b.corp_code: second},
        max_companies=3,
    )
    path = tmp_path / "different.xlsx"
    write_cash_survey_workbook(result, path)
    sheet = load_workbook(path).worksheets[0]
    assert "2026.09.30" in sheet["C3"].value and "별도" in sheet["C3"].value
    assert "2026.06.30" in sheet["C4"].value and "개별" in sheet["C4"].value
    assert sheet["B3"].value == 0.000007 and sheet["B4"].value == 0.007
    assert "적용 단위: 원" in sheet["B3"].comment.text
    assert "적용 단위: 천원" in sheet["B4"].comment.text


def test_empty_confirmed_results_does_not_claim_all_unknown_targets_are_nonmatching(
    tmp_path: Path,
) -> None:
    result = query_cash_survey(run(), roster(), "standalone", Decimal(500), {}, max_companies=1)
    path = tmp_path / "empty.xlsx"
    write_cash_survey_workbook(result, path)
    sheet = load_workbook(path).worksheets[0]
    assert "확인된 조건 충족" in sheet["A3"].value and "미처리 3" in sheet["A1"].value
    assert sheet["B3"].value is None and result.counts["document_non_match"] == 0


def test_scope_conflict_is_review_without_a_consolidated_fallback() -> None:
    u = roster()
    a = u.companies[0]
    result = query_cash_survey(
        run(), u, "consolidated", Decimal(500), {a.corp_code: source(a)}, max_companies=1
    )
    assert (
        result.entries[0].status == "needs_review"
        and result.entries[0].failure == "basis_scope_mismatch"
    )
    assert result.counts["document_match"] == 0


@pytest.mark.parametrize(
    "kind", ["day", "future_observation", "duplicate", "markets", "profile_hash", "profile_missing"]
)
def test_universe_provenance_and_date_errors_are_not_a_smaller_successful_survey(kind: str) -> None:
    u = roster()
    if kind == "day":
        u = replace(u, execution_date=date(2026, 11, 25))
    elif kind == "future_observation":
        u = replace(u, observed_until=NOW + timedelta(seconds=1))
    elif kind == "duplicate":
        u = replace(u, companies=(u.companies[0], u.companies[0], u.companies[2]))
    elif kind == "markets":
        u = replace(u, companies=u.companies[:2])
    elif kind == "profile_hash":
        u = replace(u, profile_sha256=((u.companies[0].corp_code, "bad"), *u.profile_sha256[1:]))
    elif kind == "profile_missing":
        u = replace(u, profile_sha256=u.profile_sha256[:-1])
    with pytest.raises(ValueError):
        query_cash_survey(run(), u, "standalone", Decimal(500), {}, max_companies=3)


def test_outside_company_and_invalid_operational_limits_are_rejected() -> None:
    with pytest.raises(ValueError, match="unexpected_company_sources"):
        query_cash_survey(
            run(),
            roster(),
            "standalone",
            Decimal(500),
            {"00000009": CashSourceFailure("missing")},
            max_companies=3,
        )
    for limit in (0, -1, True):
        with pytest.raises(ValueError, match="positive_company_limit"):
            query_cash_survey(run(), roster(), "standalone", Decimal(500), {}, max_companies=limit)


def test_review_sheet_is_optional_and_uses_plain_reasons(tmp_path: Path) -> None:
    u = roster()
    a = u.companies[0]
    requested = replace(run(), request=replace(run().request, include_review=True))
    result = query_cash_survey(
        requested,
        u,
        "standalone",
        Decimal(500),
        {a.corp_code: CashSourceFailure("archive_hash_mismatch")},
        max_companies=1,
    )
    path = tmp_path / "review.xlsx"
    write_cash_survey_workbook(result, path)
    book = load_workbook(path)
    assert book.sheetnames == ["현금 조건 조회", "확인 내역"]
    sheet = book["확인 내역"]
    assert sheet["A3"].value == a.name and sheet["B3"].value == "확인 필요"
    assert sheet["C3"].value == "저장된 원문 파일이 수집 기록과 다릅니다."
    assert sheet["B4"].value == "미처리" and sheet.max_row == 5
    assert result.to_dict()["include_review_requested"] is True
    assert book.worksheets[0]["B3"].value is None
    assert all(
        c.font.sz == 10 and c.alignment.horizontal == "left"
        for row in sheet
        for c in row
        if c.value is not None
    )
    default = query_cash_survey(run(), u, "standalone", Decimal(500), {}, max_companies=1)
    other = tmp_path / "default.xlsx"
    write_cash_survey_workbook(default, other)
    assert len(load_workbook(other).worksheets) == 1


def test_bad_table_link_does_not_change_a_verified_cash_value(tmp_path: Path) -> None:
    u = roster()
    a = u.companies[0]
    prepared = replace(source(a), table_section=b"not a balance table")
    result = query_cash_survey(
        run(), u, "standalone", Decimal(500), {a.corp_code: prepared}, max_companies=1
    )
    assert result.counts["document_match"] == 1
    assert result.entries[0].result is not None
    report = result.entries[0].result.report
    assert report is not None and isinstance(report.value, CashValue)
    assert report.value.amount_krw == Decimal(600)
    assert report.viewer_link is None and report.viewer_link_failure
    path = tmp_path / "fallback.xlsx"
    write_cash_survey_workbook(result, path)
    sheet = load_workbook(path).worksheets[0]
    assert sheet["A3"].hyperlink.target == report.disclosure.source_url
    assert "표 바로가기 미확인" in sheet["B3"].comment.text


def test_one_company_source_error_is_preserved_while_other_companies_continue() -> None:
    u = roster()
    a, b, c = u.companies
    broken = source(a)
    broken = replace(
        broken,
        history=replace(
            broken.history, request=replace(broken.history.request, corp_code="00000099")
        ),
    )
    result = query_cash_survey(
        run(),
        u,
        "standalone",
        Decimal(500),
        {a.corp_code: broken, b.corp_code: source(b), c.corp_code: source(c)},
        max_companies=3,
    )
    assert result.counts["needs_review"] == 1 and result.counts["document_match"] == 2
    assert result.entries[0].reason == "history_company_mismatch"
    assert result.all_targets_processed and not result.all_values_verified
