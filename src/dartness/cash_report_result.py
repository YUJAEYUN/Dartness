"""Specified-report result and JSON audit record shared by execution and file output."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal

from dartness.cash_contract import CashBasis, CashNeedsReview, CashQuery, CashResult, CashValue
from dartness.disclosure_list import Disclosure
from dartness.report_section import ReportSection


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
