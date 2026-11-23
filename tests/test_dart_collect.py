"""Offline checks for the evaluation collection with fake OpenDART responses."""

import io
import json
import zipfile
from pathlib import Path
from typing import Any, cast

import pytest

from dartness import dart_collect
from dartness.dart_collect import collect, parse_request
from dartness.dart_smoke import CollectionError

KEY = "A" * 40


def archive(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipped:
        for name, data in files.items():
            zipped.writestr(name, data)
    return buffer.getvalue()


CORPS = archive(
    {
        "CORPCODE.xml": (
            "<result>"
            "<list><corp_code>00000001</corp_code><corp_name>가람</corp_name>"
            "<stock_code>111111</stock_code></list>"
            "<list><corp_code>00000002</corp_code><corp_name>나래</corp_name>"
            "<stock_code>222222</stock_code></list>"
            "</result>"
        ).encode()
    }
)


def filings(stock: str, names: list[str]) -> bytes:
    rows = [
        {"stock_code": stock, "report_nm": name, "rcept_no": f"2026031000000{i}"}
        for i, name in enumerate(names, 1)
    ]
    return json.dumps({"status": "000", "total_page": 1, "list": rows}).encode()


def figures(amount: str | None) -> bytes:
    if amount is None:
        return json.dumps({"status": "013", "message": "no data"}).encode()
    rows = [
        {"sj_div": "BS", "account_nm": "현금및 현금성자산", "account_id": "ifrs-full_Cash",
         "thstrm_nm": "제 10 기", "thstrm_amount": amount, "currency": "KRW", "rcept_no": "x"},
        {"sj_div": "IS", "account_nm": "현금및현금성자산", "thstrm_amount": "999"},
    ]  # fmt: skip
    return json.dumps({"status": "000", "list": rows}).encode()


def fake(responses: dict[tuple[str, str], bytes]) -> tuple[list[str], dart_collect.Fetch]:
    calls: list[str] = []

    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        calls.append(endpoint)
        if endpoint == "corpCode.xml":
            return CORPS
        detail = params.get("corp_code") or params.get("rcept_no", "")
        return responses[(endpoint, detail + params.get("fs_div", ""))]

    return calls, fetch


def test_collects_original_report_documents_and_api_figures() -> None:
    calls, fetch = fake(
        {
            ("list.json", "00000001"): filings(
                "111111", ["사업보고서 (2025.12)", "[기재정정]사업보고서 (2025.12)", "분기보고서"]
            ),
            ("document.xml", "20260310000001"): archive({"a.xml": b"<doc/>"}),
            ("fnlttSinglAcntAll.json", "00000001OFS"): figures("1000"),
            ("fnlttSinglAcntAll.json", "00000001CFS"): figures(None),
        }
    )
    manifest, files = collect(fetch, ["111111"], 2025)
    assert calls == [
        "corpCode.xml",
        "list.json",
        "document.xml",
        "fnlttSinglAcntAll.json",
        "fnlttSinglAcntAll.json",
    ]
    assert manifest["request_count"] == 5
    [company] = cast(list[dict[str, Any]], manifest["companies"])
    assert company["status"] == "collected"
    assert company["rcept_no"] == "20260310000001"
    assert company["corrections"] == ["[기재정정]사업보고서 (2025.12)"]
    ofs, cfs = company["api_cash"]
    assert ofs["cash"] == [
        {"rcept_no": "x", "account_id": "ifrs-full_Cash", "thstrm_nm": "제 10 기",
         "thstrm_amount": "1000", "currency": "KRW"}
    ]  # fmt: skip
    assert cfs == {"fs_div": "CFS", "status": "no_data"}
    assert set(files) == {"111111/document.zip", "111111/fnltt-OFS.json", "111111/fnltt-CFS.json"}


def test_one_company_failure_does_not_stop_the_others() -> None:
    _, fetch = fake(
        {
            ("list.json", "00000001"): filings("111111", ["사업보고서 (2025.12)"] * 2),
            ("list.json", "00000002"): filings("222222", ["반기보고서 (2025.06)"]),
        }
    )
    manifest, files = collect(fetch, ["111111", "222222", "333333"], 2025)
    statuses = [c["status"] for c in cast(list[dict[str, Any]], manifest["companies"])]
    assert statuses == ["ambiguous_filing", "no_filing", "company_not_found"]
    assert files == {}


@pytest.mark.parametrize(
    "codes,year,error",
    [
        ("", "2025", "invalid_company_count"),
        ("111111,111111", "2025", "invalid_company_count"),
        (",".join(f"{i:06d}" for i in range(9)), "2025", "invalid_company_count"),
        ("11111", "2025", "invalid_stock_code"),
        ("111111", "25", "invalid_business_year"),
    ],
)
def test_rejects_invalid_requests(codes: str, year: str, error: str) -> None:
    with pytest.raises(CollectionError, match=error):
        parse_request(codes, year)


def test_main_writes_files_without_the_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, fake_fetch = fake(
        {
            ("list.json", "00000001"): filings("111111", ["사업보고서 (2025.12)"]),
            ("document.xml", "20260310000001"): archive({"a.xml": b"<doc/>"}),
            ("fnlttSinglAcntAll.json", "00000001OFS"): figures("1000"),
            ("fnlttSinglAcntAll.json", "00000001CFS"): figures("2000"),
        }
    )
    monkeypatch.setattr(dart_collect, "fetch_bytes", lambda e, p, key: fake_fetch(e, p))
    monkeypatch.setenv("DART_API_KEY", KEY)
    monkeypatch.setenv("STOCK_CODES", "111111")
    monkeypatch.setenv("BUSINESS_YEAR", "2025")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    assert dart_collect.main() == 0
    written = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()}
    assert written == {
        "manifest.json",
        "111111/document.zip",
        "111111/fnltt-OFS.json",
        "111111/fnltt-CFS.json",
    }
    assert all(KEY not in p.read_text(errors="ignore") for p in tmp_path.rglob("*") if p.is_file())


def test_main_refuses_a_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DART_API_KEY", raising=False)
    assert dart_collect.main() == 1
