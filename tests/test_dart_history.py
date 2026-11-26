"""Collection-only tests with synthetic listing responses; not a latest-version test."""

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest
from test_dart_collect import KEY

from dartness import dart_collect
from dartness.dart_history import collect_history, parse_history_request
from dartness.dart_smoke import CollectionError
from dartness.disclosure_list import ListRequest

EMPTY = b'{"status":"013","message":"no data"}'


def test_month_windows_and_all_type_raw_responses_are_preserved() -> None:
    calls: list[dict[str, str]] = []

    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        assert endpoint == "list.json"
        calls.append(dict(params))
        return EMPTY

    manifest, files = collect_history(
        fetch, parse_history_request("01205842", "2026-03-18", "2026-11-26")
    )
    assert len(calls) == 9 and manifest["request_count"] == 9
    assert calls[0]["bgn_de"] == "20260318" and calls[-1]["end_de"] == "20261126"
    assert all(p["last_reprt_at"] == "N" and p["corp_code"] == "01205842" for p in calls)
    assert all("pblntf_ty" not in p and "corp_cls" not in p for p in calls)
    assert manifest["complete"] is True and manifest["items"] == []
    assert len(files) == 9 and all(payload == EMPTY for payload in files.values())
    responses = manifest["responses"]
    assert isinstance(responses, list)
    assert responses[0]["parameters"] == calls[0]
    assert responses[0]["response_sha256"] == hashlib.sha256(EMPTY).hexdigest()


@pytest.mark.parametrize("kind", ["all_companies", "market_filter", "type_filter", "over_budget"])
def test_broad_filtered_or_over_budget_request_is_not_issued(kind: str) -> None:
    request = {
        "all_companies": ListRequest(date(2026, 1, 1), date(2026, 1, 1)),
        "market_filter": ListRequest(date(2026, 1, 1), date(2026, 1, 1), "01205842", "Y"),
        "type_filter": ListRequest(date(2026, 1, 1), date(2026, 1, 1), "01205842", "", "A"),
        "over_budget": ListRequest(date(2025, 1, 1), date(2026, 11, 26), "01205842"),
    }[kind]

    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        raise AssertionError("invalid requests must fail before network activity")

    with pytest.raises(CollectionError):
        collect_history(fetch, request)


def test_failed_month_is_not_a_complete_empty_history() -> None:
    count = 0

    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        nonlocal count
        count += 1
        if count == 2:
            raise CollectionError("rate_limit")
        return EMPTY

    with pytest.raises(CollectionError, match="rate_limit"):
        collect_history(fetch, parse_history_request("01205842", "2026-03-18", "2026-11-26"))
    assert count == 2


def test_cli_history_has_no_document_or_financial_api_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DART_API_KEY", KEY)
    monkeypatch.setenv("COLLECTION_MODE", "filing_history")
    monkeypatch.setenv("HISTORY_CORP_CODE", "01205842")
    monkeypatch.setenv("HISTORY_START", "2026-11-01")
    monkeypatch.setenv("HISTORY_END", "2026-11-26")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    calls = []

    def fetch(endpoint: str, params: dict[str, str], key: str) -> bytes:
        assert key == KEY
        calls.append(endpoint)
        return EMPTY

    monkeypatch.setattr(dart_collect, "fetch_bytes", fetch)
    assert dart_collect.main() == 0 and calls == ["list.json"]
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["mode"] == "filing_history" and manifest["complete"] is True
    assert manifest["request"]["disclosure_type"] == ""
