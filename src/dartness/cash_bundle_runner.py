"""Developer replay of collected files; no API key, network, or product input defaults."""

import argparse
import json
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, cast

from dartness.cash_contract import CashBasis, CashValue
from dartness.cash_viewer import verify_cash_viewer
from dartness.cash_workbook import write_cash_report_workbook
from dartness.collection_bundle import (
    load_body,
    load_correction_pair,
    load_history,
    load_reports,
    read_web_file,
)
from dartness.dart_smoke import CollectionError
from dartness.latest_cash import query_latest_cash
from dartness.query_contract import QueryRun, SnapshotRequest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-dir", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, action="append", default=[])
    parser.add_argument("--corp-code", required=True)
    parser.add_argument("--mode", choices=("latest", "as_of"), required=True)
    parser.add_argument("--max-age-months", type=int, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat)
    parser.add_argument(
        "--basis", choices=("separate", "individual", "consolidated"), required=True
    )
    parser.add_argument("--minimum-krw", type=Decimal, required=True)
    parser.add_argument("--checked-at", type=datetime.fromisoformat, required=True)
    parser.add_argument(
        "--body", action="append", nargs=3, default=[], metavar=("RECEIPT", "HTML", "OBSERVED_AT")
    )
    parser.add_argument("--correction-input", type=Path, action="append", default=[])
    parser.add_argument("--table-section", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.suffix.lower() != ".json":
        parser.error("output must be .json")
    if args.output.exists() or args.output.with_suffix(".xlsx").exists():
        parser.error("use an unused output path; existing files are preserved")
    result = None
    try:
        run = QueryRun(
            SnapshotRequest(
                "cash", cast(Literal["latest", "as_of"], args.mode), args.max_age_months, args.as_of
            ),
            args.checked_at,
        )
        history, rows = load_history(args.history_dir, run.executed_at)
        if history.request.corp_code != args.corp_code:
            raise ValueError("history_company_mismatch")
        reports = load_reports(tuple(args.source_dir), rows)
        bodies = tuple(
            load_body(receipt, Path(filename), datetime.fromisoformat(observed))
            for receipt, filename, observed in args.body
        )
        pairs = tuple(load_correction_pair(path) for path in args.correction_input)
        result = query_latest_cash(
            run,
            args.corp_code,
            cast(CashBasis, args.basis),
            args.minimum_krw,
            history,
            reports,
            bodies,
            pairs,
        )
        if result.report is not None:
            report = result.report
            failure = "table_section_not_supplied"
            if args.table_section is not None and isinstance(report.value, CashValue):
                try:
                    section = read_web_file(args.table_section)
                    main_body = next(
                        b.payload for b in bodies if b.receipt == report.disclosure.receipt
                    )
                    link = verify_cash_viewer(
                        report.value, main_body, lambda url: section, run.executed_at
                    )
                    report = replace(report, viewer_link=link)
                    failure = ""
                except (OSError, ValueError) as error:
                    failure = str(error)
            report = replace(report, viewer_link_failure=failure or None)
            result = replace(result, report=report)
        data = result.to_dict()
    except (OSError, ValueError, CollectionError) as error:
        result = None
        data = {
            "run_scope": "collection_load_failed",
            "status": "needs_review",
            "latest_correction_verified": False,
            "selected_receipt": None,
            "reason": str(error),
        }
    data["input_locations"] = {
        "history_dir": str(args.history_dir),
        "source_dirs": [str(path) for path in args.source_dir],
        "body_files": [filename for receipt, filename, observed in args.body],
        "correction_inputs": [str(path) for path in args.correction_input],
    }
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if result is not None and result.report is not None:
            write_cash_report_workbook(result.report, args.output.with_suffix(".xlsx"))
    except (OSError, ValueError) as error:
        print(
            f"cash replay output failed: {type(error).__name__}; no successful file pair reported"
        )
        return 1
    print(f"cash replay: {data['status']}; output={args.output}")
    return 0 if result is not None and result.report is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
