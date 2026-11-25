"""Manual, bounded live checks; never run from ordinary PR tests.

See docs/guides/listed-live-check.md. Probe results are not full listing results.
"""

import hashlib
import json
import os
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dartness.dart_smoke import CollectionError, Fetch, fetch_bytes
from dartness.disclosure_list import ListRequest, _page, _row
from dartness.listed_universe import (
    Clock,
    ListedFilings,
    _execution_day,
    _observe,
    _profile,
    _registry,
    collect_listed_filings,
)

MAX_REQUESTS = 5000
MAX_SECONDS = 3000
type Progress = Callable[[dict[str, object]], None]


def _shape(endpoint: str, body: bytes) -> dict[str, object]:
    result: dict[str, object] = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    if endpoint == "corpCode.xml":
        return result
    try:
        decoded: object = json.loads(body)
    except (ValueError, UnicodeError):
        result["format"] = "invalid_json"
        return result
    if not isinstance(decoded, dict):
        result["format"] = "not_object"
        return result
    status = decoded.get("status")
    result["status"] = (
        status if isinstance(status, str) and re.fullmatch(r"[0-9]{3}", status) else "invalid"
    )
    fields = (
        "corp_name",
        "corp_cls",
        "stock_code",
        "page_no",
        "page_count",
        "total_count",
        "total_page",
        "list",
    )
    result["field_types"] = {field: type(decoded.get(field)).__name__ for field in fields}
    return result


def _result(result: ListedFilings) -> dict[str, object]:
    universe = result.universe
    hashes = dict(universe.profile_sha256)
    return {
        "company_count": len(universe.companies),
        "profile_count": len(hashes),
        "market_counts": {
            market: sum(c.market == market for c in universe.companies) for market in "YKN"
        },
        "excluded_other_corps": universe.excluded_other_corps,
        "registry_sha256": universe.registry_sha256,
        "profile_sha256": universe.profile_sha256,
        "observed_from": universe.observed_from.isoformat(),
        "observed_until": universe.observed_until.isoformat(),
        "finished_at": result.finished_at.isoformat(),
        "matched_filing_count": len(result.items),
        "outside_filings_count": result.outside_filings_count,
        "no_filings": result.no_filings,
        "companies": [
            {
                "corp_code": c.corp_code,
                "name": c.name,
                "market": c.market,
                "stock_code": c.stock_code,
                "profile_sha256": hashes[c.corp_code],
            }
            for c in universe.companies
        ],
        "filings": [
            {
                "receipt": f.receipt,
                "corp_code": f.corp_code,
                "report_name": f.report_name,
                "filed_on": f.filed_on.isoformat(),
                "source_url": f.source_url,
            }
            for f in result.items
        ],
    }


def run_check(
    mode: str,
    max_requests: int,
    executed_at: datetime,
    *,
    fetch: Fetch,
    clock: Clock,
    progress: Progress | None = None,
    save_registry: Callable[[bytes], None] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, object]:
    if mode not in {"probe", "full"} or type(max_requests) is not int:
        raise ValueError("invalid_live_check_input")
    if not 1 <= max_requests <= (20 if mode == "probe" else MAX_REQUESTS):
        raise ValueError("invalid_live_check_budget")
    day = _execution_day(executed_at)
    previous_day = day - timedelta(days=1)
    search = ListRequest(previous_day, previous_day)
    report: dict[str, object] = {
        "mode": mode,
        "status": "running",
        "executed_at": executed_at.isoformat(),
        "execution_date": day.isoformat(),
        "search_date": previous_day.isoformat(),
        "max_requests": max_requests,
        "requests_attempted": 0,
        "responses_received": 0,
        "financial_or_correction_verification": False,
        "independent_exchange_roster_verification": False,
    }
    started = monotonic()
    attempted, responses = 0, 0
    last_observation: datetime | None = None

    def observed_fetch(endpoint: str, params: dict[str, str]) -> bytes:
        nonlocal attempted, responses, last_observation
        if monotonic() - started >= MAX_SECONDS:
            raise CollectionError("live_time_limit")
        if attempted >= max_requests:
            raise CollectionError("live_request_budget")
        last_observation = _observe(executed_at, clock, last_observation)
        attempted += 1
        report["requests_attempted"] = attempted
        report["last_request"] = {
            "endpoint": endpoint,
            **{
                key: params[key]
                for key in ("corp_code", "bgn_de", "end_de", "page_no")
                if key in params
            },
        }
        report["last_response"] = {}
        body = fetch(endpoint, params)
        responses += 1
        report["responses_received"] = responses
        report["last_response"] = _shape(endpoint, body)
        if endpoint == "corpCode.xml" and save_registry is not None:
            save_registry(body)
        if progress is not None and responses % 100 == 0:
            progress(report.copy())
        return body

    try:
        if mode == "probe":
            payload = observed_fetch("corpCode.xml", {})
            candidates = _registry(payload, day)
            samples = []
            for code in sorted(candidates)[:3]:
                body = observed_fetch("company.json", {"corp_code": code})
                market, _, stock = _profile(body, code, {s for s, _ in candidates[code]})
                samples.append(
                    {
                        "corp_code": code,
                        "market": market,
                        "stock_code": stock,
                        "sha256": hashlib.sha256(body).hexdigest(),
                    }
                )
            encoded = f"{previous_day.year:04d}{previous_day.month:02d}{previous_day.day:02d}"
            body = observed_fetch(
                "list.json",
                {
                    "bgn_de": encoded,
                    "end_de": encoded,
                    "page_no": "1",
                    "page_count": "100",
                    "sort": "date",
                    "sort_mth": "asc",
                    "last_reprt_at": "N",
                },
            )
            total, pages, rows = _page(body, 1)
            for value in rows:
                _row(value, search, previous_day, previous_day)
            report.update(
                {
                    "status": "probe_only",
                    "registry_sha256": hashlib.sha256(payload).hexdigest(),
                    "candidate_count": len(candidates),
                    "profile_samples": samples,
                    "listing_total_count": total,
                    "listing_total_pages": pages,
                    "estimated_full_requests": 1 + len(candidates) + max(1, pages),
                    "full_population_or_pagination_complete": False,
                }
            )
        else:
            result = collect_listed_filings(
                executed_at, search, max_requests=max_requests, fetch=observed_fetch, clock=clock
            )
            report.update(_result(result))
            report.update(
                {"status": "complete_listing", "full_population_or_pagination_complete": True}
            )
    except CollectionError as error:
        report.update(
            {
                "status": "failed",
                "error_code": str(error),
                "full_population_or_pagination_complete": False,
            }
        )
    if report["status"] != "failed":
        try:
            report["finished_at"] = _observe(executed_at, clock, last_observation).isoformat()
        except CollectionError as error:
            report.update(
                {
                    "status": "failed",
                    "error_code": str(error),
                    "full_population_or_pagination_complete": False,
                }
            )
    if progress is not None:
        progress(report.copy())
    return report


def main() -> int:
    output = Path("work/listed-live-check")
    key = os.environ.get("DART_API_KEY", "").strip()
    output.mkdir(parents=True, exist_ok=True)

    def write_report(report: dict[str, object]) -> None:
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if key and key in rendered:
            raise CollectionError("credential_in_output")
        temporary = output / "report.tmp"
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(output / "report.json")
        print(
            f"Live check: {report.get('status')} / requests {report.get('requests_attempted')}",
            flush=True,
        )
        summary_fields = (
            "status",
            "requests_attempted",
            "responses_received",
            "candidate_count",
            "listing_total_pages",
            "estimated_full_requests",
            "company_count",
            "matched_filing_count",
            "error_code",
        )
        print(
            "Live check summary: "
            + json.dumps({field: report[field] for field in summary_fields if field in report}),
            flush=True,
        )

    def save_registry(body: bytes) -> None:
        if key and key.encode() in body:
            raise CollectionError("credential_in_output")
        (output / "registry.zip").write_bytes(body)

    try:
        if len(key) != 40:
            raise ValueError("missing_or_invalid_key")
        budget = int(os.environ.get("LISTED_MAX_REQUESTS", "20"))
        mode = os.environ.get("LISTED_CHECK_MODE", "probe")
        executed_at = datetime.now(UTC)
        report = run_check(
            mode,
            budget,
            executed_at,
            fetch=lambda endpoint, params: fetch_bytes(endpoint, params, key),
            clock=lambda: datetime.now(UTC),
            progress=write_report,
            save_registry=save_registry,
        )
        write_report(report)
        return int(report["status"] == "failed")
    except (ValueError, CollectionError, OSError):
        # Never print credential-bearing exception messages or transport objects.
        (output / "report.json").write_text(
            '{"status":"failed","error_code":"live_configuration_or_output_error"}\n',
            encoding="utf-8",
        )
        print("Live check configuration or output failed; no successful verification.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
