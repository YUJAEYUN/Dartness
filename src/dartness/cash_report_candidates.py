"""Build dated cash candidates from supplied annual-report archives, not a complete universe."""

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime

from dartness.cash_contract import CashBasis, CashEvidence, CashQuery, CashScope, CashValue
from dartness.cash_table import cash_table_dates, extract_cash_table
from dartness.dart_smoke import CollectionError, read_archive
from dartness.disclosure_candidate import CandidateKey, CandidateSource, DisclosureCandidate
from dartness.disclosure_list import Disclosure
from dartness.report_section import find_balance_section


@dataclass(frozen=True)
class StoredCashReport:
    disclosure: Disclosure
    archive: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.disclosure, Disclosure) or not isinstance(self.archive, bytes):
            raise ValueError("disclosure_and_archive_required")
        if not isinstance(self.disclosure.receipt, str) or not re.fullmatch(
            r"[0-9]{14}", self.disclosure.receipt
        ):
            raise ValueError("fourteen_digit_receipt_required")
        if not all(
            isinstance(text, str) for text in (self.disclosure.report_name, self.disclosure.remarks)
        ):
            raise ValueError("filing_status_text_required")
        if type(self.disclosure.filed_on) is not date:
            raise ValueError("publication_date_required")


@dataclass(frozen=True)
class ReportCashCandidates:
    report: StoredCashReport
    candidates: tuple[DisclosureCandidate, ...]
    failure: str | None = None
    excluded_after_cutoff: bool = False

    def to_dict(self) -> dict[str, object]:
        disclosure = self.report.disclosure
        return {
            "receipt": disclosure.receipt,
            "corp_code": disclosure.corp_code,
            "company_name": disclosure.corp_name,
            "report_name": disclosure.report_name,
            "remarks": disclosure.remarks,
            "published_on": disclosure.filed_on.isoformat(),
            "source_url": disclosure.source_url,
            "archive_sha256": hashlib.sha256(self.report.archive).hexdigest(),
            "failure": self.failure,
            "excluded_after_cutoff": self.excluded_after_cutoff,
            "candidate_count": len(self.candidates),
        }


def read_cash_candidates(
    report: StoredCashReport,
    key: CandidateKey,
    basis: CashBasis,
    checked_at: datetime,
    *,
    report_code: str = "11011",
) -> ReportCashCandidates:
    """Require a supported complete period set; never drop a failed comparison column."""
    disclosure = report.disclosure
    if key != CandidateKey(key.corp_code, "cash", "cash-and-cash-equivalents", basis, "KRW"):
        raise ValueError("cash_candidate_key_mismatch")
    if disclosure.corp_code != key.corp_code:
        raise ValueError("request_company_mismatch")
    candidates: list[DisclosureCandidate] = []
    try:
        files = read_archive(report.archive)
        document_id = f"{disclosure.receipt}.xml"
        if document_id not in files:
            raise ValueError("main_document_missing")
        document = files[document_id]
        digest = hashlib.sha256(document).hexdigest()
        section = find_balance_section(document, key.corp_code, basis, report_code=report_code)
        evidence = CashEvidence(
            disclosure.source_url,
            digest,
            section.locator,
            "지정 공시 본문의 명시적 재무상태표 구역",
            disclosure.receipt,
        )
        for actual_date in cash_table_dates(section.text):
            scope: CashScope = "consolidated" if basis == "consolidated" else "standalone"
            value = extract_cash_table(
                CashQuery(key.corp_code, actual_date, scope),
                section.text,
                basis,
                evidence,
                checked_at,
            )
            if not isinstance(value, CashValue):
                raise ValueError(
                    f"cash_column_unavailable:{actual_date}:{value.reason}:{value.detail}"
                )
            source = CandidateSource(
                document_id,
                disclosure.filed_on,
                disclosure.source_url,
                digest,
                value.evidence.locator,
                value.evidence.context,
            )
            candidates.append(DisclosureCandidate(key, actual_date, source))
    except (CollectionError, ValueError) as error:
        return ReportCashCandidates(report, (), str(error))
    return ReportCashCandidates(report, tuple(candidates))
