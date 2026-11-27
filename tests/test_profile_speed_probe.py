"""Synthetic safety checks, independent of live latency or financial answers."""

import json
import threading
import time
from pathlib import Path

import pytest

from dartness.dart_smoke import CollectionError
from dartness.profile_speed_probe import main, run_probe


def _profile(corp: str) -> bytes:
    return json.dumps(
        {
            "status": "000",
            "corp_code": corp,
            "stock_code": {"00118804": "005290", "01205842": "267270"}[corp],
            "corp_cls": "K",
            "ignored_contact": "do not retain",
        }
    ).encode()


def test_budget_pacing_identity_and_no_raw_profile_retention() -> None:
    starts: list[float] = []

    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        assert endpoint == "company.json"
        starts.append(time.monotonic())
        return _profile(params["corp_code"])

    checkpoints: list[dict[str, object]] = []
    result = run_probe(fetch, checkpoint=checkpoints.append)
    assert result["status"] == "completed_probe"
    assert result["api_requests"] == 8
    assert len(starts) == 8
    assert all(b - a >= 0.48 for a, b in zip(starts, starts[1:], strict=False))
    assert "ignored_contact" not in json.dumps(result)
    assert checkpoints[0]["api_requests"] == 1
    assert checkpoints[0]["attempts"] != result["attempts"]


@pytest.mark.parametrize("failure", ["rate_limit", "network_error"])
def test_first_failure_stops_without_retry(failure: str) -> None:
    calls = 0

    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        nonlocal calls
        calls += 1
        raise CollectionError(failure)

    result = run_probe(fetch, checkpoint=lambda report: None)
    assert result["status"] == "failed"
    assert result["api_requests"] == calls == 1
    assert failure in json.dumps(result)


def test_identity_mismatch_is_not_success() -> None:
    result = run_probe(
        lambda endpoint, params: _profile("01205842"), checkpoint=lambda report: None
    )
    assert result["status"] == "failed"
    assert result["api_requests"] == 1
    assert "profile_identity_mismatch" in json.dumps(result)


def test_concurrent_failure_drains_sibling_and_stops_later_phases() -> None:
    lock = threading.Lock()
    both_started = threading.Event()
    calls = 0
    active = 0
    peak = 0

    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        nonlocal calls, active, peak
        with lock:
            calls += 1
            position = calls
            active += 1
            peak = max(peak, active)
            if position == 4:
                both_started.set()
        try:
            if position in (3, 4):
                assert both_started.wait(3)
                if position == 3:
                    raise CollectionError("rate_limit")
            return _profile(params["corp_code"])
        finally:
            with lock:
                active -= 1

    result = run_probe(fetch, checkpoint=lambda report: None)
    assert result["status"] == "failed"
    assert result["api_requests"] == calls == 4
    assert result["max_in_flight"] == peak == 2
    assert active == 0


def test_cli_rejects_reused_output_before_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DART_API_KEY", "a" * 40)
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    assert main() == 1
    assert not (tmp_path / "report.json").exists()


def test_expanded_probe_has_eighty_attempts_and_reverses_second_round() -> None:
    # This test checks the experiment budget/order, not the public registry identities.
    from dartness.profile_speed_probe import _EXPANDED_SAMPLES

    stocks = dict(_EXPANDED_SAMPLES)
    assert len(stocks) == 20
    calls: list[str] = []
    lock = threading.Lock()

    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        corp = params["corp_code"]
        with lock:
            calls.append(corp)
        return json.dumps(
            {"status": "000", "corp_code": corp, "stock_code": stocks[corp], "corp_cls": "Y"}
        ).encode()

    result = run_probe(fetch, checkpoint=lambda report: None, expanded=True)
    assert result["status"] == "completed_probe"
    assert result["sample_size"] == 20
    assert result["api_requests"] == result["max_api_requests"] == len(calls) == 80
    assert all(calls.count(corp) == 4 for corp in stocks)
    phases = result["phases"]
    assert isinstance(phases, list)
    assert [phase["name"] for phase in phases] == [
        "round-1-workers-1",
        "round-1-workers-2",
        "round-2-workers-2",
        "round-2-workers-1",
    ]


def test_expanded_first_failure_does_not_start_remaining_samples() -> None:
    calls = 0

    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        nonlocal calls
        calls += 1
        raise CollectionError("rate_limit")

    result = run_probe(fetch, checkpoint=lambda report: None, expanded=True)
    assert result["status"] == "failed"
    assert result["max_api_requests"] == 80
    assert result["api_requests"] == calls == 1


def test_cli_rejects_unknown_sample_mode_before_creating_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PROFILE_PROBE_EXPANDED", "1000")
    output = tmp_path / "new"
    monkeypatch.setenv("OUTPUT_DIR", str(output))
    assert main() == 1
    assert not output.exists()
