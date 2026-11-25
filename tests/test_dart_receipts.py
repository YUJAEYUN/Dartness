"""Offline exact-receipt collection and compressed credential rejection."""

import hashlib
import io
import zipfile
from pathlib import Path

import pytest
from test_dart_collect import KEY, archive

from dartness import dart_collect
from dartness.dart_receipts import collect_receipts, ensure_no_credential, parse_receipts
from dartness.dart_smoke import CollectionError

A, B = "20260318001192", "20260602000456"


def test_only_explicit_receipts_are_requested_and_archives_remain_unchanged() -> None:
    payloads = {A: archive({A + ".xml": b"original"}), B: archive({B + ".xml": b"corrected"})}
    calls = []

    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        calls.append((endpoint, params))
        return payloads[params["rcept_no"]]

    manifest, files = collect_receipts(fetch, [A, B])
    assert calls == [("document.xml", {"rcept_no": A}), ("document.xml", {"rcept_no": B})]
    assert files == {f"{receipt}/document.zip": data for receipt, data in payloads.items()}
    assert manifest["complete"] is True and manifest["request_count"] == 2
    assert manifest["requested_receipts"] == [A, B]
    reports = manifest["reports"]
    assert isinstance(reports, list)
    assert reports[0]["archive_sha256"] == hashlib.sha256(payloads[A]).hexdigest()
    assert reports[1]["main_document"] == B + ".xml"


@pytest.mark.parametrize(
    "raw", ["", A + ",", A + "," + A, A + "," + B + ",20260101000001", "../file", "2026"]
)
def test_invalid_or_unbounded_request_is_rejected_before_fetch(raw: str) -> None:
    with pytest.raises(CollectionError, match="invalid_receipt"):
        parse_receipts(raw)


def test_missing_requested_main_is_not_replaced_by_attachment() -> None:
    with pytest.raises(CollectionError, match="requested_main_document_missing"):
        collect_receipts(lambda endpoint, params: archive({A + "_00760.xml": b"attachment"}), [A])


def test_second_failure_does_not_return_a_complete_partial_batch() -> None:
    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        if params["rcept_no"] == B:
            raise CollectionError("rate_limit")
        return archive({A + ".xml": b"original"})

    with pytest.raises(CollectionError, match="rate_limit"):
        collect_receipts(fetch, [A, B])


def test_compressed_key_is_rejected_before_output() -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr(A + ".xml", ("source " + KEY).encode())
    payload = stream.getvalue()
    assert KEY.encode() not in payload
    with pytest.raises(CollectionError, match="credential_in_output"):
        ensure_no_credential("{}", {A + "/document.zip": payload}, KEY)


def test_exact_mode_uses_registered_key_without_stock_lookup_or_financial_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []
    monkeypatch.setenv("DART_API_KEY", KEY)
    monkeypatch.setenv("COLLECTION_MODE", "exact_receipts")
    monkeypatch.setenv("RECEIPT_NUMBERS", A + "," + B)
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

    def fetch(endpoint: str, params: dict[str, str], key: str) -> bytes:
        assert key == KEY
        calls.append(endpoint)
        return archive({params["rcept_no"] + ".xml": b"source"})

    monkeypatch.setattr(dart_collect, "fetch_bytes", fetch)
    assert dart_collect.main() == 0
    assert calls == ["document.xml", "document.xml"]
    assert (tmp_path / A / "document.zip").exists()
