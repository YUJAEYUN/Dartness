"""Explicit manual public evaluation adapter; ordinary CI never executes this main function."""

import hashlib
import json
import os
import re
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from dartness.cash_contract import CashBasis, CashScope
from dartness.cash_survey import write_cash_survey_workbook
from dartness.cash_viewer import fetch_dart_viewer
from dartness.dart_receipts import ensure_no_credential
from dartness.dart_smoke import CollectionError, fetch_bytes
from dartness.query_contract import SnapshotMode, SnapshotRequest
from dartness.universe_cash import UniverseCashPlan, collect_universe_cash


def parse_plan(raw: str, history_start: str) -> UniverseCashPlan:
    if len(raw.encode()) > 16384:
        raise ValueError("evaluation_config_too_large")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("evaluation_config_object_required")
    required = {
        "mode",
        "max_age_months",
        "scope",
        "minimum_krw",
        "max_api_requests",
        "max_web_requests",
        "max_companies",
        "max_reports_per_company",
        "basis_by_corp",
        "target_codes",
    }
    if not required <= set(data) or set(data) - required - {"as_of"}:
        raise ValueError("explicit_evaluation_fields_required")
    mode, scope = data["mode"], data["scope"]
    if mode not in ("latest", "as_of") or scope not in ("standalone", "consolidated"):
        raise ValueError("evaluation_mode_and_scope_required")
    amount = data["minimum_krw"]
    if not isinstance(amount, str):
        raise ValueError("exact_amount_string_required")
    for key in (
        "max_age_months",
        "max_api_requests",
        "max_web_requests",
        "max_companies",
        "max_reports_per_company",
    ):
        if type(data[key]) is not int:
            raise ValueError("integer_evaluation_limits_required")
    bases, targets = data["basis_by_corp"], data["target_codes"]
    if (
        not isinstance(bases, dict)
        or not isinstance(targets, list)
        or any(not isinstance(code, str) for code in targets)
        or any(
            not isinstance(code, str) or basis not in ("separate", "individual", "consolidated")
            for code, basis in bases.items()
        )
    ):
        raise ValueError("explicit_evaluation_targets_and_bases_required")
    if not targets or any(code not in bases for code in targets):
        raise ValueError("confirmed_public_pilot_targets_required")
    try:
        minimum = Decimal(amount)
    except InvalidOperation as error:
        raise ValueError("exact_amount_string_required") from error
    as_of = data.get("as_of")
    if as_of is not None and not isinstance(as_of, str):
        raise ValueError("iso_as_of_required")
    return UniverseCashPlan(
        SnapshotRequest(
            "cash",
            cast(SnapshotMode, mode),
            data["max_age_months"],
            date.fromisoformat(as_of) if as_of is not None else None,
        ),
        cast(CashScope, scope),
        minimum,
        date.fromisoformat(history_start),
        data["max_api_requests"],
        data["max_web_requests"],
        data["max_companies"],
        data["max_reports_per_company"],
        tuple((code, cast(CashBasis, basis)) for code, basis in bases.items()),
        tuple(targets),
    )


def main() -> int:
    key = os.environ.get("DART_API_KEY", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9]{40}", key):
        print("Universe cash failed: missing_or_invalid_key")
        return 1
    target = Path(os.environ.get("OUTPUT_DIR", "work/universe-cash"))
    if target.exists():
        print("Universe cash failed: unused_output_directory_required")
        return 1
    calls: list[dict[str, object]] = []

    def save(name: str, payload: bytes) -> None:
        ensure_no_credential("", {name: payload}, key)
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".part")
        temp.write_bytes(payload)
        temp.replace(path)

    def progress(status: str) -> None:
        save(
            "progress.json",
            json.dumps({"status": status, "requests": calls}, ensure_ascii=False).encode(),
        )

    def api(endpoint: str, params: dict[str, str]) -> bytes:
        record: dict[str, object] = {"endpoint": endpoint, "parameters": dict(params)}
        calls.append(record)
        try:
            payload = fetch_bytes(endpoint, params, key)
            record.update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
            # Full company profiles contain fields outside this evaluation's retained scope.
            if endpoint != "company.json":
                suffix = ".zip" if endpoint in ("corpCode.xml", "document.xml") else ""
                name = f"raw/api-{len(calls):05}-{endpoint}{suffix}"
                save(name, payload)
                record["file"] = name
            return payload
        except CollectionError as error:
            record["failure"] = str(error)
            raise
        finally:
            if endpoint != "company.json" or len(calls) % 50 == 0 or "failure" in record:
                progress("collecting")

    def web(url: str) -> bytes:
        record: dict[str, object] = {"url": url}
        calls.append(record)
        try:
            payload = fetch_dart_viewer(url)
            name = f"raw/web-{len(calls):05}.html"
            save(name, payload)
            record.update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(), file=name)
            return payload
        except ValueError as error:
            record["failure"] = str(error)
            raise
        finally:
            progress("collecting")

    try:
        plan = parse_plan(
            os.environ.get("UNIVERSE_CASH_CONFIG", ""), os.environ.get("HISTORY_START", "")
        )
        result = collect_universe_cash(plan, fetch=api, web=web)
        save("report.json", json.dumps(result.to_dict(), ensure_ascii=False, indent=2).encode())
        write_cash_survey_workbook(result.survey, target / "matches.xlsx")
        progress("completed_bounded_run")
    except (ValueError, CollectionError):
        if calls:
            progress("failed")
        print("Universe cash failed: invalid_input_or_incomplete_run; no complete result")
        return 1
    print(f"Universe cash bounded run: {result.survey.counts}; not full-market value verification")
    return 0


if __name__ == "__main__":
    sys.exit(main())
