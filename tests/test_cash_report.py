"""Whole stored real-dev report and explicitly synthetic/mutated failure cases."""

import hashlib
import io
import json
import zipfile
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from dartness.cash_contract import CashQuery, CashValue
from dartness.cash_report import inspect_cash_report
from dartness.disclosure_list import Disclosure
from dartness.report_section import find_balance_section

FIXTURE = Path(__file__).parent / "fixtures/cash/report-slice"
ORIGIN = json.loads((FIXTURE / "origin.json").read_text())
ARCHIVE = (FIXTURE / "023910.zip").read_bytes()
D = Disclosure(
    "20260318001361",
    "00113128",
    "대한약품",
    "K",
    "023910",
    "사업보고서",
    date(2026, 3, 18),
    "대한약품",
    "",
)
QUERY = CashQuery("00113128", date(2025, 12, 31))
NOW = datetime(2026, 11, 25, tzinfo=UTC)


def main_bytes() -> bytes:
    with zipfile.ZipFile(io.BytesIO(ARCHIVE)) as z:
        return z.read(ORIGIN["main_document"])


def packed(main: bytes | None, attachment: bytes = b"ignored") -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        if main is not None:
            z.writestr(D.receipt + ".xml", main)
        z.writestr(D.receipt + "_00760.xml", attachment)
    return stream.getvalue()


@pytest.mark.parametrize(
    "minimum,status",
    [
        ("50000000000", "document_non_match"),
        ("40000000000", "document_match"),
        ("43972786132", "document_match"),
        ("43972786133", "document_non_match"),
    ],
)
def test_real_development_whole_archive_to_exact_condition(minimum: str, status: str) -> None:
    assert hashlib.sha256(ARCHIVE).hexdigest() == ORIGIN["archive_sha256"]
    assert hashlib.sha256(main_bytes()).hexdigest() == ORIGIN["main_document_sha256"]
    result = inspect_cash_report(D, QUERY, "individual", Decimal(minimum), ARCHIVE, NOW)
    assert result.status == status
    assert isinstance(result.value, CashValue)
    # Existing source answer, fixed before this pipeline existed.
    assert result.value.amount_krw == Decimal("43972786132")
    assert result.value.raw_amount.raw_value == "43,972,786,132"
    assert result.value.raw_amount.unit == "원"
    assert result.document_sha256 == ORIGIN["main_document_sha256"]
    assert result.section is not None
    assert result.section.text.encode() in main_bytes()
    assert result.value.evidence.document_sha256 != result.section.sha256
    assert "BS_S" in result.value.evidence.locator
    assert "table[2]/tr[14]/td[2]" in result.value.evidence.locator
    report = result.to_dict()
    assert report["run_scope"] == "specified_report_only"
    assert report["latest_correction_verified"] is False
    assert report["basis_origin"] == "supplied_upstream"
    assert report["amount_krw"] == "43972786132"


def test_attachment_is_not_used_when_main_is_missing() -> None:
    result = inspect_cash_report(
        D, QUERY, "individual", Decimal(0), packed(None, main_bytes()), NOW
    )
    assert result.status == "needs_review"
    assert result.failure == "main_document_missing"
    assert result.to_dict()["amount_krw"] is None


def test_modified_main_company_cannot_use_another_company_table() -> None:
    raw = main_bytes().replace(b'AREGCIK="00113128"', b'AREGCIK="00000001"', 1)
    result = inspect_cash_report(D, QUERY, "individual", Decimal(0), packed(raw), NOW)
    assert result.failure == "document_company_mismatch"
    assert result.status == "needs_review" and result.value is None


def test_wrong_requested_company_is_rejected_before_archive_processing() -> None:
    with pytest.raises(ValueError, match="request_company"):
        inspect_cash_report(
            D, replace(QUERY, corp_code="00000001"), "individual", Decimal(0), b"not zip", NOW
        )


def test_no_consolidated_group_does_not_fall_back_to_individual() -> None:
    result = inspect_cash_report(
        D,
        CashQuery(D.corp_code, QUERY.as_of, "consolidated"),
        "consolidated",
        Decimal(0),
        ARCHIVE,
        NOW,
    )
    assert result.status == "needs_review"
    assert result.failure == "missing_or_ambiguous_balance_group"


def test_modified_duplicate_group_is_not_resolved_by_first_occurrence() -> None:
    raw = main_bytes()
    section = find_balance_section(raw, D.corp_code, "individual")
    raw = raw.replace(b"</DOCUMENT>", section.text.encode() + b"</DOCUMENT>")
    result = inspect_cash_report(D, QUERY, "individual", Decimal(0), packed(raw), NOW)
    assert result.status == "needs_review"
    assert result.failure == "missing_or_ambiguous_balance_group"


def test_requested_date_missing_is_not_a_zero_or_non_match() -> None:
    result = inspect_cash_report(
        D, replace(QUERY, as_of=date(2022, 12, 31)), "individual", Decimal(0), ARCHIVE, NOW
    )
    assert result.status == "needs_review"
    assert result.value is not None and result.value.status == "needs_review"
    assert result.to_dict()["failure"] == "period_unavailable"
    assert result.to_dict()["amount_krw"] is None


def test_modified_missing_unit_is_not_a_condition_result() -> None:
    raw = main_bytes()
    section = find_balance_section(raw, D.corp_code, "individual")
    changed = section.text.replace("(단위 : 원)", "(단위 : 알 수 없음)")
    assert changed != section.text
    raw = raw.replace(section.text.encode(), changed.encode())
    result = inspect_cash_report(D, QUERY, "individual", Decimal(0), packed(raw), NOW)
    assert result.status == "needs_review" and result.to_dict()["amount_krw"] is None
    assert result.to_dict()["failure"] == "extraction_failed"
    assert result.to_dict()["currency"] is None
    assert result.to_dict()["requested_currency"] == "KRW"


@pytest.mark.parametrize("minimum", [Decimal(-1), Decimal("NaN"), Decimal("Infinity")])
def test_invalid_condition_is_not_coerced(minimum: Decimal) -> None:
    with pytest.raises(ValueError, match="nonnegative_exact"):
        inspect_cash_report(D, QUERY, "individual", minimum, ARCHIVE, NOW)


def test_future_publication_is_not_eligible_for_specified_run() -> None:
    with pytest.raises(ValueError, match="future_publication"):
        inspect_cash_report(
            replace(D, filed_on=date(2026, 11, 26)), QUERY, "individual", Decimal(0), ARCHIVE, NOW
        )


@pytest.mark.parametrize(
    "raw,reason",
    [
        (b"<!DOCTYPE DOCUMENT><DOCUMENT></DOCUMENT>", "unsafe_document_declaration"),
        (b"\xff", "unsupported_document_encoding"),
        (b'<DOCUMENT><COMPANY-NAME AREGCIK="00113128"/></DOCUMENT>', "unsupported_report_kind"),
    ],
)
def test_unsupported_source_forms_are_explicit(raw: bytes, reason: str) -> None:
    result = inspect_cash_report(D, QUERY, "individual", Decimal(0), packed(raw), NOW)
    assert result.status == "needs_review" and result.failure == reason


def test_nested_or_unfinished_groups_do_not_pass() -> None:
    prefix = b'<DOCUMENT><DOCUMENT-NAME ACODE="11011"/><COMPANY-NAME AREGCIK="00113128"/>'
    for suffix in [
        b"<TABLE-GROUP><TABLE-GROUP></TABLE-GROUP></TABLE-GROUP></DOCUMENT>",
        b'<TABLE-GROUP ACLASS="{XBRL}BS_S"></DOCUMENT>',
    ]:
        result = inspect_cash_report(
            D, QUERY, "individual", Decimal(0), packed(prefix + suffix), NOW
        )
        assert result.status == "needs_review" and result.value is None


def test_invalid_archive_has_no_success_value() -> None:
    result = inspect_cash_report(D, QUERY, "individual", Decimal(0), b"not a ZIP", NOW)
    assert result.status == "needs_review" and result.to_dict()["amount_krw"] is None


def test_modified_unicode_line_separator_does_not_shift_raw_section_offsets() -> None:
    raw = main_bytes().replace(b"<SUMMARY>", "<P>앞문장\u2028뒷문장</P><SUMMARY>".encode(), 1)
    assert raw != main_bytes()
    result = inspect_cash_report(D, QUERY, "individual", Decimal(0), packed(raw), NOW)
    assert isinstance(result.value, CashValue)
    assert result.value.amount_krw == Decimal("43972786132")
    assert result.section is not None and result.section.text.encode() in raw

    assert result.section.text.startswith('<TABLE-GROUP ACLASS="{XBRL}BS_S">')
    assert result.section.text.endswith("</TABLE-GROUP>")
