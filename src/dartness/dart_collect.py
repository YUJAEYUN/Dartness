"""Collect annual reports and OpenDART cash figures for an evaluation set (issue #31).

This only gathers source material. It does not extract cash from the documents or
decide which figure is correct; expected answers are fixed from the originals later.
"""

import hashlib
import json
import os
import re
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from dartness.dart_receipts import collect_receipts, ensure_no_credential, parse_receipts
from dartness.dart_smoke import CollectionError, _api_status, _xml, fetch_bytes, read_archive

MAX_COMPANIES = 8
type Fetch = Callable[[str, dict[str, str]], bytes]


def parse_request(stock_codes: str, business_year: str) -> tuple[list[str], int]:
    codes = [code.strip() for code in stock_codes.split(",") if code.strip()]
    if not codes or len(codes) > MAX_COMPANIES or len(set(codes)) != len(codes):
        raise CollectionError("invalid_company_count")
    if not all(re.fullmatch(r"[0-9]{6}", code) for code in codes):
        raise CollectionError("invalid_stock_code")
    if not re.fullmatch(r"20[0-9]{2}", business_year.strip()):
        raise CollectionError("invalid_business_year")
    return codes, int(business_year)


def _json(payload: bytes) -> dict[str, object]:
    try:
        result: object = json.loads(payload)
    except (ValueError, UnicodeError):
        raise CollectionError("invalid_json") from None
    if not isinstance(result, dict):
        raise CollectionError("invalid_response")
    return result


def corp_codes(fetch: Fetch, wanted: list[str]) -> dict[str, tuple[str, str]]:
    found: dict[str, list[tuple[str, str]]] = {code: [] for code in wanted}
    for name, payload in read_archive(fetch("corpCode.xml", {})).items():
        if name.lower().endswith(".xml"):
            for row in _xml(payload).findall("list"):
                stock = row.findtext("stock_code", "").strip()
                if stock in found:
                    found[stock].append(
                        (row.findtext("corp_code", ""), row.findtext("corp_name", ""))
                    )
    return {
        stock: rows[0]
        for stock, rows in found.items()
        if len(rows) == 1 and re.fullmatch(r"[0-9]{8}", rows[0][0])
    }


def fiscal_month(fetch: Fetch, corp_code: str) -> str:
    """The company's fiscal year-end month from OpenDART company.json (acc_mt), e.g. "03"."""
    result = _json(fetch("company.json", {"corp_code": corp_code}))
    _api_status(result.get("status"))
    month = result.get("acc_mt")
    if not isinstance(month, str) or not re.fullmatch(r"0[1-9]|1[0-2]", month):
        raise CollectionError("invalid_fiscal_month")
    return month


def report_name(year: int, month: str) -> str:
    """Business year means the year the fiscal year ends (docs/guides/dart-live-check.md)."""
    return f"사업보고서 ({year}.{month})"


def search_window(year: int, month: str) -> tuple[date, date]:
    """One year of filings starting the day after the fiscal year ends."""
    start = date(year + int(month) // 12, int(month) % 12 + 1, 1)
    return start, date(start.year + 1, start.month, 1) - timedelta(days=1)


def annual_report(
    fetch: Fetch, corp_code: str, stock: str, year: int, month: str
) -> tuple[str, list[str]]:
    """Return the original annual report receipt and the names of its corrections."""
    start, end = search_window(year, month)
    result = _json(
        fetch(
            "list.json",
            {
                "corp_code": corp_code,
                "bgn_de": start.strftime("%Y%m%d"),
                "end_de": end.strftime("%Y%m%d"),
                "pblntf_detail_ty": "A001",
                "last_reprt_at": "N",
                "page_count": "100",
            },
        )
    )
    _api_status(result.get("status"))
    rows = result.get("list")
    if result.get("total_page") != 1 or not isinstance(rows, list):
        raise CollectionError("unexpected_pagination")
    name = report_name(year, month)
    mine = [r for r in rows if isinstance(r, dict) and r.get("stock_code") == stock]
    originals = [r for r in mine if r.get("report_nm") == name]
    names = [r.get("report_nm") for r in mine]
    corrections = [n for n in names if isinstance(n, str) and n != name and name in n]
    if len(originals) != 1:
        raise CollectionError("no_filing" if not originals else "ambiguous_filing")
    receipt = originals[0].get("rcept_no")
    if not isinstance(receipt, str) or not re.fullmatch(r"[0-9]{14}", receipt):
        raise CollectionError("invalid_receipt")
    return receipt, corrections


def api_cash(
    fetch: Fetch, corp_code: str, year: int, fs_div: str, receipt: str
) -> tuple[bytes, dict[str, object]]:
    """OpenDART structured figures, kept only as a cross-check for source-verified answers."""
    payload = fetch(
        "fnlttSinglAcntAll.json",
        {"corp_code": corp_code, "bsns_year": str(year), "reprt_code": "11011", "fs_div": fs_div},
    )
    result = _json(payload)
    if result.get("status") == "013":
        return payload, {"fs_div": fs_div, "status": "no_data"}
    _api_status(result.get("status"))
    rows = result.get("list")
    if not isinstance(rows, list):
        raise CollectionError("invalid_response")
    cash = [
        {
            key: row.get(key)
            for key in ("rcept_no", "account_id", "thstrm_nm", "thstrm_amount", "currency")
        }
        for row in rows
        if isinstance(row, dict)
        and row.get("sj_div") == "BS"
        and "".join(str(row.get("account_nm", "")).split()) == "현금및현금성자산"
    ]
    # Whether the API answered for the same filing; unverified for non-December fiscal years.
    receipts = {row.get("rcept_no") for row in rows if isinstance(row, dict)}
    return payload, {
        "fs_div": fs_div,
        "status": "found" if cash else "no_cash_row",
        "matches_report": receipts == {receipt},
        "cash": cash,
    }


def collect(
    fetch: Fetch, codes: list[str], year: int
) -> tuple[dict[str, object], dict[str, bytes]]:
    files: dict[str, bytes] = {}
    companies: list[dict[str, object]] = []
    known = corp_codes(fetch, codes)
    requests = 1
    for stock in codes:
        entry: dict[str, object] = {"stock_code": stock}
        companies.append(entry)
        if stock not in known:
            entry["status"] = "company_not_found"
            continue
        corp_code, corp_name = known[stock]
        entry.update(corp_code=corp_code, corp_name=corp_name)
        try:
            requests += 1
            month = fiscal_month(fetch, corp_code)
            entry.update(fiscal_month=month, report_name=report_name(year, month))
            requests += 1
            receipt, corrections = annual_report(fetch, corp_code, stock, year, month)
            entry.update(rcept_no=receipt, corrections=corrections)
            entry["dart_url"] = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}"
            requests += 1
            original = fetch("document.xml", {"rcept_no": receipt})
            documents = read_archive(original)
            files[f"{stock}/document.zip"] = original
            entry["zip_sha256"] = hashlib.sha256(original).hexdigest()
            entry["documents"] = [
                {"name": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                for name, data in sorted(documents.items())
            ]
            summaries: list[dict[str, object]] = []
            entry["api_cash"] = summaries
            for fs_div in ("OFS", "CFS"):
                requests += 1
                raw, summary = api_cash(fetch, corp_code, year, fs_div, receipt)
                files[f"{stock}/fnltt-{fs_div}.json"] = raw
                summaries.append(summary)
            entry["status"] = "collected"
        except CollectionError as error:
            entry["status"] = str(error)
    manifest: dict[str, object] = {
        "purpose": "evaluation source collection for issue #31; no extraction performed",
        "collected_at": datetime.now(UTC).isoformat(),
        "business_year": year,
        "business_year_rule": "fiscal year ending in business_year; report_name per company",
        "request_count": requests,
        "companies": companies,
    }
    return manifest, files


def main() -> int:
    key = os.environ.get("DART_API_KEY", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9]{40}", key):
        print("DART collection failed: missing_or_invalid_key")
        return 1
    try:
        mode = os.environ.get("COLLECTION_MODE", "annual").strip() or "annual"
        if mode == "exact_receipts":
            receipts = parse_receipts(os.environ.get("RECEIPT_NUMBERS", ""))
            manifest, files = collect_receipts(lambda e, p: fetch_bytes(e, p, key), receipts)
        elif mode == "annual":
            if os.environ.get("RECEIPT_NUMBERS", "").strip():
                raise CollectionError("exact_receipt_mode_required")
            codes, year = parse_request(
                os.environ.get("STOCK_CODES", ""), os.environ.get("BUSINESS_YEAR", "")
            )
            manifest, files = collect(lambda e, p: fetch_bytes(e, p, key), codes, year)
        else:
            raise CollectionError("invalid_collection_mode")
        rendered = json.dumps(manifest, ensure_ascii=False, indent=2)
        ensure_no_credential(rendered, files, key)
        target = Path(os.environ.get("OUTPUT_DIR", "work/collect"))
        for name, data in files.items():
            (target / name).parent.mkdir(parents=True, exist_ok=True)
            (target / name).write_bytes(data)
        target.mkdir(parents=True, exist_ok=True)
        (target / "manifest.json").write_text(rendered + "\n")
    except CollectionError as error:
        print(f"DART collection failed: {error}")
        return 1
    entries = manifest["reports" if mode == "exact_receipts" else "companies"]
    assert isinstance(entries, list)
    print(f"DART collection finished: {', '.join(str(entry.get('status')) for entry in entries)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
