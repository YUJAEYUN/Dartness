"""Developer checkpoint: specified report ZIP to cash condition evidence, not final selection."""

import argparse
import hashlib
import json
import re
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from dartness.cash_contract import (
    CashBasis,
    CashEvidence,
    CashQuery,
    CashScope,
    CashValue,
)
from dartness.cash_report_result import CashReportResult
from dartness.cash_table import extract_cash_table
from dartness.cash_viewer import fetch_dart_viewer, verify_cash_viewer
from dartness.cash_workbook import write_cash_report_workbook
from dartness.dart_smoke import CollectionError, read_archive
from dartness.disclosure_list import Disclosure
from dartness.report_section import find_balance_section


def inspect_cash_report(
    disclosure: Disclosure,
    query: CashQuery,
    basis: CashBasis,
    minimum_krw: Decimal,
    archive: bytes,
    checked_at: datetime,
    *,
    report_code: str = "11011",
) -> CashReportResult:
    if not isinstance(disclosure, Disclosure) or not isinstance(query, CashQuery):
        raise ValueError("disclosure_and_cash_query_required")
    if disclosure.corp_code != query.corp_code:
        raise ValueError("request_company_mismatch")
    if not isinstance(checked_at, datetime) or checked_at.utcoffset() is None:
        raise ValueError("aware_check_time_required")
    if not isinstance(minimum_krw, Decimal) or not minimum_krw.is_finite() or minimum_krw < 0:
        raise ValueError("nonnegative_exact_minimum_required")
    if not isinstance(disclosure.receipt, str) or not re.fullmatch(
        r"[0-9]{14}", disclosure.receipt
    ):
        raise ValueError("fourteen_digit_receipt_required")
    if type(disclosure.filed_on) is not date:
        raise ValueError("publication_date_required")
    cutoff = checked_at.astimezone(ZoneInfo("Asia/Seoul")).date()
    if max(disclosure.filed_on, query.as_of) > cutoff:
        raise ValueError("future_publication_or_financial_date")
    section, value, digest, failure = None, None, None, None
    try:
        files = read_archive(archive)
        main_name = f"{disclosure.receipt}.xml"
        if main_name not in files:
            raise CollectionError("main_document_missing")
        document = files[main_name]
        digest = hashlib.sha256(document).hexdigest()
        section = find_balance_section(document, query.corp_code, basis, report_code=report_code)
        evidence = CashEvidence(
            disclosure.source_url,
            digest,
            section.locator,
            "지정 공시 본문의 명시적 재무상태표 구역",
            disclosure.receipt,
        )
        value = extract_cash_table(query, section.text, basis, evidence, checked_at)
    except (CollectionError, ValueError) as error:
        failure = str(error)
    return CashReportResult(
        disclosure, query, basis, minimum_krw, checked_at, digest, section, value, failure
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--corp-code", required=True)
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--published-on", type=date.fromisoformat, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--basis", choices=["separate", "individual", "consolidated"], required=True
    )
    parser.add_argument("--minimum-krw", type=Decimal, required=True)
    parser.add_argument("--checked-at", type=datetime.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--viewer-main", type=Path)
    parser.add_argument("--viewer-section", type=Path)
    args = parser.parse_args()
    if (args.viewer_main is None) != (args.viewer_section is None):
        parser.error("--viewer-main and --viewer-section must be supplied together")
    if args.output.suffix.lower() != ".json":
        parser.error("--output must be a JSON path; XLSX is saved alongside it")
    scope: CashScope = "consolidated" if args.basis == "consolidated" else "standalone"
    disclosure = Disclosure(
        args.receipt, args.corp_code, args.company_name, "", "", "", args.published_on, "", ""
    )
    result = inspect_cash_report(
        disclosure,
        CashQuery(args.corp_code, args.as_of, scope),
        args.basis,
        args.minimum_krw,
        args.archive.read_bytes(),
        args.checked_at,
    )
    viewer_main: Path | None = args.viewer_main
    viewer_section: Path | None = args.viewer_section
    if result.status == "document_match" and isinstance(result.value, CashValue):
        try:
            main_page = (
                viewer_main.read_bytes()
                if viewer_main is not None
                else fetch_dart_viewer(disclosure.source_url)
            )

            def fetch_section(url: str) -> bytes:
                if viewer_section is not None:
                    return viewer_section.read_bytes()
                return fetch_dart_viewer(url)

            link = verify_cash_viewer(result.value, main_page, fetch_section, args.checked_at)
            result = replace(result, viewer_link=link)
        except (ValueError, OSError) as error:
            # Link failure never changes the cash value/condition; explicitly mark the fallback.
            failure = str(error) if isinstance(error, ValueError) else "viewer_file_error"
            result = replace(result, viewer_link_failure=failure)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n")
    write_cash_report_workbook(result, args.output.with_suffix(".xlsx"))
    print(f"Specified report checkpoint: {result.status}; latest correction not verified")
    if result.status == "document_match":
        print(
            "Table link: verified"
            if result.viewer_link
            else f"Table link: unverified ({result.viewer_link_failure})"
        )
    return 2 if result.status == "needs_review" else 0


if __name__ == "__main__":
    raise SystemExit(main())
