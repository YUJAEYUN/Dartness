"""Developer checkpoint: specified report ZIP to cash condition evidence, not final selection."""

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from dartness.cash_contract import (
    CashBasis,
    CashEvidence,
    CashNeedsReview,
    CashQuery,
    CashResult,
    CashScope,
    CashValue,
)
from dartness.cash_table import extract_cash_table
from dartness.dart_smoke import CollectionError, read_archive
from dartness.disclosure_list import Disclosure
from dartness.report_section import ReportSection, find_balance_section


@dataclass(frozen=True)
class CashReportResult:
    disclosure: Disclosure
    query: CashQuery
    basis: CashBasis
    minimum_krw: Decimal
    checked_at: datetime
    document_sha256: str | None
    section: ReportSection | None
    value: CashResult | None
    failure: str | None
    status: Literal["document_match", "document_non_match", "needs_review"] = field(init=False)

    def __post_init__(self) -> None:
        status: Literal["document_match", "document_non_match", "needs_review"] = "needs_review"
        if isinstance(self.value, CashValue) and self.failure is None:
            status = (
                "document_match"
                if self.value.amount_krw >= self.minimum_krw
                else "document_non_match"
            )
        object.__setattr__(self, "status", status)

    def to_dict(self) -> dict[str, object]:
        value = self.value if isinstance(self.value, CashValue) else None
        review = self.value if isinstance(self.value, CashNeedsReview) else None
        return {
            "run_scope": "specified_report_only",
            "latest_correction_verified": False,
            "status": self.status,
            "corp_code": self.disclosure.corp_code,
            "company_name": self.disclosure.corp_name,
            "receipt": self.disclosure.receipt,
            "published_on": self.disclosure.filed_on.isoformat(),
            "requested_as_of": self.query.as_of.isoformat(),
            "actual_as_of": value.as_of.isoformat() if value else None,
            "basis": self.basis,
            "basis_origin": "supplied_upstream",
            "minimum_krw": str(self.minimum_krw),
            "amount_krw": str(value.amount_krw) if value else None,
            "raw_amount": value.raw_amount.raw_value if value else None,
            "unit": value.raw_amount.unit if value else None,
            "requested_currency": "KRW",
            "currency": "KRW" if value else None,
            "source_url": self.disclosure.source_url,
            "document_sha256": self.document_sha256,
            "section_sha256": self.section.sha256 if self.section else None,
            "locator": value.evidence.locator
            if value
            else (self.section.locator if self.section else None),
            "context": value.evidence.context if value else None,
            "failure": self.failure or (review.reason if review else None),
            "detail": review.detail if review else None,
            "checked_at": self.checked_at.isoformat(),
        }


def inspect_cash_report(
    disclosure: Disclosure,
    query: CashQuery,
    basis: CashBasis,
    minimum_krw: Decimal,
    archive: bytes,
    checked_at: datetime,
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
        section = find_balance_section(document, query.corp_code, basis)
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
    args = parser.parse_args()
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
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n")
    print(f"Specified report checkpoint: {result.status}; latest correction not verified")
    return 2 if result.status == "needs_review" else 0


if __name__ == "__main__":
    raise SystemExit(main())
