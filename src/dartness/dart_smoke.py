"""Bounded, manually invoked OpenDART collection check; no financial extraction."""

import hashlib
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn
from xml.etree import ElementTree

_MAX_DOWNLOAD = 32 * 1024 * 1024
_MAX_UNCOMPRESSED = 128 * 1024 * 1024
_STOCK_CODE = "084990"
_FILING_DATE = "20260320"
_REPORT_NAME = "사업보고서 (2025.12)"
type Fetch = Callable[[str, dict[str, str]], bytes]


class CollectionError(Exception):
    """A safe, fixed diagnostic code; never includes a URL or upstream message."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: object, fp: object, code: int, msg: str, headers: object, newurl: str
    ) -> NoReturn:
        raise CollectionError("redirect_rejected")


def fetch_bytes(endpoint: str, params: dict[str, str], key: str) -> bytes:
    if endpoint not in {
        "corpCode.xml",
        "company.json",
        "list.json",
        "document.xml",
        "fnlttSinglAcntAll.json",
    }:
        raise CollectionError("unsupported_endpoint")
    query = urllib.parse.urlencode({**params, "crtfc_key": key})
    request = urllib.request.Request(f"https://opendart.fss.or.kr/api/{endpoint}?{query}")
    try:
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=30) as response:
            payload: object = response.read(_MAX_DOWNLOAD + 1)
    except urllib.error.HTTPError:
        raise CollectionError("http_error") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise CollectionError("network_error") from None
    if not isinstance(payload, bytes):
        raise CollectionError("invalid_response")
    if len(payload) > _MAX_DOWNLOAD:
        raise CollectionError("download_too_large")
    if key.encode() in payload:
        raise CollectionError("credential_in_response")
    return payload


def _xml(payload: bytes) -> ElementTree.Element:
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise CollectionError("unsafe_xml")
    try:
        return ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        raise CollectionError("invalid_xml") from None


def _api_status(status: object) -> None:
    if not isinstance(status, str):
        raise CollectionError("invalid_response")
    if status == "000":
        return
    groups = {
        "010": "authentication",
        "011": "authentication",
        "012": "ip_restricted",
        "013": "no_data",
        "014": "missing_file",
        "020": "rate_limit",
        "800": "maintenance",
        "901": "authentication",
    }
    raise CollectionError(groups.get(status or "", "api_error"))


def read_archive(payload: bytes) -> dict[str, bytes]:
    if not zipfile.is_zipfile(io.BytesIO(payload)):
        _api_status(_xml(payload).findtext("status"))
        raise CollectionError("expected_zip")
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
            if len(entries) > 100 or sum(x.file_size for x in entries) > _MAX_UNCOMPRESSED:
                raise CollectionError("archive_too_large")
            if len({x.filename for x in entries}) != len(entries):
                raise CollectionError("duplicate_archive_entries")
            return {x.filename: archive.read(x) for x in entries if not x.is_dir()}
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError):
        raise CollectionError("invalid_zip") from None


def _text(row: dict[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str):
        raise CollectionError("invalid_response")
    return value


def collect(fetch: Fetch) -> tuple[dict[str, object], bytes]:
    corp_archive = read_archive(fetch("corpCode.xml", {}))
    candidates: list[tuple[str, str]] = []
    for name, payload in corp_archive.items():
        if name.lower().endswith(".xml"):
            for row in _xml(payload).findall("list"):
                if row.findtext("stock_code") == _STOCK_CODE:
                    candidates.append(
                        (row.findtext("corp_code", ""), row.findtext("corp_name", ""))
                    )
    if len(candidates) != 1:
        raise CollectionError("ambiguous_company")
    corp_code, corp_name = candidates[0]
    if not re.fullmatch(r"[0-9]{8}", corp_code) or "헬릭스미스" not in corp_name:
        raise CollectionError("company_mismatch")
    try:
        result: object = json.loads(
            fetch(
                "list.json",
                {
                    "corp_code": corp_code,
                    "bgn_de": _FILING_DATE,
                    "end_de": _FILING_DATE,
                    "pblntf_detail_ty": "A001",
                    "last_reprt_at": "N",
                    "page_count": "100",
                },
            )
        )
    except (ValueError, UnicodeError):
        raise CollectionError("invalid_json") from None
    if not isinstance(result, dict):
        raise CollectionError("invalid_response")
    _api_status(result.get("status"))
    if result.get("total_page") != 1 or not isinstance(result.get("list"), list):
        raise CollectionError("unexpected_pagination")
    reports = [
        x
        for x in result["list"]
        if isinstance(x, dict)
        and x.get("report_nm") == _REPORT_NAME
        and x.get("corp_code") == corp_code
        and x.get("rcept_dt") == _FILING_DATE
        and x.get("stock_code") == _STOCK_CODE
    ]
    if len(reports) != 1:
        raise CollectionError("ambiguous_filing")
    receipt = _text(reports[0], "rcept_no")
    if not re.fullmatch(r"[0-9]{14}", receipt):
        raise CollectionError("invalid_receipt")
    original = fetch("document.xml", {"rcept_no": receipt})
    documents = read_archive(original)
    xml_documents = {
        name: data
        for name, data in documents.items()
        if name.lower().endswith(".xml") and data.strip()
    }
    if not xml_documents:
        raise CollectionError("missing_document_xml")
    manifest: dict[str, object] = {
        "status": "collected",
        "collected_at": datetime.now(UTC).isoformat(),
        "corp_code": corp_code,
        "stock_code": _STOCK_CODE,
        "corp_name": corp_name,
        "report_name": _REPORT_NAME,
        "filing_date": _FILING_DATE,
        "rcept_no": receipt,
        "report_period_from_name": "2025.12",
        "request_count": 3,
        "dart_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}",
        "zip_sha256": hashlib.sha256(original).hexdigest(),
        "documents": [
            {"name": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in xml_documents.items()
        ],
        "financial_extraction": "not_performed",
        "correction_history": "not_checked",
    }
    return manifest, original


def main() -> int:
    key = os.environ.get("DART_API_KEY", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9]{40}", key):
        print("DART collection failed: missing_or_invalid_key")
        return 1
    try:
        manifest, original = collect(lambda endpoint, params: fetch_bytes(endpoint, params, key))
        rendered = json.dumps(manifest, ensure_ascii=False, indent=2)
        if key in rendered or any(key.encode() in data for data in read_archive(original).values()):
            raise CollectionError("credential_in_output")
        target = Path("work/dart-smoke")
        target.mkdir(parents=True, exist_ok=True)
        (target / "manifest.json").write_text(rendered + "\n")
        (target / "document.zip").write_bytes(original)
    except CollectionError as error:
        print(f"DART collection failed: {error}")
        return 1
    print(
        "DART collection succeeded; see the artifact manifest. Financial extraction not performed."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
