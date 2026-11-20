import io
import json
import urllib.error
import zipfile
from unittest.mock import patch

import pytest

from dartness.dart_smoke import CollectionError, collect, fetch_bytes, main, read_archive


def archive(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipped:
        for name, data in files.items():
            zipped.writestr(name, data)
    return buffer.getvalue()


def responses() -> dict[str, bytes]:
    return {
        "corpCode.xml": archive(
            {
                "CORPCODE.xml": (
                    "<result><list><corp_code>00123456</corp_code><corp_name>헬릭스미스</corp_name>"
                    "<stock_code>084990</stock_code></list></result>"
                ).encode()
            }
        ),
        "list.json": json.dumps(
            {
                "status": "000",
                "total_page": 1,
                "list": [
                    {
                        "corp_code": "00123456",
                        "stock_code": "084990",
                        "report_nm": "사업보고서 (2025.12)",
                        "rcept_dt": "20260320",
                        "rcept_no": "20260320000001",
                    }
                ],
            }
        ).encode(),
        "document.xml": archive({"report.xml": b"<document>fixture</document>"}),
    }


def test_collects_only_one_matching_filing_and_records_identity() -> None:
    payloads = responses()
    calls: list[tuple[str, dict[str, str]]] = []

    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        calls.append((endpoint, params))
        return payloads[endpoint]

    manifest, original = collect(fetch)
    assert len(calls) == 3
    assert calls[1][1]["bgn_de"] == "20260320"
    assert calls[2] == ("document.xml", {"rcept_no": "20260320000001"})
    assert manifest["rcept_no"] == "20260320000001"
    assert manifest["financial_extraction"] == "not_performed"
    assert original == payloads["document.xml"]


@pytest.mark.parametrize(
    "code,reason",
    [
        ("010", "authentication"),
        ("012", "ip_restricted"),
        ("013", "no_data"),
        ("020", "rate_limit"),
        ("800", "maintenance"),
        ("900", "api_error"),
    ],
)
def test_api_failures_are_not_reported_as_success(code: str, reason: str) -> None:
    payloads = responses()
    payloads["list.json"] = json.dumps({"status": code, "message": "untrusted text"}).encode()
    with pytest.raises(CollectionError, match=f"^{reason}$"):
        collect(lambda endpoint, params: payloads[endpoint])


def test_ambiguous_filing_does_not_download_an_arbitrary_document() -> None:
    payloads = responses()
    payloads["list.json"] = payloads["list.json"].replace(b'"20260320"', b'"20260321"')
    with pytest.raises(CollectionError, match="ambiguous_filing"):
        collect(lambda endpoint, params: payloads[endpoint])


def test_more_than_one_page_is_not_silently_truncated() -> None:
    payloads = responses()
    payloads["list.json"] = payloads["list.json"].replace(b'"total_page": 1', b'"total_page": 2')
    with pytest.raises(CollectionError, match="unexpected_pagination"):
        collect(lambda endpoint, params: payloads[endpoint])


def test_non_zip_xml_error_has_safe_diagnostic() -> None:
    with pytest.raises(CollectionError, match="missing_file"):
        read_archive(b"<result><status>014</status><message>secret</message></result>")


def test_unsafe_xml_is_rejected() -> None:
    with pytest.raises(CollectionError, match="unsafe_xml"):
        read_archive(b'<!DOCTYPE x [<!ENTITY a "unsafe">]><result>&a;</result>')


def test_empty_xml_archive_is_not_a_document() -> None:
    payloads = responses()
    payloads["document.xml"] = archive({"empty.xml": b" "})
    with pytest.raises(CollectionError, match="missing_document_xml"):
        collect(lambda endpoint, params: payloads[endpoint])


def test_network_exception_never_exposes_a_key_or_url() -> None:
    secret = "K" * 40
    with patch("urllib.request.build_opener") as opener:
        opener.return_value.open.side_effect = urllib.error.URLError(
            f"https://example/?key={secret}"
        )
        with pytest.raises(CollectionError) as caught:
            fetch_bytes("list.json", {}, secret)
    assert str(caught.value) == "network_error"
    assert secret not in str(caught.value)


def test_echoed_key_is_rejected_before_storage() -> None:
    secret = "K" * 40
    with patch("urllib.request.build_opener") as opener:
        opener.return_value.open.return_value.__enter__.return_value.read.return_value = (
            secret.encode()
        )
        with pytest.raises(CollectionError, match="credential_in_response"):
            fetch_bytes("list.json", {}, secret)


def test_missing_key_fails_without_network_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DART_API_KEY", raising=False)
    with patch("urllib.request.build_opener") as opener:
        assert main() == 1
        opener.assert_not_called()
