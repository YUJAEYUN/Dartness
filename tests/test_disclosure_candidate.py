"""Synthetic scope/provenance cases fixed in docs before the selector exists."""

from dataclasses import FrozenInstanceError, asdict, replace
from datetime import UTC, date, datetime
from typing import Any, cast

import pytest

from dartness.disclosure_candidate import (
    CandidateKey,
    CandidateRequest,
    CandidateSelection,
    CandidateSource,
    DisclosureCandidate,
    select_candidate,
)
from dartness.query_contract import DateNeedsReview, QueryRun, SelectedDate, SnapshotRequest


def key() -> CandidateKey:
    return CandidateKey("00359395", "cash", "cash-and-cash-equivalents", "separate", "KRW")


def source() -> CandidateSource:
    # Synthetic identifiers/hash/context; no claim to have downloaded this document.
    return CandidateSource(
        "synthetic-report-a",
        date(2026, 10, 20),
        "https://dart.fss.or.kr/dsaf001/main.do",
        "a" * 64,
        "재무상태표 / 현금및현금성자산 / 2026-06-30 열",
        "합성 예시: 별도재무제표, 단위 원",
    )


def request() -> CandidateRequest:
    return CandidateRequest(
        QueryRun(
            SnapshotRequest("cash", "as_of", 6, date(2026, 9, 30)),
            datetime(2026, 11, 23, 1, tzinfo=UTC),
        ),
        key(),
    )


def candidate() -> DisclosureCandidate:
    return DisclosureCandidate(key(), date(2026, 6, 30), source())


def test_prior_candidate_preserves_request_and_entire_provenance() -> None:
    wanted, original = request(), candidate()
    result = select_candidate(wanted, [original])
    assert result.status == "selected"
    assert result.reason is None
    assert result.candidate is original
    assert result.candidates == (original,)
    assert result.request is wanted
    assert result.request.run.request.as_of == date(2026, 9, 30)
    assert isinstance(result.date_selection, SelectedDate)
    assert result.date_selection.actual_date == date(2026, 6, 30)
    assert result.date_selection.is_prior is True
    assert result.candidate.source.document_id == "synthetic-report-a"
    assert result.candidate.source.document_sha256 == "a" * 64
    assert result.candidate.source.locator == source().locator
    assert result.candidate.source.context == source().context
    assert result.candidate.source.source_url == source().source_url
    assert result.candidate.source.published_on == date(2026, 10, 20)
    assert "amount_krw" not in asdict(result)


@pytest.mark.parametrize(
    "change",
    [
        {"corp_code": "00000001"},
        {"query_type": "try-assets"},
        {"item_key": "other-asset"},
        {"basis": "consolidated"},
        {"basis": "individual"},
        {"currency": "TRY"},
    ],
)
def test_mixed_scope_is_rejected_even_with_a_usable_candidate(change: dict[str, Any]) -> None:
    wrong = replace(candidate(), key=replace(key(), **change))
    for values in ([wrong, candidate()], [candidate(), wrong]):
        with pytest.raises(ValueError, match="target"):
            select_candidate(request(), values)


def test_request_type_must_match_run() -> None:
    with pytest.raises(ValueError, match="query type"):
        replace(request(), key=replace(key(), query_type="us-bonds"))


@pytest.mark.parametrize("query_type", ["try-assets", "us-bonds"])
def test_other_snapshot_types_have_no_cash_defaults(query_type: Any) -> None:
    target = replace(key(), query_type=query_type, item_key="explicit-item", currency="USD")
    run = QueryRun(SnapshotRequest(query_type, "latest", 6), request().run.executed_at)
    wanted = CandidateRequest(run, target)
    original = replace(candidate(), key=target)
    assert select_candidate(wanted, [original]).candidate is original


def test_latest_exact_and_window_boundary_use_existing_date_policy() -> None:
    exact = replace(candidate(), actual_date=date(2026, 9, 30))
    prior = candidate()
    assert select_candidate(request(), [prior, exact]).candidate is exact
    assert select_candidate(request(), [exact, prior]).candidate is exact
    start = replace(candidate(), actual_date=date(2026, 3, 30))
    before = replace(candidate(), actual_date=date(2026, 3, 29))
    after = replace(candidate(), actual_date=date(2026, 10, 1))
    assert select_candidate(request(), [after, before, start]).candidate is start
    latest = CandidateRequest(
        QueryRun(SnapshotRequest("cash", "latest", 6), request().run.executed_at), key()
    )
    assert select_candidate(latest, [prior, exact]).candidate is exact
    zero = replace(
        request(),
        run=QueryRun(replace(request().run.request, max_age_months=0), request().run.executed_at),
    )
    assert select_candidate(zero, [prior]).reason == "period_unavailable"


@pytest.mark.parametrize("which", ["id", "hash", "locator", "publication", "context", "url"])
def test_different_candidates_at_same_date_are_never_picked_by_order(which: str) -> None:
    first = replace(candidate(), actual_date=date(2026, 9, 30))
    changes: dict[str, Any] = {
        "id": {"document_id": "synthetic-correction"},
        "hash": {"document_sha256": "b" * 64},
        "locator": {"locator": "다른 표"},
        "publication": {"published_on": date(2026, 11, 22)},
        "context": {"context": "별도 표의 다른 문맥"},
        "url": {"source_url": "https://opendart.fss.or.kr/api/document.xml"},
    }
    second = replace(first, source=replace(first.source, **changes[which]))
    for inputs in ((first, second, candidate()), (candidate(), second, first)):
        result = select_candidate(request(), inputs)
        assert result.status == "needs_review"
        assert result.reason == "ambiguous_candidate"
        assert result.candidate is None
        assert result.candidates == inputs
        assert isinstance(result.date_selection, SelectedDate)
        assert result.date_selection.actual_date == date(2026, 9, 30)
        assert not hasattr(result, "amount_krw")


def test_only_identical_full_record_repetitions_are_deduplicated() -> None:
    first, copy = candidate(), replace(candidate())
    inputs = [first, copy]
    result = select_candidate(request(), inputs)
    inputs.clear()
    assert result.status == "selected"
    assert result.candidate == first
    assert result.candidates == (first, copy)


def test_newer_unique_date_is_not_blocked_by_older_ambiguity() -> None:
    first = candidate()
    other = replace(first, source=replace(source(), document_id="other-report"))
    latest = replace(candidate(), actual_date=date(2026, 9, 30))
    assert select_candidate(request(), [first, other, latest]).candidate is latest


def test_publication_cutoff_uses_execution_date_not_financial_reference() -> None:
    on_cutoff = replace(candidate(), source=replace(source(), published_on=date(2026, 11, 23)))
    after = replace(candidate(), source=replace(source(), published_on=date(2026, 11, 24)))
    result = select_candidate(request(), [after, on_cutoff])
    assert result.candidate is on_cutoff
    assert result.candidates == (after, on_cutoff)
    # The selected report was published after the financial reference date.
    assert result.candidate.source.published_on > result.request.run.anchor_date


@pytest.mark.parametrize("case", ["empty", "too_old", "future_date", "future_publication"])
def test_unavailable_preserves_inputs_without_date_or_value_fabrication(case: str) -> None:
    cases = {
        "empty": [],
        "too_old": [replace(candidate(), actual_date=date(2026, 3, 29))],
        "future_date": [replace(candidate(), actual_date=date(2026, 10, 1))],
        "future_publication": [
            replace(candidate(), source=replace(source(), published_on=date(2026, 11, 24)))
        ],
    }
    inputs = cases[case]
    result = select_candidate(request(), inputs)
    assert result.status == "needs_review"
    assert result.reason == "period_unavailable"
    assert result.candidate is None
    assert result.candidates == tuple(inputs)
    assert isinstance(result.date_selection, DateNeedsReview)
    assert not hasattr(result.date_selection, "actual_date")
    assert not hasattr(result, "amount_krw")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("corp_code", "123"),
        ("corp_code", 12345678),
        ("query_type", "stock-collateral-loan"),
        ("item_key", " "),
        ("basis", None),
        ("currency", "krw"),
        ("currency", "USDD"),
    ],
)
def test_invalid_target_fields_are_rejected(field: str, value: Any) -> None:
    with pytest.raises(ValueError):
        replace(key(), **{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("document_id", ""),
        ("document_sha256", "a" * 63),
        ("document_sha256", "z" * 64),
        ("locator", " "),
        ("context", None),
        ("published_on", "2026-10-20"),
        ("published_on", request().run.executed_at),
        ("source_url", "http://dart.fss.or.kr/"),
        ("source_url", "https://dart.fss.or.kr.example.com/"),
        ("source_url", "https://user:password@dart.fss.or.kr/"),
        ("source_url", "https://dart.fss.or.kr:8443/"),
        ("source_url", "https://[invalid"),
    ],
)
def test_missing_or_malformed_provenance_is_rejected(field: str, value: Any) -> None:
    with pytest.raises(ValueError):
        replace(source(), **{field: value})


@pytest.mark.parametrize(
    "url", ["https://dart.fss.or.kr/", "https://opendart.fss.or.kr/", "https://kind.krx.co.kr/"]
)
def test_official_hosts_are_allowed_without_online_verification(url: str) -> None:
    assert replace(source(), source_url=url).source_url == url


def test_invalid_nested_objects_or_candidates_are_rejected() -> None:
    with pytest.raises(ValueError, match="QueryRun"):
        replace(request(), run=cast(QueryRun, None))
    with pytest.raises(ValueError, match="CandidateKey"):
        replace(request(), key=cast(CandidateKey, None))
    with pytest.raises(ValueError, match="CandidateKey"):
        replace(candidate(), key=cast(CandidateKey, None))
    with pytest.raises(ValueError, match="CandidateSource"):
        replace(candidate(), source=cast(CandidateSource, {}))
    with pytest.raises(ValueError, match="date"):
        replace(candidate(), actual_date=cast(date, request().run.executed_at))
    with pytest.raises(ValueError, match="CandidateRequest"):
        select_candidate(cast(CandidateRequest, None), [])
    with pytest.raises(ValueError, match="DisclosureCandidate"):
        select_candidate(request(), [candidate(), cast(DisclosureCandidate, None)])
    with pytest.raises(ValueError, match="tuple"):
        CandidateSelection(request(), cast(tuple[DisclosureCandidate, ...], [candidate()]))


def test_results_are_immutable_and_derived_not_caller_supplied() -> None:
    result = select_candidate(request(), [candidate()])
    with pytest.raises(FrozenInstanceError):
        result.candidate = None  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        candidate().source.locator = "rewritten"  # type: ignore[misc]
    with pytest.raises(TypeError):
        CandidateSelection(request(), (), status="selected")  # type: ignore[call-arg]
    changed = replace(result, candidates=())
    assert changed.status == "needs_review"
    assert changed.candidate is None
