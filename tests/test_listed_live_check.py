"""Bounded manual checks and reports; tests inject fake public API responses, never secrets."""

import json
from datetime import timedelta
from pathlib import Path

import pytest
from test_listed_universe import EXECUTED, NOW, FakeDart

from dartness.dart_smoke import CollectionError
from dartness.listed_live_check import MAX_SECONDS, main, run_check


def test_probe_is_not_full_success_and_exposes_request_estimate() -> None:
    fetch = FakeDart()
    result = run_check("probe", 20, EXECUTED, fetch=fetch, clock=lambda: NOW)
    assert result["status"] == "probe_only"
    assert result["candidate_count"] == 3
    assert result["estimated_full_requests"] == 5
    assert result["requests_attempted"] == 5
    assert result["responses_received"] == 5
    assert result["full_population_or_pagination_complete"] is False
    assert "not retained" not in json.dumps(result)


def test_full_runs_the_actual_composition_and_retains_only_needed_fields() -> None:
    result = run_check("full", 5, EXECUTED, fetch=FakeDart(), clock=lambda: NOW)
    assert result["status"] == "complete_listing"
    assert result["company_count"] == 3
    assert result["market_counts"] == {"Y": 1, "K": 1, "N": 1}
    assert result["matched_filing_count"] == 1
    assert result["outside_filings_count"] == 1
    assert result["no_filings"] == ("00000002", "00000003")
    assert result["search_date"] == "2026-11-24"
    assert result["financial_or_correction_verification"] is False
    assert "not retained" not in json.dumps(result)


@pytest.mark.parametrize("mode,budget", [("off", 20), ("probe", 21), ("full", 5001), ("full", 0)])
def test_unapproved_mode_or_budget_never_calls_api(mode: str, budget: int) -> None:
    fetch = FakeDart()
    with pytest.raises(ValueError):
        run_check(mode, budget, EXECUTED, fetch=fetch, clock=lambda: NOW)
    assert fetch.calls == []


def test_probe_budget_failure_is_not_probe_success() -> None:
    fetch = FakeDart()
    result = run_check("probe", 2, EXECUTED, fetch=fetch, clock=lambda: NOW)
    assert result["status"] == "failed"
    assert result["error_code"] == "live_request_budget"
    assert result["requests_attempted"] == len(fetch.calls) == 2
    assert result["full_population_or_pagination_complete"] is False


def test_transport_failure_keeps_stage_and_does_not_claim_a_response() -> None:
    def fail(endpoint: str, params: dict[str, str]) -> bytes:
        raise CollectionError("network_error")

    reports: list[dict[str, object]] = []
    result = run_check("full", 5, EXECUTED, fetch=fail, clock=lambda: NOW, progress=reports.append)
    assert result["status"] == "failed"
    assert result["error_code"] == "network_error"
    assert result["requests_attempted"] == 1
    assert result["responses_received"] == 0
    assert result["last_request"] == {"endpoint": "corpCode.xml"}
    assert reports[-1]["status"] == "failed"


def test_report_keeps_only_field_types_not_upstream_messages() -> None:
    fetch = FakeDart()
    fetch.profiles["00000001"] = b'{"status":"020","message":"not for output"}'
    result = run_check("probe", 20, EXECUTED, fetch=fetch, clock=lambda: NOW)
    assert result["status"] == "failed"
    assert result["error_code"] == "rate_limit"
    assert "not for output" not in json.dumps(result)


def test_internal_deadline_stops_before_first_request() -> None:
    values = iter([0.0, float(MAX_SECONDS)])
    fetch = FakeDart()
    result = run_check(
        "full", 5, EXECUTED, fetch=fetch, clock=lambda: NOW, monotonic=lambda: next(values)
    )
    assert result["error_code"] == "live_time_limit"
    assert fetch.calls == []


def test_probe_also_rejects_observation_on_another_day() -> None:
    fetch = FakeDart()
    result = run_check("probe", 20, EXECUTED, fetch=fetch, clock=lambda: NOW + timedelta(days=1))
    assert result["status"] == "failed"
    assert result["error_code"] == "universe_date_changed"
    assert fetch.calls == []


def test_missing_key_writes_failure_without_network_or_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DART_API_KEY", raising=False)
    assert main() == 1
    report = json.loads((tmp_path / "work/listed-live-check/report.json").read_text())
    assert report["status"] == "failed"


def test_console_summary_keeps_estimate_but_omits_company_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    result = run_check("probe", 20, EXECUTED, fetch=FakeDart(), clock=lambda: NOW)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DART_API_KEY", "x" * 40)
    monkeypatch.setattr("dartness.listed_live_check.run_check", lambda *args, **kwargs: result)
    assert main() == 0
    output = capsys.readouterr().out
    summary = json.loads(output.split("Live check summary: ")[1])
    assert summary["candidate_count"] == 3
    assert summary["estimated_full_requests"] == 5
    assert summary["status"] == "probe_only"
    assert "profile_samples" not in output
    assert "00000001" not in output
    assert "x" * 40 not in output
