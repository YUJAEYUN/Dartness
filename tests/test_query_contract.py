"""Synthetic expectations fixed from the calendar contract before implementation."""

from dataclasses import FrozenInstanceError, asdict, replace
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any, cast

import pytest
from doc_examples import DocExample, check_example, load_examples

from dartness.query_contract import (
    DateNeedsReview,
    QueryRun,
    SelectedDate,
    SnapshotRequest,
    select_date,
)

EXECUTED = datetime(2026, 11, 23, 1, tzinfo=UTC)


def run_example(data: dict[str, Any]) -> QueryRun | SelectedDate | DateNeedsReview:
    request = SnapshotRequest(
        query_type="cash",
        mode=data["mode"],
        max_age_months=data["months"],
        as_of=date.fromisoformat(data["as_of"]) if "as_of" in data else None,
    )
    run = QueryRun(request, datetime.fromisoformat(data["executed_at"]))
    if "candidates" in data:
        return select_date(run, (date.fromisoformat(d) for d in data["candidates"]))
    return run


@pytest.mark.parametrize("example", load_examples("query-window"), ids=lambda x: x.id)
def test_documented_windows(example: DocExample) -> None:
    check_example(example, run_example)


@pytest.mark.parametrize("example", load_examples("query-date-selection"), ids=lambda x: x.id)
def test_documented_date_selection(example: DocExample) -> None:
    check_example(example, run_example)


@pytest.mark.parametrize("months", [True, False, -1, 1.5, "6", None])
def test_rejects_implicit_month_conversions(months: Any) -> None:
    with pytest.raises(ValueError, match="nonnegative integer"):
        SnapshotRequest("cash", "latest", months)


@pytest.mark.parametrize("kind", ["cash", "try-assets", "us-bonds"])
def test_snapshot_types_and_output_option(kind: Any) -> None:
    request = SnapshotRequest(kind, "latest", 3, include_review=True)
    assert request.query_type == kind
    assert request.include_review is True
    assert request.contract_version == "snapshot-v1"
    assert SnapshotRequest(kind, "latest", 3).include_review is False


@pytest.mark.parametrize("kind", ["share-compensation", "stock-collateral-loan", "other", None])
def test_unimplemented_event_requests_are_not_routed_as_cash(kind: Any) -> None:
    with pytest.raises(ValueError, match="snapshot query type"):
        SnapshotRequest(kind, "latest", 3)


@pytest.mark.parametrize("option", [0, 1, "false", None])
def test_review_option_requires_boolean(option: Any) -> None:
    with pytest.raises(ValueError, match="include_review"):
        SnapshotRequest("cash", "latest", 6, include_review=option)


@pytest.mark.parametrize(
    ("mode", "as_of", "message"),
    [
        ("latest", date(2026, 9, 30), "latest"),
        ("as_of", None, "date"),
        ("as_of", "2026-09-30", "date"),
        ("as_of", EXECUTED, "date"),
        ("unknown", None, "mode"),
    ],
)
def test_invalid_mode_date_combinations(mode: Any, as_of: Any, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        SnapshotRequest("cash", mode, 6, as_of)


def test_required_fields_cannot_be_omitted() -> None:
    with pytest.raises(TypeError):
        SnapshotRequest(query_type="cash", mode="latest")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        QueryRun(SnapshotRequest("cash", "latest", 6))  # type: ignore[call-arg]


@pytest.mark.parametrize("instant", [datetime(2026, 11, 23), date(2026, 11, 23), "now", None])
def test_run_requires_explicit_aware_timestamp(instant: Any) -> None:
    with pytest.raises(ValueError, match="timezone"):
        QueryRun(SnapshotRequest("cash", "latest", 6), instant)


def test_seoul_midnight_and_same_instant_in_other_offsets() -> None:
    request = SnapshotRequest("cash", "latest", 0)
    before = datetime(2026, 8, 30, 14, 59, 59, tzinfo=UTC)
    after = before + timedelta(seconds=1)
    assert QueryRun(request, before).execution_date == date(2026, 8, 30)
    assert QueryRun(request, after).execution_date == date(2026, 8, 31)
    assert QueryRun(
        request, after.astimezone(timezone(timedelta(hours=-7)))
    ).execution_date == date(2026, 8, 31)


def test_future_reference_is_invalid_but_past_reference_does_not_change_universe_date() -> None:
    with pytest.raises(ValueError, match="future"):
        QueryRun(SnapshotRequest("cash", "as_of", 6, date(2026, 11, 24)), EXECUTED)
    run = QueryRun(SnapshotRequest("cash", "as_of", 6, date(2020, 12, 31)), EXECUTED)
    assert run.anchor_date == date(2020, 12, 31)
    assert run.execution_date == date(2026, 11, 23)
    assert run.executed_at == EXECUTED
    assert run.earliest_date == date(2020, 6, 30)


@pytest.mark.parametrize(
    ("anchor", "months", "earliest"),
    [
        (date(2026, 3, 31), 2, date(2026, 1, 31)),  # Not two chained one-month shifts.
        (date(2024, 2, 29), 12, date(2023, 2, 28)),
        (date(2026, 1, 31), 3, date(2025, 10, 31)),
        (date(2026, 11, 23), 120, date(2016, 11, 23)),  # No invented API-month cap.
        (date(1, 1, 1), 0, date(1, 1, 1)),
    ],
)
def test_calendar_windows(anchor: date, months: int, earliest: date) -> None:
    run = QueryRun(SnapshotRequest("cash", "as_of", months, anchor), EXECUTED)
    assert run.earliest_date == earliest
    assert run.anchor_date == anchor


@pytest.mark.parametrize("months", [1, 10**100])
def test_unrepresentable_window_is_rejected_without_clamping(months: int) -> None:
    with pytest.raises(ValueError, match="date range"):
        QueryRun(SnapshotRequest("cash", "as_of", months, date(1, 1, 1)), EXECUTED)


def test_rejects_fake_run_request() -> None:
    with pytest.raises(ValueError, match="SnapshotRequest"):
        QueryRun(cast(SnapshotRequest, {}), EXECUTED)


def test_selection_is_independent_of_candidate_order_and_keeps_original_request() -> None:
    run = QueryRun(SnapshotRequest("cash", "as_of", 6, date(2026, 9, 30)), EXECUTED)
    dates = (date(2026, 3, 29), date(2026, 9, 29), date(2026, 6, 30), date(2026, 10, 1))
    for candidates in (dates, reversed(dates), iter(dates)):
        result = select_date(run, candidates)
        assert isinstance(result, SelectedDate)
        assert result.actual_date == date(2026, 9, 29)
        assert result.is_prior is True
        assert result.run == run
        assert result.run.request.as_of == date(2026, 9, 30)
        assert "amount_krw" not in asdict(result)


@pytest.mark.parametrize("dates", [(), (date(2026, 3, 29),), (date(2026, 10, 1),)])
def test_empty_or_outside_window_never_fabricates_date_or_amount(dates: tuple[date, ...]) -> None:
    run = QueryRun(SnapshotRequest("cash", "as_of", 6, date(2026, 9, 30)), EXECUTED)
    result = select_date(run, dates)
    assert isinstance(result, DateNeedsReview)
    assert result.reason == "period_unavailable"
    assert result.status == "needs_review"
    assert result.run == run
    assert not hasattr(result, "actual_date")
    assert not hasattr(result, "amount_krw")


@pytest.mark.parametrize("candidate", [EXECUTED, "2026-09-30", None, 0])
def test_bad_candidate_is_input_error_not_missing_data(candidate: Any) -> None:
    run = QueryRun(SnapshotRequest("cash", "latest", 6), EXECUTED)
    with pytest.raises(ValueError, match="candidate date"):
        select_date(run, [date(2026, 9, 30), candidate])


def test_selected_date_cannot_be_constructed_outside_window() -> None:
    run = QueryRun(SnapshotRequest("cash", "as_of", 0, date(2026, 9, 30)), EXECUTED)
    for invalid in (date(2026, 9, 29), date(2026, 10, 1), cast(date, EXECUTED)):
        with pytest.raises(ValueError, match="selected date"):
            SelectedDate(run, invalid)
    result = SelectedDate(run, date(2026, 9, 30))
    assert result.is_prior is False
    with pytest.raises(FrozenInstanceError):
        result.actual_date = date(2026, 9, 29)  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        run.anchor_date = date(2026, 9, 29)  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        run.request.max_age_months = 12  # type: ignore[misc]
    assert replace(run, request=replace(run.request, max_age_months=6)).earliest_date == date(
        2026, 3, 30
    )


def test_date_contracts_require_real_run() -> None:
    invalid = cast(QueryRun, None)
    with pytest.raises(ValueError, match="QueryRun"):
        select_date(invalid, [])
    with pytest.raises(ValueError, match="QueryRun"):
        SelectedDate(invalid, date(2026, 9, 30))
    with pytest.raises(ValueError, match="QueryRun"):
        DateNeedsReview(invalid)


def test_unrepresentable_korean_execution_date_is_input_error() -> None:
    with pytest.raises(ValueError, match="date range"):
        QueryRun(SnapshotRequest("cash", "latest", 0), datetime.max.replace(tzinfo=UTC))


def test_selected_date_can_feed_cash_contract_without_rewriting_original_request() -> None:
    # CASH-003: selected extraction date is separate from the original reference.
    from dartness.cash_contract import CashQuery

    run = QueryRun(SnapshotRequest("cash", "as_of", 6, date(2026, 9, 30)), EXECUTED)
    selected = select_date(run, [date(2026, 6, 30)])
    assert isinstance(selected, SelectedDate)
    query = CashQuery("00359395", selected.actual_date)
    assert query.as_of == date(2026, 6, 30)
    assert selected.run.request.as_of == date(2026, 9, 30)
    assert selected.is_prior is True
