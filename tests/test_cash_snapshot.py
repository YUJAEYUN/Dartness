"""Real-dev annual report dates and explicitly synthetic/mutated boundary cases."""

import io
import zipfile
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook
from test_cash_report import ARCHIVE, NOW, D, main_bytes, packed

from dartness.cash_contract import CashValue
from dartness.cash_report_candidates import StoredCashReport
from dartness.cash_snapshot import query_cash_reports
from dartness.cash_workbook import write_cash_report_workbook
from dartness.disclosure_list import Disclosure
from dartness.query_contract import QueryRun, SnapshotRequest


def run(as_of: date | None, months: int = 0) -> QueryRun:
    return QueryRun(
        SnapshotRequest("cash", "latest" if as_of is None else "as_of", months, as_of), NOW
    )


def test_real_dev_prior_column_is_selected_without_changing_request(tmp_path: Path) -> None:
    request = run(date(2024, 12, 31))
    result = query_cash_reports(
        request, D.corp_code, "individual", Decimal(50000000000), (StoredCashReport(D, ARCHIVE),)
    )
    assert result.status == "document_match" and result.reason is None
    assert [c.actual_date for c in result.selection.candidates] == [
        date(2025, 12, 31),
        date(2024, 12, 31),
        date(2023, 12, 31),
    ]
    assert result.report is not None and isinstance(result.report.value, CashValue)
    assert result.report.value.raw_amount.raw_value == "61,302,198,358"
    assert result.report.value.amount_krw == Decimal("61302198358")
    assert result.report.value.evidence.locator.endswith("table[2]/tr[14]/td[3]")
    assert result.report.to_dict()["requested_as_of"] == "2024-12-31"
    assert result.report.to_dict()["actual_as_of"] == "2024-12-31"
    assert result.to_dict()["latest_correction_verified"] is False
    output = tmp_path / "selected.xlsx"
    write_cash_report_workbook(result.report, output)
    assert load_workbook(output).worksheets[0]["B3"].value == 613.02198358


@pytest.mark.parametrize(
    "as_of,months,actual,amount,prior",
    [
        (None, 12, "2025-12-31", "43972786132", True),
        (date(2025, 6, 30), 6, "2024-12-31", "61302198358", True),
        (date(2025, 12, 31), 0, "2025-12-31", "43972786132", False),
    ],
)
def test_latest_and_calendar_window_preserve_requested_actual_dates(
    as_of: date | None, months: int, actual: str, amount: str, prior: bool, tmp_path: Path
) -> None:
    result = query_cash_reports(
        run(as_of, months), D.corp_code, "individual", Decimal(0), (StoredCashReport(D, ARCHIVE),)
    )
    assert result.report is not None
    audit = result.report.to_dict()
    assert audit["actual_as_of"] == actual and audit["amount_krw"] == amount
    assert audit["requested_as_of"] == str(run(as_of, months).anchor_date)
    assert audit["is_prior"] is prior
    path = tmp_path / "prior.xlsx"
    write_cash_report_workbook(result.report, path)
    sheet = load_workbook(path).worksheets[0]
    assert ("이전 자료" in str(sheet["C3"].value)) is prior
    assert str(run(as_of, months).anchor_date) in str(sheet["A1"].value)


def test_no_period_is_review_not_zero_or_nonmatch() -> None:
    result = query_cash_reports(
        run(date(2025, 6, 30)),
        D.corp_code,
        "individual",
        Decimal(0),
        (StoredCashReport(D, ARCHIVE),),
    )
    assert result.status == "needs_review" and result.reason == "period_unavailable"
    assert result.report is None and result.to_dict()["selected_report"] is None


def test_different_documents_same_date_do_not_fall_back_or_pick_latest_filing() -> None:
    other = replace(D, receipt="20260318001362")
    # Explicit synthetic filing identity around the same stored public XML.
    raw = packed(main_bytes())

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr(other.receipt + ".xml", main_bytes())
    result = query_cash_reports(
        run(None, 12),
        D.corp_code,
        "individual",
        Decimal(0),
        (StoredCashReport(D, raw), StoredCashReport(other, stream.getvalue())),
    )
    assert result.reason == "ambiguous_candidate" and result.report is None
    assert len(result.selection.candidates) == 6


def test_identical_input_repetition_is_preserved_but_selectable() -> None:
    report = StoredCashReport(D, ARCHIVE)
    result = query_cash_reports(
        run(None, 12), D.corp_code, "individual", Decimal(0), (report, report)
    )
    assert result.report is not None and len(result.selection.candidates) == 6
    assert len(result.sources) == 2


def test_future_publication_is_recorded_and_not_used_even_if_unreadable() -> None:
    future = replace(D, filed_on=date(2026, 11, 26))
    result = query_cash_reports(
        run(None, 12),
        D.corp_code,
        "individual",
        Decimal(0),
        (StoredCashReport(future, b"unreadable"),),
    )
    assert result.reason == "period_unavailable" and result.report is None
    assert result.sources[0].excluded_after_cutoff is True


@pytest.mark.parametrize("change", ["broken_zip", "missing_unit", "bad_prior_amount", "company"])
def test_unreadable_source_is_not_silently_removed_before_choosing_older(change: str) -> None:
    if change == "broken_zip":
        archive = b"bad"
    else:
        raw = main_bytes()
        before, after = {
            "missing_unit": ("(단위 : 원)".encode(), "(단위 : )".encode()),
            "bad_prior_amount": (b"61,302,198,358", b"-"),
            "company": (b'AREGCIK="00113128"', b'AREGCIK="00000001"'),
        }[change]
        archive = packed(raw.replace(before, after))
    result = query_cash_reports(
        run(None, 12),
        D.corp_code,
        "individual",
        Decimal(0),
        (StoredCashReport(D, ARCHIVE), StoredCashReport(D, archive)),
    )
    assert result.reason == "source_incomplete" and result.report is None
    assert result.sources[1].failure
    assert result.to_dict()["status"] == "needs_review"


@pytest.mark.parametrize(
    "correction", [replace(D, report_name="[기재정정]사업보고서"), replace(D, remarks="정")]
)
def test_unresolved_correction_is_not_reported_as_final_selection(correction: Disclosure) -> None:
    result = query_cash_reports(
        run(None, 12),
        D.corp_code,
        "individual",
        Decimal(0),
        (StoredCashReport(correction, ARCHIVE),),
    )
    assert result.reason == "correction_unresolved" and result.report is None


def test_consolidated_request_never_uses_standalone_report() -> None:
    result = query_cash_reports(
        run(None, 12), D.corp_code, "consolidated", Decimal(0), (StoredCashReport(D, ARCHIVE),)
    )
    assert result.reason == "source_incomplete" and result.report is None


def test_mixed_corporations_are_input_error() -> None:
    with pytest.raises(ValueError, match="company_mismatch"):
        query_cash_reports(
            run(None, 12),
            D.corp_code,
            "individual",
            Decimal(0),
            (StoredCashReport(replace(D, corp_code="00000001"), ARCHIVE),),
        )


def test_separate_company_reuses_original_source_answers_without_tuning() -> None:
    import hashlib
    import json

    fixture = Path(__file__).parent / "fixtures/cash/report-candidate-check"
    origin = json.loads((fixture / "origin.json").read_text())
    archive = (fixture / "092130.zip").read_bytes()
    assert hashlib.sha256(archive).hexdigest() == origin["archive_sha256"]
    d = Disclosure(
        origin["receipt"],
        origin["corp_code"],
        origin["company_name"],
        "K",
        "092130",
        "사업보고서",
        date(2026, 3, 18),
        origin["company_name"],
        "",
    )
    for period in origin["periods"]:
        result = query_cash_reports(
            run(date.fromisoformat(period["actual_date"])),
            d.corp_code,
            "separate",
            Decimal(35000000000),
            (StoredCashReport(d, archive),),
        )
        assert result.report is not None and isinstance(result.report.value, CashValue)
        assert str(result.report.value.amount_krw) == period["amount_krw"]
        assert result.report.value.raw_amount.raw_value == period["raw_amount"]
        assert result.report.document_sha256 == origin["document_sha256"]
        assert result.report.basis == "separate"
        assert result.report.value.raw_amount.unit == "원"
        assert result.selection.candidate is not None
        assert result.selection.candidate.source.document_sha256 == origin["document_sha256"]


def test_real_dev_all_three_period_answers_are_source_fixed() -> None:
    import json

    origin = json.loads(
        (Path(__file__).parent / "fixtures/cash/report-slice/periods.json").read_text()
    )
    for period in origin["periods"]:
        result = query_cash_reports(
            run(date.fromisoformat(period["actual_date"])),
            D.corp_code,
            "individual",
            Decimal(0),
            (StoredCashReport(D, ARCHIVE),),
        )
        assert result.report is not None and isinstance(result.report.value, CashValue)
        assert str(result.report.value.amount_krw) == period["amount_krw"]
        assert result.report.value.raw_amount.raw_value == period["raw_amount"]
        assert result.report.document_sha256 == origin["document_sha256"]


def test_selected_known_amount_below_minimum_is_nonmatch_and_not_an_exported_lead(
    tmp_path: Path,
) -> None:
    result = query_cash_reports(
        run(date(2025, 12, 31)),
        D.corp_code,
        "individual",
        Decimal(50000000000),
        (StoredCashReport(D, ARCHIVE),),
    )
    assert result.status == "document_non_match" and result.report is not None
    path = tmp_path / "nonmatch.xlsx"
    write_cash_report_workbook(result.report, path)
    sheet = load_workbook(path).worksheets[0]
    assert sheet["B3"].value is None and sheet["A3"].value != D.corp_name


def test_other_all_in_one_types_are_not_implicitly_run_as_cash() -> None:
    other = QueryRun(SnapshotRequest("try-assets", "latest", 12), NOW)
    with pytest.raises(ValueError, match="cash_query_run_required"):
        query_cash_reports(other, D.corp_code, "individual", Decimal(0), ())
