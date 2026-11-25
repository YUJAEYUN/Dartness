"""Workbook behavior and evidence accessibility; not an Excel desktop rendering test."""

import json
import sys
import zipfile
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from openpyxl import load_workbook
from test_cash_report import ARCHIVE, NOW, QUERY, D

from dartness.amounts import AmountInput
from dartness.cash_contract import CashValue
from dartness.cash_report import inspect_cash_report, main
from dartness.cash_report_result import CashReportResult
from dartness.cash_workbook import write_cash_report_workbook


@pytest.fixture(scope="module")
def result() -> CashReportResult:
    return inspect_cash_report(D, QUERY, "individual", Decimal("40000000000"), ARCHIVE, NOW)


def test_three_columns_keep_amount_date_basis_and_accessible_source(
    tmp_path: Path, result: CashReportResult
) -> None:
    path = tmp_path / "result.xlsx"
    before = result.to_dict()
    write_cash_report_workbook(result, path)
    book = load_workbook(path)
    assert book.sheetnames == ["지정 공시 확인"]
    sheet = book[book.sheetnames[0]]
    assert sheet.max_column == 3
    assert [sheet.cell(2, i).value for i in range(1, 4)] == [
        "법인명",
        "현금및현금성자산(억원)",
        "조회 기준",
    ]
    assert sheet["A3"].value == "대한약품"
    assert sheet["A3"].hyperlink is not None
    assert sheet["A3"].hyperlink.target == D.source_url
    assert sheet["B3"].data_type == "n"
    assert Decimal(str(sheet["B3"].value)) == Decimal("439.72786132")
    assert sheet["C3"].value == "2025.12.31 · 법인 자체(개별)"
    assert sheet["B3"].comment is not None
    assert "43,972,786,132" in sheet["B3"].comment.text and "단위: 원" in sheet["B3"].comment.text
    assert "개발용" in str(sheet["A1"].value)
    assert "SHA" not in " ".join(str(cell.value) for row in sheet for cell in row)
    assert result.to_dict() == before


@pytest.mark.parametrize("kind", ["below", "review"])
def test_nonmatching_or_unknown_companies_are_not_exported_as_leads(
    tmp_path: Path, kind: str
) -> None:
    result = inspect_cash_report(
        D,
        QUERY,
        "individual",
        Decimal("50000000000"),
        ARCHIVE if kind == "below" else b"invalid archive",
        NOW,
    )
    path = tmp_path / "result.xlsx"
    write_cash_report_workbook(result, path)
    sheet = load_workbook(path).worksheets[0]
    assert sheet["B3"].value is None
    assert "대한약품" not in [cell.value for row in sheet for cell in row]
    if kind == "review":
        assert "확인 필요" in str(sheet["A3"].value)
    else:
        assert "조건 충족 금액이 확인되지" in str(sheet["A3"].value)


def test_company_text_is_not_an_executable_formula(tmp_path: Path) -> None:
    result = inspect_cash_report(
        replace(D, corp_name='=HYPERLINK("https://example.com")'),
        QUERY,
        "individual",
        Decimal(0),
        ARCHIVE,
        NOW,
    )
    path = tmp_path / "result.xlsx"
    write_cash_report_workbook(result, path)
    cell = load_workbook(path).worksheets[0]["A3"]
    assert cell.data_type == "s" and str(cell.value).startswith("=HYPERLINK")
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    assert root.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}f") == []


def test_precision_loss_is_rejected_instead_of_silently_changing_amount(
    tmp_path: Path, result: CashReportResult
) -> None:
    assert isinstance(result.value, CashValue)
    changed = replace(
        result.value,
        raw_amount=AmountInput("1234567890123456", "원"),
        amount_krw=Decimal("1234567890123456"),
    )
    path = tmp_path / "result.xlsx"
    with pytest.raises(ValueError, match="excel_numeric_precision"):
        write_cash_report_workbook(replace(result, value=changed), path)
    assert not path.exists()


def test_fake_match_status_cannot_bypass_exact_condition(tmp_path: Path) -> None:
    result = inspect_cash_report(D, QUERY, "individual", Decimal("50000000000"), ARCHIVE, NOW)
    object.__setattr__(result, "status", "document_match")
    path = tmp_path / "result.xlsx"
    write_cash_report_workbook(result, path)
    sheet = load_workbook(path).worksheets[0]
    assert sheet["B3"].value is None and "대한약품" not in str(sheet["A3"].value)


def cli_args(tmp_path: Path, output: Path) -> list[str]:
    archive = tmp_path / "source.zip"
    archive.write_bytes(ARCHIVE)
    return [
        "cash_report",
        "--archive",
        str(archive),
        "--corp-code",
        D.corp_code,
        "--company-name",
        D.corp_name,
        "--receipt",
        D.receipt,
        "--published-on",
        str(D.filed_on),
        "--as-of",
        str(QUERY.as_of),
        "--basis",
        "individual",
        "--minimum-krw",
        "40000000000",
        "--checked-at",
        NOW.isoformat(),
        "--output",
        str(output),
    ]


def test_cli_writes_audit_json_and_simple_workbook_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", cli_args(tmp_path, output))
    assert main() == 0
    record = json.loads(output.read_text())
    assert record["amount_krw"] == "43972786132" and record["latest_correction_verified"] is False
    assert record["document_sha256"] and record["locator"]
    sheet = load_workbook(output.with_suffix(".xlsx")).worksheets[0]
    assert sheet["A3"].value == "대한약품" and sheet["B3"].data_type == "n"


def test_wrong_cli_output_extension_does_not_overwrite_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "keep.xlsx"
    output.write_text("keep")
    monkeypatch.setattr(sys, "argv", cli_args(tmp_path, output))
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2 and output.read_text() == "keep"


def test_writer_requires_xlsx_extension(tmp_path: Path, result: CashReportResult) -> None:
    with pytest.raises(ValueError, match="xlsx_output_required"):
        write_cash_report_workbook(result, tmp_path / "wrong.json")
