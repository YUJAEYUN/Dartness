"""Validate prepared candidate metadata; do not infer facts or resolve corrections."""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Literal
from urllib.parse import urlsplit

from dartness.query_contract import (
    DateNeedsReview,
    QueryRun,
    SelectedDate,
    SnapshotType,
    select_date,
)


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"nonempty {name} required")


@dataclass(frozen=True)
class CandidateKey:
    corp_code: str
    query_type: SnapshotType
    item_key: str
    basis: str
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.corp_code, str) or not re.fullmatch(r"[0-9]{8}", self.corp_code):
            raise ValueError("eight-digit DART corp_code required")
        if self.query_type not in ("cash", "try-assets", "us-bonds"):
            raise ValueError("unsupported snapshot query type")
        _text(self.item_key, "item_key")
        _text(self.basis, "basis")
        if not isinstance(self.currency, str) or not re.fullmatch(r"[A-Z]{3}", self.currency):
            raise ValueError("three-letter uppercase currency required")


@dataclass(frozen=True)
class CandidateSource:
    document_id: str
    published_on: date
    source_url: str
    document_sha256: str
    locator: str
    context: str

    def __post_init__(self) -> None:
        _text(self.document_id, "document_id")
        if type(self.published_on) is not date:
            raise ValueError("explicit publication date required")
        _text(self.source_url, "source_url")
        try:
            url = urlsplit(self.source_url)
            valid_url = (
                url.scheme == "https"
                and url.hostname in ("dart.fss.or.kr", "opendart.fss.or.kr", "kind.krx.co.kr")
                and url.username is None
                and url.password is None
                and url.port in (None, 443)
            )
        except ValueError as error:
            raise ValueError("official disclosure URL required") from error
        if not valid_url:
            raise ValueError("official disclosure URL required")
        if not isinstance(self.document_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.document_sha256
        ):
            raise ValueError("full document SHA-256 required")
        _text(self.locator, "locator")
        _text(self.context, "context")


@dataclass(frozen=True)
class DisclosureCandidate:
    key: CandidateKey
    actual_date: date
    source: CandidateSource

    def __post_init__(self) -> None:
        if not isinstance(self.key, CandidateKey):
            raise ValueError("CandidateKey required")
        if not isinstance(self.source, CandidateSource):
            raise ValueError("CandidateSource required")
        if type(self.actual_date) is not date:
            raise ValueError("explicit actual date required")


@dataclass(frozen=True)
class CandidateRequest:
    run: QueryRun
    key: CandidateKey

    def __post_init__(self) -> None:
        if not isinstance(self.run, QueryRun):
            raise ValueError("QueryRun required")
        if not isinstance(self.key, CandidateKey):
            raise ValueError("CandidateKey required")
        if self.key.query_type != self.run.request.query_type:
            raise ValueError("target query type must match the run")


@dataclass(frozen=True)
class CandidateSelection:
    request: CandidateRequest
    candidates: tuple[DisclosureCandidate, ...]
    date_selection: SelectedDate | DateNeedsReview = field(init=False)
    candidate: DisclosureCandidate | None = field(init=False)
    status: Literal["selected", "needs_review"] = field(init=False)
    reason: Literal["period_unavailable", "ambiguous_candidate"] | None = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.request, CandidateRequest):
            raise ValueError("CandidateRequest required")
        if type(self.candidates) is not tuple:
            raise ValueError("immutable candidate tuple required")
        for candidate in self.candidates:
            if not isinstance(candidate, DisclosureCandidate):
                raise ValueError("DisclosureCandidate required")
            if candidate.key != self.request.key:
                raise ValueError("candidate must match the entire target")
        run = self.request.run
        eligible = tuple(c for c in self.candidates if c.source.published_on <= run.execution_date)
        date_selection = select_date(run, (c.actual_date for c in eligible))
        selected = None
        reason: Literal["period_unavailable", "ambiguous_candidate"] | None
        if isinstance(date_selection, DateNeedsReview):
            reason = "period_unavailable"
        else:
            selected_date = date_selection.actual_date
            unique = tuple(dict.fromkeys(c for c in eligible if c.actual_date == selected_date))
            if len(unique) == 1:
                selected = unique[0]
                reason = None
            else:
                reason = "ambiguous_candidate"
        object.__setattr__(self, "date_selection", date_selection)
        object.__setattr__(self, "candidate", selected)
        object.__setattr__(self, "status", "selected" if selected is not None else "needs_review")
        object.__setattr__(self, "reason", reason)


def select_candidate(
    request: CandidateRequest, candidates: Iterable[DisclosureCandidate]
) -> CandidateSelection:
    """Keep all supplied records; only exact repetitions are one selectable candidate."""
    return CandidateSelection(request, tuple(candidates))
