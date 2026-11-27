"""Source reuse must not turn old or untrusted inputs into a new live observation."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from test_small_cash_e2e import fixture

from dartness.dart_smoke import CollectionError
from dartness.sample_reuse import reusable_source
from dartness.small_cash_e2e import Capture, run_sample

NOW = datetime(2026, 11, 27, 6, tzinfo=UTC)


def saved(root: Path) -> dict[str, object]:
    payload = b"original bytes"
    (root / "raw").mkdir()
    (root / "raw/source.zip").write_bytes(payload)
    record: dict[str, object] = {
        "kind": "api",
        "endpoint": "corpCode.xml",
        "parameters": {},
        "file": "raw/source.zip",
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "started_at": (NOW - timedelta(seconds=1)).isoformat(),
        "finished_at": NOW.isoformat(),
    }
    return record


def write_index(root: Path, records: list[dict[str, object]]) -> None:
    (root / "requests.json").write_text(json.dumps({"requests": records}))


@pytest.mark.parametrize(
    "change",
    [
        "none",
        "different_day",
        "future",
        "naive",
        "reused_old_day",
        "hash",
        "path",
        "partial",
        "size",
        "conflict",
    ],
)
def test_only_verified_same_day_registry_is_reused(tmp_path: Path, change: str) -> None:
    record = saved(tmp_path)
    if change == "different_day":
        record["finished_at"] = (NOW - timedelta(days=1)).isoformat()
    elif change == "future":
        record["finished_at"] = (NOW + timedelta(seconds=1)).isoformat()
    elif change == "naive":
        record["finished_at"] = "2026-11-27T06:00:00"
    elif change == "reused_old_day":
        record["source_observed_at"] = (NOW - timedelta(days=1)).isoformat()
    elif change == "hash":
        record["sha256"] = "0" * 64
    elif change == "path":
        outside = tmp_path.parent / (tmp_path.name + "-outside")
        outside.write_bytes(b"original bytes")
        record["file"] = "../" + outside.name
    elif change == "partial":
        del record["sha256"]
    elif change == "size":
        record["bytes"] = 32 * 1024 * 1024 + 1
    records = [record]
    if change == "conflict":
        (tmp_path / "raw/other.zip").write_bytes(b"other")
        records.append(
            {
                **record,
                "file": "raw/other.zip",
                "bytes": 5,
                "sha256": hashlib.sha256(b"other").hexdigest(),
            }
        )
    write_index(tmp_path, records)
    found = reusable_source(tmp_path, "corpCode.xml", {}, NOW)
    if change == "none":
        assert found is not None and found[0] == b"original bytes"
        assert found[1]["source_observed_at"] == NOW.isoformat()
    else:
        assert found is None


def test_relationship_data_and_different_receipts_are_never_reused(tmp_path: Path) -> None:
    record = saved(tmp_path)
    record.update(endpoint="document.xml", parameters={"rcept_no": "20261116000630"})
    write_index(tmp_path, [record])
    assert reusable_source(tmp_path, "document.xml", {"rcept_no": "20261116000630"}, NOW)
    assert reusable_source(tmp_path, "document.xml", {"rcept_no": "20261116001470"}, NOW) is None
    for endpoint in ("company.json", "list.json"):
        assert reusable_source(tmp_path, endpoint, {}, NOW) is None


def test_checkpoint_can_resume_without_a_final_report_and_refreshes_relationships(
    tmp_path: Path,
) -> None:
    today, payloads = fixture()
    first = tmp_path / "first"
    result, _ = run_sample(
        lambda e, p: payloads[e],
        lambda u: payloads["body"],
        ("267270",),
        today.replace(day=1),
        today,
        output=first,
    )
    assert result["api_requests"] == 4 and not (first / "report.json").exists()
    calls = []

    def fresh(endpoint: str, params: dict[str, str]) -> bytes:
        calls.append(endpoint)
        return payloads[endpoint]

    second = tmp_path / "second"
    resumed, _ = run_sample(
        fresh,
        lambda u: payloads["body"],
        ("267270",),
        today.replace(day=1),
        today,
        reuse=first,
        output=second,
    )
    assert calls == ["company.json", "list.json"]
    assert resumed["api_requests"] == 2 and resumed["reused_api_responses"] == 2
    assert resumed["web_requests"] == 1 and resumed["counts"] == {"document_non_match": 1}
    assert reusable_source(second, "corpCode.xml", {}, datetime.now(UTC)) is not None
    # Today's profile can remove a company even when the registry is reused.
    payloads["company.json"] = b'{"status":"000","corp_code":"invalid"}'
    removed, _ = run_sample(
        fresh, lambda u: payloads["body"], ("267270",), today.replace(day=1), today, reuse=first
    )
    assert removed["counts"] == {"needs_review": 1} and removed["api_requests"] == 1


def test_partial_and_rejected_payloads_are_not_published_as_reusable(tmp_path: Path) -> None:
    def failed(endpoint: str, params: dict[str, str]) -> bytes:
        raise CollectionError("network_error")

    capture = Capture(failed, lambda u: b"", output=tmp_path)
    with pytest.raises(CollectionError, match="network_error"):
        capture.api("corpCode.xml", {})
    record = json.loads((tmp_path / "requests.json").read_text())["requests"][0]
    assert record["failure"] == "network_error" and "sha256" not in record
    assert reusable_source(tmp_path, "corpCode.xml", {}, datetime.now(UTC)) is None

    def reject(name: str, payload: bytes) -> None:
        raise CollectionError("credential_in_output")

    capture = Capture(lambda e, p: b"not safe", lambda u: b"", output=tmp_path, validator=reject)
    with pytest.raises(CollectionError, match="credential_in_output"):
        capture.api("corpCode.xml", {})
    assert not (tmp_path / "raw").exists()


def test_terminated_process_keeps_only_completed_source_for_resume(tmp_path: Path) -> None:
    import os
    import subprocess
    import sys

    program = """
import signal, sys
from pathlib import Path
from dartness.small_cash_e2e import Capture
capture = Capture(lambda e,p: b"completed source", lambda u:b"", output=Path(sys.argv[1]))
capture.api("corpCode.xml", {})
def interrupted(endpoint, params):
    signal.pause()
    return b"never completed"
capture.fetch = interrupted
capture.api("document.xml", {"rcept_no":"20261116000630"})
"""
    process = subprocess.Popen(
        [sys.executable, "-c", program, str(tmp_path)],
        env={**os.environ, "PYTHONPATH": str(Path("src").resolve())},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            process.communicate(timeout=3)
    finally:
        process.terminate()
        process.communicate(timeout=5)
    assert process.returncode != 0
    records = json.loads((tmp_path / "requests.json").read_text())["requests"]
    assert len(records) == 2 and records[0]["sha256"] and "sha256" not in records[1]
    assert reusable_source(tmp_path, "corpCode.xml", {}, datetime.now(UTC)) is not None
    assert (
        reusable_source(tmp_path, "document.xml", {"rcept_no": "20261116000630"}, datetime.now(UTC))
        is None
    )
