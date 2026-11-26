"""Saved producer formats to existing query objects; synthetic financial answers are fixed."""

import json
from dataclasses import asdict
from pathlib import Path

import pytest
from openpyxl import load_workbook
from test_latest_cash import NOW, body, history_for, synthetic
from test_native_correction import INPUTS

from dartness import cash_bundle_runner
from dartness.cash_report_candidates import StoredCashReport
from dartness.collection_bundle import load_correction_pair, load_history, load_reports
from dartness.dart_receipts import collect_receipts


def bundle(root: Path) -> tuple[Path, Path, Path, StoredCashReport]:
    a, b = synthetic(False), synthetic(True)
    h = history_for((a.disclosure, b.disclosure))
    history = root / "history"
    history.mkdir()
    response_records = []
    for i, response in enumerate(h.responses, 1):
        filename = f"history/response-{i:02}.json"
        target = history / filename
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(response.payload)
        response_records.append(
            {
                "file": filename,
                "parameters": dict(response.parameters),
                "response_sha256": response.sha256,
            }
        )
    manifest = {
        "mode": "filing_history",
        "complete": True,
        "request": {
            "start": h.request.start.isoformat(),
            "end": h.request.end.isoformat(),
            "corp_code": h.request.corp_code,
            "corp_cls": "",
            "disclosure_type": "",
        },
        "request_count": len(response_records),
        "responses": response_records,
        "started_at": NOW.isoformat(),
        "collected_at": NOW.isoformat(),
        "items": [
            {**asdict(r.disclosure), "filed_on": r.disclosure.filed_on.isoformat()} for r in (a, b)
        ],
    }
    (history / "manifest.json").write_text(json.dumps(manifest))
    sources = root / "sources"
    sources.mkdir()
    archives = {r.disclosure.receipt: r.archive for r in (a, b)}
    source_manifest, files = collect_receipts(
        lambda endpoint, params: archives[params["rcept_no"]], list(archives)
    )
    for filename, payload in files.items():
        target = sources / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    (sources / "manifest.json").write_text(json.dumps(source_manifest))
    main = root / "viewer.html"
    main.write_bytes(body(b).payload)
    return history, sources, main, b


def invoke(
    monkeypatch: pytest.MonkeyPatch,
    h: Path,
    s: Path,
    main: Path,
    b: StoredCashReport,
    output: Path,
    minimum: str = "500",
) -> int:
    monkeypatch.setattr(
        "sys.argv",
        [
            "cash_bundle_runner",
            "--history-dir",
            str(h),
            "--source-dir",
            str(s),
            "--corp-code",
            b.disclosure.corp_code,
            "--mode",
            "as_of",
            "--as-of",
            "2025-12-31",
            "--max-age-months",
            "0",
            "--basis",
            "separate",
            "--minimum-krw",
            minimum,
            "--checked-at",
            NOW.isoformat(),
            "--body",
            b.disclosure.receipt,
            str(main),
            NOW.isoformat(),
            "--output",
            str(output),
        ],
    )
    return cash_bundle_runner.main()


def test_saved_producer_outputs_run_to_json_and_three_column_workbook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("saved replay must not call the network")

    monkeypatch.setattr("urllib.request.urlopen", forbidden)
    h, s, main, b = bundle(tmp_path)
    output = tmp_path / "out/result.json"
    assert invoke(monkeypatch, h, s, main, b, output) == 0
    result = json.loads(output.read_text())
    assert (
        result["selected_receipt"] == b.disclosure.receipt
        and result["latest_correction_verified"] is True
    )
    assert result["selected_report"]["amount_krw"] == "600"
    assert result["selected_report"]["actual_as_of"] == "2025-12-31"
    assert result["selected_report"]["table_link"]["failure"] == "table_section_not_supplied"
    sheet = load_workbook(output.with_suffix(".xlsx")).worksheets[0]
    assert sheet.max_column == 3 and sheet["A3"].value == "HD건설기계"
    assert sheet["B3"].value == 0.000006 and sheet["A3"].hyperlink.target == b.disclosure.source_url
    assert sheet["A3"].font.sz == 10 and sheet["A3"].alignment.horizontal == "left"


@pytest.mark.parametrize("kind", ["summary", "path", "hash", "missing"])
def test_history_summary_cannot_replace_raw_verified_responses(tmp_path: Path, kind: str) -> None:
    h, _, _, _ = bundle(tmp_path)
    p = h / "manifest.json"
    m = json.loads(p.read_text())
    if kind == "summary":
        m["items"] = []
    elif kind == "path":
        m["responses"][0]["file"] = "../outside.json"
    elif kind == "hash":
        m["responses"][0]["response_sha256"] = "0" * 64
    elif kind == "missing":
        (h / m["responses"][0]["file"]).unlink()
    p.write_text(json.dumps(m))
    with pytest.raises((ValueError, OSError)):
        load_history(h, NOW)


@pytest.mark.parametrize(
    "kind", ["zip_hash", "member_hash", "member_size", "main", "duplicate", "incomplete"]
)
def test_source_manifest_is_not_accepted_as_verified_archive(tmp_path: Path, kind: str) -> None:
    h, s, _, _ = bundle(tmp_path)
    _, rows = load_history(h, NOW)
    p = s / "manifest.json"
    m = json.loads(p.read_text())
    r = m["reports"][0]
    if kind == "zip_hash":
        r["archive_sha256"] = "0" * 64
    elif kind == "member_hash":
        r["documents"][0]["sha256"] = "0" * 64
    elif kind == "member_size":
        r["documents"][0]["bytes"] += 1
    elif kind == "main":
        r["main_document"] = "wrong.xml"
    elif kind == "duplicate":
        m["reports"] = [r, r]
    elif kind == "incomplete":
        m["complete"] = False
    p.write_text(json.dumps(m))
    with pytest.raises(ValueError):
        load_reports((s,), rows)


def test_loader_failure_is_recorded_without_financial_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h, s, main, b = bundle(tmp_path)
    p = s / "manifest.json"
    m = json.loads(p.read_text())
    m["reports"][0]["archive_sha256"] = "0" * 64
    p.write_text(json.dumps(m))
    output = tmp_path / "result.json"
    assert invoke(monkeypatch, h, s, main, b, output) == 1
    result = json.loads(output.read_text())
    assert result["status"] == "needs_review" and result["selected_receipt"] is None
    assert result["reason"] == "archive_hash_mismatch" and not output.with_suffix(".xlsx").exists()


def test_existing_outputs_are_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    h, s, main, b = bundle(tmp_path)
    output = tmp_path / "result.json"
    output.write_text("existing user data")
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, h, s, main, b, output)
    assert error.value.code == 2 and output.read_text() == "existing user data"


def test_correction_input_reads_literal_files_without_expected_answers(tmp_path: Path) -> None:
    for name, payload in [
        ("a.html", INPUTS.original_main),
        ("b.html", INPUTS.correction_main),
        ("e.html", INPUTS.errata_html),
    ]:
        (tmp_path / name).write_bytes(payload)
    p = tmp_path / "proof.json"
    p.write_text(
        json.dumps(
            {
                "original_receipt": "20260318001192",
                "correction_receipt": "20260602000456",
                "original_main": "a.html",
                "correction_main": "b.html",
                "errata_html": "e.html",
                "observed_at": INPUTS.observed_at.isoformat(),
                "errata_url": INPUTS.errata_url,
            }
        )
    )
    proof = load_correction_pair(p)
    assert proof.web == INPUTS and proof.original_receipt == "20260318001192"
    data = json.loads(p.read_text())
    data["original_main"] = "../outside.html"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="outside_root"):
        load_correction_pair(p)


def test_annual_and_exact_modes_can_be_combined_without_changing_expected_values(
    tmp_path: Path,
) -> None:
    h, sources, _, _ = bundle(tmp_path)
    _, rows = load_history(h, NOW)
    path = sources / "manifest.json"
    manifest = json.loads(path.read_text())
    first = manifest["reports"][0]
    row = rows[0]
    annual = tmp_path / "annual"
    target = annual / row.stock_code / "document.zip"
    target.parent.mkdir(parents=True)
    target.write_bytes((sources / row.receipt / "document.zip").read_bytes())
    annual_record = {
        "rcept_no": row.receipt,
        "corp_code": row.corp_code,
        "stock_code": row.stock_code,
        "status": "collected",
        "dart_url": row.source_url,
        "zip_sha256": first["archive_sha256"],
        "documents": first["documents"],
    }
    (annual / "manifest.json").write_text(json.dumps({"companies": [annual_record]}))
    second = manifest["reports"][1]
    manifest.update(reports=[second], requested_receipts=[second["receipt"]], request_count=1)
    path.write_text(json.dumps(manifest))
    result = load_reports((annual, sources), rows)
    assert [r.disclosure.receipt for r in result] == [row.receipt, second["receipt"]]
    annual_record["corp_code"] = "00000001"
    (annual / "manifest.json").write_text(json.dumps({"companies": [annual_record]}))
    with pytest.raises(ValueError, match="annual_collection_company_mismatch"):
        load_reports((annual, sources), rows)


def test_oversized_manifests_are_rejected_before_parsing(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_bytes(b"x" * (1024 * 1024 + 1))
    with pytest.raises(ValueError, match="collection_file_too_large"):
        load_history(tmp_path, NOW)


def test_nonmatching_condition_is_a_successful_query_without_a_company_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h, s, main, b = bundle(tmp_path)
    output = tmp_path / "nonmatch.json"
    assert invoke(monkeypatch, h, s, main, b, output, minimum="700") == 0
    data = json.loads(output.read_text())
    assert data["status"] == "document_non_match"
    assert data["selected_receipt"] == b.disclosure.receipt
    assert data["selected_report"]["amount_krw"] == "600"
    sheet = load_workbook(output.with_suffix(".xlsx")).worksheets[0]
    assert sheet["A3"].value != "HD건설기계" and sheet["B3"].value is None
