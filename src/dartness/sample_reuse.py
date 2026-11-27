"""Same-Korean-day raw-source reuse for the manual sample, never for live relationship data."""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from dartness.query_contract import SEOUL

_MAX_BYTES = 32 * 1024 * 1024


def reusable_source(
    root: Path | None, endpoint: str, params: dict[str, str], now: datetime
) -> tuple[bytes, dict[str, object]] | None:
    if root is None or endpoint not in ("corpCode.xml", "document.xml"):
        return None
    if (endpoint == "corpCode.xml" and params) or (
        endpoint == "document.xml"
        and (set(params) != {"rcept_no"} or not re.fullmatch(r"[0-9]{14}", params["rcept_no"]))
    ):
        return None
    try:
        base = root.resolve(strict=True)
        index = base / "requests.json"
        if not index.exists():
            index = base / "report.json"
        if (
            not index.resolve(strict=True).is_relative_to(base)
            or index.stat().st_size > 1024 * 1024
        ):
            return None
        document = json.loads(index.read_bytes())
        records = document.get("requests") if isinstance(document, dict) else None
        if not isinstance(records, list) or len(records) > 50:
            return None
        found: list[tuple[bytes, dict[str, object]]] = []
        for record in records:
            if not isinstance(record, dict) or record.get("kind") != "api":
                continue
            if record.get("endpoint") != endpoint or record.get("parameters") != params:
                continue
            if record.get("failure") is not None or "sha256" not in record:
                continue
            # Reusing a reuse must preserve the original observation, never refresh its age.
            observed = record.get("source_observed_at", record.get("finished_at"))
            if not isinstance(observed, str):
                return None
            stamp = datetime.fromisoformat(observed)
            if stamp.utcoffset() is None or stamp > now:
                return None
            if stamp.astimezone(SEOUL).date() != now.astimezone(SEOUL).date():
                continue
            name, digest, size = record.get("file"), record.get("sha256"), record.get("bytes")
            if (
                not isinstance(name, str)
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or type(size) is not int
                or not 0 < size <= _MAX_BYTES
            ):
                return None
            path = (base / name).resolve(strict=True)
            if not path.is_relative_to(base) or not path.is_file() or path.stat().st_size != size:
                return None
            payload = path.read_bytes()
            if hashlib.sha256(payload).hexdigest() != digest:
                return None
            found.append(
                (
                    payload,
                    {"source_observed_at": observed, "source_sha256": digest, "source_file": name},
                )
            )
        if not found or len({hashlib.sha256(p).hexdigest() for p, _ in found}) != 1:
            return None
        return found[-1]
    except (OSError, ValueError):
        # An unusable optional cache is a miss; current collection/validation remains mandatory.
        return None
