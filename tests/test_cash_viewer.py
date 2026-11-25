"""Real-dev official viewer responses and explicitly mutated failure cases."""

import gzip
import hashlib
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook
from test_cash_report import ARCHIVE, NOW, QUERY, D

from dartness.cash_contract import CashValue
from dartness.cash_report import inspect_cash_report
from dartness.cash_viewer import balance_viewer_url, fetch_dart_viewer, verify_cash_viewer
from dartness.cash_workbook import write_cash_report_workbook

FIXTURE = Path(__file__).parent / "fixtures/cash/report-viewer"
ORIGIN = json.loads((FIXTURE / "origin.json").read_text())
MAIN = gzip.decompress((FIXTURE / "main.html.gz").read_bytes())
BALANCE = gzip.decompress((FIXTURE / "balance.html.gz").read_bytes())
URL = ORIGIN["balance_url"]


@pytest.fixture
def value() -> CashValue:
    result = inspect_cash_report(D, QUERY, "individual", Decimal(40000000000), ARCHIVE, NOW)
    assert isinstance(result.value, CashValue)
    return result.value


def test_real_viewer_table_matches_preexisting_source_answer_and_workbook(tmp_path: Path) -> None:
    result = inspect_cash_report(D, QUERY, "individual", Decimal(40000000000), ARCHIVE, NOW)
    assert isinstance(result.value, CashValue)
    calls = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return BALANCE

    link = verify_cash_viewer(result.value, MAIN, fetch, NOW)
    assert calls == [URL]
    assert link.value.amount_krw == Decimal("43972786132")
    assert link.url == URL
    for name, payload in (("main", MAIN), ("balance", BALANCE)):
        assert hashlib.sha256(payload).hexdigest() == ORIGIN["files"][name]["response_sha256"]
    result = replace(result, viewer_link=link)
    audit = result.to_dict()
    assert audit["source_url"] == D.source_url
    assert audit["table_link"] == link.to_dict()
    assert link.section_sha256 != result.document_sha256
    path = tmp_path / "direct.xlsx"
    write_cash_report_workbook(result, path)
    sheet = load_workbook(path).worksheets[0]
    assert sheet["A3"].hyperlink is not None and sheet["A3"].hyperlink.target == URL
    assert sheet["B3"].value == 439.72786132
    assert sheet["B3"].comment is not None
    assert "대조한 재무상태표 구간" in sheet["B3"].comment.text
    assert sheet["A3"].font.sz == 10 and sheet["A3"].alignment.horizontal == "left"


@pytest.mark.parametrize(
    "before,after,error",
    [
        (b"00113128", b"00000001", "company_mismatch"),
        (b"20260318001361", b"20260318001362", "receipt_mismatch"),
        ("4-1. 재무상태표".encode(), "4-1. 연결재무상태표".encode(), "missing_or_ambiguous"),
        (b'"32187"', b'"0"', "unsupported_viewer_location"),
        (b'"260290"', b'"-1"', "invalid_viewer_location"),
        (b'"dart4.xsd"', b'"unknown.xsd"', "unsupported_viewer_location"),
    ],
)
def test_mutated_identity_basis_or_location_is_rejected(
    before: bytes, after: bytes, error: str
) -> None:
    changed = MAIN.replace(before, after)
    assert changed != MAIN
    with pytest.raises(ValueError, match=error):
        balance_viewer_url(changed, D.receipt, D.corp_code, "individual")


def test_duplicate_target_nodes_are_not_resolved_by_taking_first() -> None:
    with pytest.raises(ValueError, match="company_mismatch"):
        balance_viewer_url(MAIN + MAIN, D.receipt, D.corp_code, "individual")
    changed = MAIN + MAIN.replace(b"openCorpInfoNew(", b"other(")
    with pytest.raises(ValueError, match="missing_or_ambiguous"):
        balance_viewer_url(changed, D.receipt, D.corp_code, "individual")


@pytest.mark.parametrize(
    "before,after,error",
    [
        (b"43,972,786,132", b"43,972,786,133", "cash_value_mismatch"),
        (b"2025.12.31", b"2024.12.31", "cash_value_mismatch"),
        ("단위 : 원".encode(), "단위 : 천원".encode(), "cash_value_mismatch"),
        ("4-1. 재무상태표".encode(), "4-1. 연결재무상태표".encode(), "section_basis_mismatch"),
        (b"</TABLE>", b"", "nested_viewer_table"),
    ],
)
def test_wrong_rendered_section_is_not_a_verified_link(
    value: CashValue, before: bytes, after: bytes, error: str
) -> None:
    changed = BALANCE.replace(before, after)
    assert changed != BALANCE
    with pytest.raises(ValueError, match=error):
        verify_cash_viewer(value, MAIN, lambda url: changed, NOW)


def test_empty_error_page_and_size_limit(value: CashValue) -> None:
    with pytest.raises(ValueError, match="section_basis_mismatch"):
        verify_cash_viewer(value, MAIN, lambda url: b"maintenance", NOW)
    with pytest.raises(ValueError, match="page_too_large"):
        balance_viewer_url(b"x" * (2 * 1024 * 1024 + 1), D.receipt, D.corp_code, "individual")


@pytest.mark.parametrize(
    "url",
    ["https://example.com/report/viewer.do", "http://dart.fss.or.kr/report/viewer.do"],
)
def test_network_rejects_unofficial_or_insecure_target_without_request(url: str) -> None:
    with pytest.raises(ValueError, match="official_viewer_url_required"):
        fetch_dart_viewer(url)


def test_verified_link_cannot_be_reused_for_another_value(tmp_path: Path, value: CashValue) -> None:
    link = verify_cash_viewer(value, MAIN, lambda url: BALANCE, NOW)
    other = replace(value, evidence=replace(value.evidence, context="different source context"))
    result = inspect_cash_report(D, QUERY, "individual", Decimal(0), ARCHIVE, NOW)
    path = tmp_path / "wrong.xlsx"
    with pytest.raises(ValueError, match="viewer_link_value_mismatch"):
        write_cash_report_workbook(replace(result, value=other, viewer_link=link), path)
    assert not path.exists()
