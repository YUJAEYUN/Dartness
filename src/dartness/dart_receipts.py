"""Bounded source collection for explicitly supplied receipts; no filing selection."""

import hashlib
import re
from collections.abc import Mapping
from datetime import UTC, datetime

from dartness.dart_smoke import CollectionError, Fetch, read_archive


def parse_receipts(raw: str) -> list[str]:
    receipts = [value.strip() for value in raw.split(",")]
    if not 1 <= len(receipts) <= 2 or len(set(receipts)) != len(receipts):
        raise CollectionError("invalid_receipt_count")
    if any(not re.fullmatch(r"[0-9]{14}", value) for value in receipts):
        raise CollectionError("invalid_receipt")
    return receipts


def collect_receipts(
    fetch: Fetch, receipts: list[str]
) -> tuple[dict[str, object], dict[str, bytes]]:
    # Revalidate before making even the first request.
    wanted = parse_receipts(",".join(receipts))
    files: dict[str, bytes] = {}
    reports: list[dict[str, object]] = []
    for receipt in wanted:
        archive = fetch("document.xml", {"rcept_no": receipt})
        documents = read_archive(archive)
        main_name = receipt + ".xml"
        if main_name not in documents:
            raise CollectionError("requested_main_document_missing")
        files[f"{receipt}/document.zip"] = archive
        reports.append(
            {
                "receipt": receipt,
                "status": "collected",
                "dart_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}",
                "archive_sha256": hashlib.sha256(archive).hexdigest(),
                "main_document": main_name,
                "main_document_sha256": hashlib.sha256(documents[main_name]).hexdigest(),
                "documents": [
                    {"name": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                    for name, data in sorted(documents.items())
                ],
            }
        )
    return {
        "purpose": "exact receipt source collection; no extraction, relation or version selection",
        "mode": "exact_receipts",
        "complete": True,
        "collected_at": datetime.now(UTC).isoformat(),
        "request_count": len(wanted),
        "requested_receipts": wanted,
        "reports": reports,
    }, files


def ensure_no_credential(rendered: str, files: Mapping[str, bytes], key: str) -> None:
    """Check ZIP members too: compressed output must not hide a key from the wire scan."""
    if key in rendered:
        raise CollectionError("credential_in_output")
    for name, data in files.items():
        if key.encode() in data:
            raise CollectionError("credential_in_output")
        if name.endswith(".zip") and any(
            key.encode() in member for member in read_archive(data).values()
        ):
            raise CollectionError("credential_in_output")
