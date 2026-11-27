"""Bounded manual profile timing experiments; never builds a universe."""

import hashlib
import json
import os
import re
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from dartness.dart_smoke import CollectionError, Fetch, _api_status, fetch_bytes

_SAMPLES = (("00118804", "005290"), ("01205842", "267270"))
# Public registry evidence and selection limitations: docs/design/universe-speed-options.md.
_EXPANDED_SAMPLES = _SAMPLES + (
    ("00126380", "005930"),
    ("00164779", "000660"),
    ("00164742", "005380"),
    ("00106641", "000270"),
    ("00155319", "005490"),
    ("00120021", "003550"),
    ("00181712", "034730"),
    ("00160588", "000880"),
    ("00266961", "035420"),
    ("00258801", "035720"),
    ("00356361", "051910"),
    ("00401731", "066570"),
    ("00164788", "012330"),
    ("00149655", "028260"),
    ("00159193", "015760"),
    ("00126256", "032830"),
    ("00138279", "010950"),
    ("00547583", "086790"),
)


def _validate(payload: bytes, corp_code: str, stock_code: str) -> None:
    try:
        data = json.loads(payload)
    except (ValueError, UnicodeDecodeError):
        raise CollectionError("invalid_json") from None
    if not isinstance(data, dict):
        raise CollectionError("invalid_response")
    _api_status(data.get("status"))
    if data.get("corp_code") != corp_code or data.get("stock_code") != stock_code:
        raise CollectionError("profile_identity_mismatch")
    if data.get("corp_cls") not in ("Y", "K", "N"):
        raise CollectionError("not_listed")


def run_probe(
    fetch: Fetch,
    *,
    checkpoint: Callable[[dict[str, object]], None],
    expanded: bool = False,
) -> dict[str, object]:
    """Compare two rounds with the same global 0.5-second launch spacing."""
    samples = _EXPANDED_SAMPLES if expanded else _SAMPLES
    lock = threading.Lock()
    gate = threading.Lock()
    stopped = threading.Event()
    attempts: list[dict[str, object]] = []
    phases: list[dict[str, object]] = []
    next_start = 0.0
    active = 0
    peak = 0
    started_at = datetime.now(UTC).isoformat()
    start = time.monotonic()

    def report(status: str) -> dict[str, object]:
        # Called under lock while workers may still be active. Copy mutable records.
        return {
            "status": status,
            "started_at": started_at,
            "elapsed_seconds": time.monotonic() - start,
            "api_requests": len(attempts),
            "sample_size": len(samples),
            "max_api_requests": 4 * len(samples),
            "max_in_flight": peak,
            "minimum_start_interval_seconds": 0.5,
            "attempts": [dict(item) for item in attempts],
            "phases": [dict(item) for item in phases],
        }

    def request(corp_code: str, stock_code: str, phase: str) -> None:
        nonlocal next_start, active, peak
        with gate:
            delay = max(0.0, next_start - time.monotonic())
            if stopped.wait(delay):
                return
            with lock:
                if stopped.is_set():
                    return
                request_start = time.monotonic()
                next_start = request_start + 0.5
                record: dict[str, object] = {
                    "phase": phase,
                    "corp_code": corp_code,
                    "stock_code": stock_code,
                    "start_offset_seconds": request_start - start,
                    "status": "started",
                }
                attempts.append(record)
                active += 1
                peak = max(peak, active)
                checkpoint(report("running"))
        try:
            payload = fetch("company.json", {"corp_code": corp_code})
            _validate(payload, corp_code, stock_code)
            with lock:
                record.update(
                    status="validated",
                    bytes=len(payload),
                    sha256=hashlib.sha256(payload).hexdigest(),
                )
        except CollectionError as error:
            with lock:
                record.update(status="failed", failure=str(error))
                stopped.set()
        finally:
            with lock:
                record["elapsed_seconds"] = time.monotonic() - request_start
                active -= 1
                checkpoint(report("running"))

    for round_number in (1, 2):
        order = (2, 1) if expanded and round_number == 2 else (1, 2)
        for workers in order:
            if stopped.is_set():
                break
            name = f"round-{round_number}-workers-{workers}"
            phase_start = time.monotonic()
            if workers == 1:
                for corp, stock in samples:
                    if stopped.is_set():
                        break
                    request(corp, stock, name)
            else:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [
                        executor.submit(request, corp, stock, name) for corp, stock in samples
                    ]
                    for future in futures:
                        future.result()
            phases.append({"name": name, "elapsed_seconds": time.monotonic() - phase_start})
    with lock:
        result = report("failed" if stopped.is_set() else "completed_probe")
        checkpoint(result)
        return result


def main() -> int:
    key = os.environ.get("DART_API_KEY", "")
    output = os.environ.get("OUTPUT_DIR", "")
    expanded = os.environ.get("PROFILE_PROBE_EXPANDED", "")
    if expanded not in ("", "true"):
        print("Profile probe failed: invalid_sample_mode")
        return 1
    if not re.fullmatch(r"[A-Za-z0-9]{40}", key) or not output:
        print("Profile probe failed: invalid_input")
        return 1
    target = Path(output)
    if target.exists():
        print("Profile probe failed: output_exists")
        return 1
    target.mkdir(parents=True)

    def save(report: dict[str, object]) -> None:
        payload = json.dumps(report, ensure_ascii=False, indent=2).encode()
        if key.encode() in payload:
            raise CollectionError("credential_in_output")
        temp = target / "report.json.part"
        temp.write_bytes(payload)
        temp.replace(target / "report.json")

    result = run_probe(
        lambda endpoint, params: fetch_bytes(endpoint, params, key),
        checkpoint=save,
        expanded=expanded == "true",
    )
    print(f"Profile probe: {result['status']}; API attempts: {result['api_requests']}")
    return 0 if result["status"] == "completed_probe" else 1


if __name__ == "__main__":
    sys.exit(main())
