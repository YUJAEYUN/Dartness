"""Snapshot request and date selection only; no collection or fact verification."""

from calendar import monthrange
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

type SnapshotType = Literal["cash", "try-assets", "us-bonds"]
type SnapshotMode = Literal["latest", "as_of"]
SEOUL = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class SnapshotRequest:
    query_type: SnapshotType
    mode: SnapshotMode
    max_age_months: int
    as_of: date | None = None
    include_review: bool = False
    contract_version: Literal["snapshot-v1"] = field(default="snapshot-v1", init=False)

    def __post_init__(self) -> None:
        if self.query_type not in ("cash", "try-assets", "us-bonds"):
            raise ValueError("unsupported snapshot query type")
        if self.mode not in ("latest", "as_of"):
            raise ValueError("unsupported snapshot mode")
        if type(self.max_age_months) is not int or self.max_age_months < 0:
            raise ValueError("max_age_months must be a nonnegative integer")
        if self.mode == "latest" and self.as_of is not None:
            raise ValueError("latest mode cannot include as_of")
        if self.mode == "as_of" and type(self.as_of) is not date:
            raise ValueError("as_of mode requires an explicit date")
        if type(self.include_review) is not bool:
            raise ValueError("include_review must be boolean")


def _subtract_months(anchor: date, months: int) -> date:
    month_index = (anchor.year - 1) * 12 + anchor.month - 1 - months
    if month_index < 0:
        raise ValueError("window exceeds representable date range")
    year, month_zero = divmod(month_index, 12)
    year += 1
    month = month_zero + 1
    return date(year, month, min(anchor.day, monthrange(year, month)[1]))


@dataclass(frozen=True)
class QueryRun:
    request: SnapshotRequest
    executed_at: datetime
    execution_date: date = field(init=False)
    anchor_date: date = field(init=False)
    earliest_date: date = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.request, SnapshotRequest):
            raise ValueError("SnapshotRequest required")
        if not isinstance(self.executed_at, datetime) or self.executed_at.utcoffset() is None:
            raise ValueError("explicit execution timestamp with timezone required")
        try:
            execution_date = self.executed_at.astimezone(SEOUL).date()
        except (OverflowError, ValueError) as error:
            raise ValueError("execution timestamp exceeds representable date range") from error
        anchor = self.request.as_of if self.request.as_of is not None else execution_date
        if anchor > execution_date:
            raise ValueError("reference date cannot be in the future")
        earliest = _subtract_months(anchor, self.request.max_age_months)
        object.__setattr__(self, "execution_date", execution_date)
        object.__setattr__(self, "anchor_date", anchor)
        object.__setattr__(self, "earliest_date", earliest)


def _require_run(run: QueryRun) -> None:
    if not isinstance(run, QueryRun):
        raise ValueError("QueryRun required")


@dataclass(frozen=True)
class SelectedDate:
    run: QueryRun
    actual_date: date
    status: Literal["selected"] = field(default="selected", init=False)
    is_prior: bool = field(init=False)

    def __post_init__(self) -> None:
        _require_run(self.run)
        if type(self.actual_date) is not date or not (
            self.run.earliest_date <= self.actual_date <= self.run.anchor_date
        ):
            raise ValueError("selected date must be within the requested window")
        object.__setattr__(self, "is_prior", self.actual_date < self.run.anchor_date)


@dataclass(frozen=True)
class DateNeedsReview:
    run: QueryRun
    status: Literal["needs_review"] = field(default="needs_review", init=False)
    reason: Literal["period_unavailable"] = field(default="period_unavailable", init=False)

    def __post_init__(self) -> None:
        _require_run(self.run)


def select_date(run: QueryRun, candidates: Iterable[date]) -> SelectedDate | DateNeedsReview:
    """Select dates already scoped to one corporation/item/basis/currency by the caller.

    This cannot establish collection completeness or choose between document versions.
    Invalid candidate types are input errors, even if another date would be usable.
    """
    _require_run(run)
    selected: date | None = None
    for candidate in candidates:
        if type(candidate) is not date:
            raise ValueError("candidate date required")
        if run.earliest_date <= candidate <= run.anchor_date:
            if selected is None or candidate > selected:
                selected = candidate
    if selected is None:
        return DateNeedsReview(run)
    return SelectedDate(run, selected)
