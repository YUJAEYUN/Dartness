"""Cash query contract v1. Structural validation is not disclosure verification."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from dartness.amounts import AmountInput, NormalizedAmount, normalize_krw_amount

type CashScope = Literal["standalone", "consolidated"]
type CashBasis = Literal["separate", "individual", "consolidated"]
type ReviewReason = Literal[
    "api_missing",
    "no_financial_statements",
    "period_unavailable",
    "extraction_failed",
    "basis_unavailable",
    "transport_error",
]
_REASONS = {
    "api_missing",
    "no_financial_statements",
    "period_unavailable",
    "extraction_failed",
    "basis_unavailable",
    "transport_error",
}


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("nonempty text required")


@dataclass(frozen=True)
class CashQuery:
    corp_code: str
    as_of: date
    scope: CashScope = "standalone"
    contract_version: Literal["cash-v1"] = field(default="cash-v1", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.corp_code, str) or not re.fullmatch(r"[0-9]{8}", self.corp_code):
            raise ValueError("corp_code must be the eight-digit DART identifier")
        if type(self.as_of) is not date:
            raise ValueError("explicit financial date required")
        if self.scope not in ("standalone", "consolidated"):
            raise ValueError("unsupported scope")


@dataclass(frozen=True)
class CashEvidence:
    source_url: str
    document_sha256: str
    locator: str
    context: str
    receipt_number: str | None = None

    def __post_init__(self) -> None:
        _text(self.source_url)
        url = urlsplit(self.source_url)
        if (
            url.scheme != "https"
            or url.hostname not in ("dart.fss.or.kr", "opendart.fss.or.kr", "kind.krx.co.kr")
            or url.username
            or url.password
            or url.port not in (None, 443)
        ):
            raise ValueError("official disclosure URL required")
        if not isinstance(self.document_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.document_sha256
        ):
            raise ValueError("full document SHA-256 required")
        if self.receipt_number is not None and (
            not isinstance(self.receipt_number, str)
            or not re.fullmatch(r"[0-9]{14}", self.receipt_number)
        ):
            raise ValueError("DART receipt number must contain fourteen digits")
        _text(self.locator)
        _text(self.context)


@dataclass(frozen=True)
class CashValue:
    query: CashQuery
    basis: CashBasis
    as_of: date
    raw_amount: AmountInput
    amount_krw: Decimal
    evidence: CashEvidence
    currency: Literal["KRW"] = "KRW"
    status: Literal["value"] = field(default="value", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.query, CashQuery) or not isinstance(self.evidence, CashEvidence):
            raise ValueError("validated query and evidence required")
        if type(self.as_of) is not date or self.as_of != self.query.as_of:
            raise ValueError("financial date must match the request")
        allowed = (
            ("separate", "individual") if self.query.scope == "standalone" else ("consolidated",)
        )
        if self.basis not in allowed:
            raise ValueError("financial basis must match the request")
        if self.currency != "KRW" or not isinstance(self.raw_amount, AmountInput):
            raise ValueError("v1 requires explicit KRW amount input")
        if not isinstance(self.amount_krw, Decimal) or not self.amount_krw.is_finite():
            raise ValueError("finite exact decimal required")
        if not isinstance(self.raw_amount.raw_value, str) or (
            self.raw_amount.unit is not None and not isinstance(self.raw_amount.unit, str)
        ):
            raise ValueError("original value and unit must be text")
        normalized = normalize_krw_amount(self.raw_amount)
        if not isinstance(normalized, NormalizedAmount) or normalized.amount_krw != self.amount_krw:
            raise ValueError("amount must equal exact normalization of the original value")


@dataclass(frozen=True)
class CashNeedsReview:
    query: CashQuery
    reason: ReviewReason
    checked_at: datetime
    checked_path: str
    detail: str
    next_action: str
    evidence: CashEvidence | None = None
    status: Literal["needs_review"] = field(default="needs_review", init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.query, CashQuery)
            or not isinstance(self.reason, str)
            or self.reason not in _REASONS
        ):
            raise ValueError("validated query and supported review reason required")
        if not isinstance(self.checked_at, datetime) or self.checked_at.utcoffset() is None:
            raise ValueError("timezone-aware check time required")
        for text in (self.checked_path, self.detail, self.next_action):
            _text(text)
        if self.evidence is not None and not isinstance(self.evidence, CashEvidence):
            raise ValueError("validated evidence required when provided")


type CashResult = CashValue | CashNeedsReview
