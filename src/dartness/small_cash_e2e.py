"""Manual two-company live evaluation; not a universe collector or production query template."""

import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from dartness.cash_contract import CashValue
from dartness.cash_report_candidates import StoredCashReport
from dartness.cash_report_result import CashReportResult
from dartness.cash_viewer import fetch_dart_viewer, verify_cash_viewer
from dartness.cash_workbook import write_cash_matches_workbook
from dartness.collection_bundle import load_history
from dartness.dart_collect import corp_codes
from dartness.dart_history import collect_history, parse_history_request
from dartness.dart_receipts import collect_receipts, ensure_no_credential
from dartness.dart_smoke import CollectionError, Fetch, _api_status, fetch_bytes
from dartness.latest_cash import BodyObservation, query_latest_cash
from dartness.query_contract import SEOUL, QueryRun, SnapshotRequest
from dartness.sample_reuse import reusable_source


@dataclass
class Capture:
    fetch: Fetch
    web: Callable[[str], bytes]
    files: dict[str, bytes] = field(default_factory=dict)
    requests: list[dict[str, object]] = field(default_factory=list)
    api_count: int = 0
    web_count: int = 0
    reused_count: int = 0
    reuse: Path | None = None
    output: Path | None = None
    validator: Callable[[str, bytes], None] | None = None

    def checkpoint(self) -> None:
        if self.output is not None:
            path = self.output / "requests.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(".part")
            temp.write_text(json.dumps({"requests": self.requests}, ensure_ascii=False))
            temp.replace(path)

    def api(self, endpoint: str, params: dict[str, str]) -> bytes:
        cached = reusable_source(self.reuse, endpoint, params, datetime.now(UTC))
        if cached is None:
            if self.api_count >= 20:
                raise CollectionError("sample_api_budget_exhausted")
            self.api_count += 1
        else:
            self.reused_count += 1
        suffix = ".zip" if endpoint in ("corpCode.xml", "document.xml") else ""
        path = f"raw/api-{len(self.requests) + 1:02}-{endpoint}{suffix}"
        record: dict[str, object] = {
            "kind": "api",
            "endpoint": endpoint,
            "parameters": params,
            "file": path,
        }
        record["transport"] = "network" if cached is None else "reused"
        if cached is not None:
            payload, origin = cached
            record.update(origin)
            return self._read(record, lambda: payload)
        return self._read(record, lambda: self.fetch(endpoint, params))

    def page(self, url: str) -> bytes:
        if self.web_count >= 6:
            raise ValueError("sample_web_budget_exhausted")
        self.web_count += 1
        record: dict[str, object] = {
            "kind": "web",
            "url": url,
            "file": f"raw/web-{self.web_count:02}.html",
        }
        return self._read(record, lambda: self.web(url))

    def _read(self, record: dict[str, object], read: Callable[[], bytes]) -> bytes:
        self.requests.append(record)
        record["started_at"] = datetime.now(UTC).isoformat()
        self.checkpoint()
        try:
            payload = read()
            if self.validator is not None:
                self.validator(str(record["file"]), payload)
        except (ValueError, CollectionError) as error:
            record["failure"] = str(error)
            raise
        finally:
            record["finished_at"] = datetime.now(UTC).isoformat()
            self.checkpoint()
        filename = str(record["file"])
        self.files[filename] = payload
        record.update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
        if self.output is not None:
            path = self.output / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(path.suffix + ".part")
            temp.write_bytes(payload)
            temp.replace(path)
        self.checkpoint()
        return payload


def run_sample(
    fetch: Fetch,
    web: Callable[[str], bytes],
    stocks: tuple[str, ...],
    start: date,
    end: date,
    *,
    reuse: Path | None = None,
    output: Path | None = None,
    validator: Callable[[str, bytes], None] | None = None,
) -> tuple[dict[str, object], dict[str, bytes]]:
    if (
        not 1 <= len(stocks) <= 2
        or len(set(stocks)) != len(stocks)
        or any(not re.fullmatch(r"[0-9]{6}", stock) for stock in stocks)
    ):
        raise ValueError("one_or_two_explicit_stocks_required")
    started = datetime.now(UTC)
    if end != started.astimezone(SEOUL).date() or start > end:
        raise ValueError("explicit_history_through_execution_day_required")
    cap = Capture(fetch, web, reuse=reuse, output=output, validator=validator)
    entries: list[dict[str, object]] = []
    ready: list[
        tuple[str, str, Path, tuple[StoredCashReport, ...], tuple[BodyObservation, ...]]
    ] = []
    minimum = Decimal("50000000000")
    with tempfile.TemporaryDirectory(prefix="dartness-sample-") as temp:
        root = Path(temp)
        try:
            known = corp_codes(cap.api, list(stocks))
        except CollectionError as error:
            known = {}
            registry_failure = str(error)
        else:
            registry_failure = "company_not_found_in_registry"
        for stock in stocks:
            entry: dict[str, object] = {"stock_code": stock, "status": "needs_review"}
            entries.append(entry)
            try:
                if stock not in known:
                    raise CollectionError(registry_failure)
                code, _ = known[stock]
                entry["corp_code"] = code
                profile = json.loads(cap.api("company.json", {"corp_code": code}))
                if not isinstance(profile, dict):
                    raise CollectionError("invalid_company_profile")
                _api_status(profile.get("status"))
                name = profile.get("corp_name")
                if (
                    profile.get("corp_code") != code
                    or profile.get("stock_code") != stock
                    or profile.get("corp_cls") not in ("Y", "K", "N")
                    or not isinstance(name, str)
                    or not name.strip()
                ):
                    raise CollectionError("sample_listed_profile_mismatch")
                entry.update(corp_name=name, market=profile["corp_cls"])
                request = parse_history_request(code, start.isoformat(), end.isoformat())
                manifest, files = collect_history(cap.api, request)
                folder = root / stock
                files["manifest.json"] = json.dumps(manifest, ensure_ascii=False).encode()
                for filename, payload in files.items():
                    path = folder / filename
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(payload)
                    cap.files[f"{stock}/history/{filename}"] = payload
                history, listed = load_history(folder, datetime.now(UTC))
                periodic = tuple(
                    r
                    for r in listed
                    if any(
                        word in r.report_name for word in ("사업보고서", "반기보고서", "분기보고서")
                    )
                )
                if not 1 <= len(periodic) <= 2:
                    raise CollectionError("sample_periodic_count_outside_one_or_two")
                receipts = [r.receipt for r in periodic]
                original, archives = collect_receipts(cap.api, receipts)
                cap.files[f"{stock}/sources/manifest.json"] = json.dumps(original).encode()
                for filename, payload in archives.items():
                    cap.files[f"{stock}/sources/{filename}"] = payload
                reports = tuple(
                    StoredCashReport(r, archives[f"{r.receipt}/document.zip"]) for r in periodic
                )
                bodies = tuple(
                    BodyObservation(
                        r.receipt,
                        cap.page(f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r.receipt}"),
                        datetime.now(UTC),
                    )
                    for r in periodic
                )
                ready.append((stock, name, folder, reports, bodies))
                entry["history"] = history.to_dict()
            except (ValueError, CollectionError) as error:
                entry["reason"] = str(error)
        run = QueryRun(SnapshotRequest("cash", "latest", 12), datetime.now(UTC))
        rows: list[tuple[str, CashReportResult]] = []
        for stock, name, folder, reports, bodies in ready:
            entry = next(e for e in entries if e["stock_code"] == stock)
            try:
                history, _ = load_history(folder, run.executed_at)
                result = query_latest_cash(
                    run, str(entry["corp_code"]), "separate", minimum, history, reports, bodies
                )
                report = result.report
                if report is not None and isinstance(report.value, CashValue):
                    main = next(b.payload for b in bodies if b.receipt == report.disclosure.receipt)
                    try:
                        link = verify_cash_viewer(report.value, main, cap.page, datetime.now(UTC))
                        report = replace(report, viewer_link=link)
                    except ValueError as error:
                        report = replace(report, viewer_link_failure=str(error))
                    result = replace(result, report=report)
                    if report.status == "document_match":
                        rows.append((name, report))
                entry.update(
                    status=result.status, reason=result.reason, query_result=result.to_dict()
                )
            except (ValueError, CollectionError) as error:
                entry["reason"] = str(error)
        counts = dict(Counter(str(e["status"]) for e in entries))
        output = root / "matches.xlsx"
        write_cash_matches_workbook(
            tuple(rows),
            output,
            run=run,
            minimum_krw=minimum,
            summary=f"지정 표본 {len(stocks)}개 · 개발용 E2E · 전수 아님",
        )
        cap.files["matches.xlsx"] = output.read_bytes()
    audit: dict[str, object] = {
        "scope": "explicit_live_sample_not_market_universe",
        "stocks": stocks,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "history_start": start.isoformat(),
        "history_end": end.isoformat(),
        "query_executed_at": run.executed_at.isoformat(),
        "max_age_months": 12,
        "basis": "separate",
        "minimum_krw": str(minimum),
        "api_requests": cap.api_count,
        "reused_api_responses": cap.reused_count,
        "web_requests": cap.web_count,
        "api_limit": 20,
        "web_limit": 6,
        "requests": cap.requests,
        "companies": entries,
        "counts": counts,
        "all_values_verified": all(
            e["status"] in ("document_match", "document_non_match") for e in entries
        ),
    }
    return audit, cap.files


def main() -> int:
    key = os.environ.get("DART_API_KEY", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9]{40}", key):
        print("Sample failed: missing_or_invalid_key")
        return 1
    target = Path(os.environ.get("OUTPUT_DIR", "work/small-cash-e2e"))
    if target.exists():
        print("Sample failed: unused_output_directory_required")
        return 1
    try:
        audit, files = run_sample(
            lambda e, p: fetch_bytes(e, p, key),
            fetch_dart_viewer,
            tuple(s.strip() for s in os.environ.get("STOCK_CODES", "").split(",")),
            date.fromisoformat(os.environ.get("HISTORY_START", "")),
            date.fromisoformat(os.environ.get("HISTORY_END", "")),
            reuse=Path(os.environ["REUSE_DIR"]) if os.environ.get("REUSE_DIR") else None,
            output=target,
            validator=lambda name, data: ensure_no_credential("", {name: data}, key),
        )
        rendered = json.dumps(audit, ensure_ascii=False, indent=2)
        ensure_no_credential(rendered, files, key)
        for filename, payload in {**files, "report.json": rendered.encode()}.items():
            path = target / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
    except (ValueError, CollectionError):
        print("Sample failed: invalid_input_or_collection")
        return 1
    print(f"Sample saved: {audit['counts']}; not a market-wide evaluation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
