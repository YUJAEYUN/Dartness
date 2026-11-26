"""Fixed-response tests for the manual sample; these are not live DART evaluations."""

import io
import json
import zipfile
from dataclasses import replace
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from test_latest_cash import CORP, body, synthetic

from dartness.dart_smoke import CollectionError
from dartness.small_cash_e2e import Capture, run_sample


def fixture() -> tuple[date, dict[str, bytes]]:
    today = datetime.now(UTC).astimezone(ZoneInfo("Asia/Seoul")).date()
    source = synthetic(False)
    receipt = source.disclosure.receipt
    with zipfile.ZipFile(io.BytesIO(source.archive)) as archive:
        text = archive.read(receipt + ".xml").decode()
    text = text.replace("2024", "PRIOR").replace("2025", str(today.year - 1))
    text = text.replace("PRIOR", str(today.year - 2))
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr(receipt + ".xml", text)
    filed = today.replace(day=1)
    source = replace(source, disclosure=replace(source.disclosure, filed_on=filed))
    registry = io.BytesIO()
    with zipfile.ZipFile(registry, "w") as archive:
        archive.writestr(
            "CORPCODE.xml",
            f"<result><list><corp_code>{CORP}</corp_code>"
            "<stock_code>267270</stock_code><corp_name>시험법인</corp_name></list></result>",
        )
    row = {
        "rcept_no": receipt,
        "corp_code": CORP,
        "corp_name": "시험법인",
        "corp_cls": "Y",
        "stock_code": "267270",
        "report_nm": f"사업보고서 ({today.year - 1}.12)",
        "rcept_dt": filed.strftime("%Y%m%d"),
        "flr_nm": "시험법인",
        "rm": "",
    }
    return today, {
        "corpCode.xml": registry.getvalue(),
        "company.json": json.dumps(
            {
                "status": "000",
                "corp_code": CORP,
                "stock_code": "267270",
                "corp_name": "시험법인",
                "corp_cls": "Y",
            }
        ).encode(),
        "list.json": json.dumps(
            {
                "status": "000",
                "page_no": 1,
                "page_count": 100,
                "total_count": 1,
                "total_page": 1,
                "list": [row],
            }
        ).encode(),
        "document.xml": raw.getvalue(),
        "body": body(source).payload,
    }


def test_fixed_sample_collects_and_preserves_a_known_nonmatch() -> None:
    today, payloads = fixture()
    result, files = run_sample(
        lambda e, p: payloads[e],
        lambda u: payloads["body"],
        ("267270",),
        today.replace(day=1),
        today,
    )
    assert result["api_requests"] == 4
    assert result["web_requests"] == 1  # no unverified table URL is fetched
    assert result["counts"] == {"document_non_match": 1}
    assert result["all_values_verified"] is True
    assert result["scope"] == "explicit_live_sample_not_market_universe"
    assert files["matches.xlsx"].startswith(b"PK")
    entries = result["companies"]
    assert isinstance(entries, list)
    query = entries[0]["query_result"]
    assert query["selected_report"]["amount_krw"] == "700"


def test_sample_preserves_registry_failure_for_every_target() -> None:
    today, _ = fixture()

    def failed(endpoint: str, params: dict[str, str]) -> bytes:
        raise CollectionError("network_error")

    result, files = run_sample(
        failed, lambda u: b"", ("267270", "005290"), today.replace(day=1), today
    )
    assert result["counts"] == {"needs_review": 2}
    assert result["all_values_verified"] is False
    assert result["api_requests"] == 1 and result["web_requests"] == 0
    assert "matches.xlsx" in files


def test_sample_rejects_too_many_targets_before_network() -> None:
    today, _ = fixture()

    def forbidden(endpoint: str, params: dict[str, str]) -> bytes:
        pytest.fail("invalid input must not make requests")

    with pytest.raises(ValueError, match="one_or_two_explicit_stocks_required"):
        run_sample(forbidden, lambda u: b"", ("267270", "005290", "005930"), today, today)


def test_sample_budgets_count_failed_attempts_and_stop_before_next_call() -> None:
    api_calls, web_calls = [], []

    def api(endpoint: str, params: dict[str, str]) -> bytes:
        api_calls.append(endpoint)
        raise CollectionError("network_error")

    def web(url: str) -> bytes:
        web_calls.append(url)
        raise ValueError("viewer_transport_error")

    capture = Capture(api, web)
    for _ in range(20):
        with pytest.raises(CollectionError, match="network_error"):
            capture.api("list.json", {})
    with pytest.raises(CollectionError, match="sample_api_budget_exhausted"):
        capture.api("list.json", {})
    for _ in range(6):
        with pytest.raises(ValueError, match="viewer_transport_error"):
            capture.page("test")
    with pytest.raises(ValueError, match="sample_web_budget_exhausted"):
        capture.page("test")
    assert len(api_calls) == 20 and len(web_calls) == 6 and len(capture.requests) == 26


@pytest.mark.parametrize("failure", ["profile", "history", "archive", "body"])
def test_sample_retains_partial_sources_without_inventing_a_value(failure: str) -> None:
    today, payloads = fixture()
    if failure == "profile":
        payloads["company.json"] = b'{"status":"000","corp_code":"99999999"}'
    elif failure == "history":
        payloads["list.json"] = b'{"status":"013"}'
    elif failure == "archive":
        payloads["document.xml"] = b"broken"

    def web(url: str) -> bytes:
        raise ValueError("viewer_transport_error")

    result, files = run_sample(
        lambda e, p: payloads[e], web, ("267270",), today.replace(day=1), today
    )
    assert result["counts"] == {"needs_review": 1}
    assert result["all_values_verified"] is False
    entries = result["companies"]
    assert isinstance(entries, list)
    expected = {
        "profile": "sample_listed_profile_mismatch",
        "history": "sample_periodic_count_outside_one_or_two",
        "archive": "invalid_xml",
        "body": "viewer_transport_error",
    }
    assert entries[0]["reason"] == expected[failure]
    assert "query_result" not in entries[0]
    assert any(k.startswith("raw/api-") for k in files)
    assert files["matches.xlsx"].startswith(b"PK")


def test_sample_writes_a_confirmed_match_in_the_existing_workbook() -> None:
    from openpyxl import load_workbook

    today, payloads = fixture()
    with zipfile.ZipFile(io.BytesIO(payloads["document.xml"])) as archive:
        name = archive.namelist()[0]
        xml = archive.read(name).replace(b">700<", b">60000000000<")
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr(name, xml)
    payloads["document.xml"] = data.getvalue()
    result, files = run_sample(
        lambda e, p: payloads[e],
        lambda u: payloads["body"],
        ("267270",),
        today.replace(day=1),
        today,
    )
    assert result["counts"] == {"document_match": 1}
    workbook = load_workbook(io.BytesIO(files["matches.xlsx"]))
    sheet = workbook.active
    assert sheet is not None and sheet.max_row == 3
    assert sheet["A3"].value == "시험법인" and sheet["B3"].value == 600
    assert sheet["A3"].hyperlink is not None
    assert sheet["B3"].alignment.horizontal == "left" and sheet["B3"].font.sz == 10
