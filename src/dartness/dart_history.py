"""Capture bounded all-type filing-history responses using the existing complete-list collector."""

import hashlib
from dataclasses import asdict
from datetime import UTC, date, datetime

from dartness.dart_smoke import CollectionError, Fetch
from dartness.disclosure_list import ListRequest, collect_list


def parse_history_request(corp_code: str, start: str, end: str) -> ListRequest:
    try:
        return ListRequest(
            date.fromisoformat(start.strip()),
            date.fromisoformat(end.strip()),
            corp_code=corp_code.strip(),
        )
    except ValueError as error:
        raise CollectionError("invalid_history_request") from error


def collect_history(
    fetch: Fetch, request: ListRequest
) -> tuple[dict[str, object], dict[str, bytes]]:
    if not request.corp_code or request.corp_cls or request.disclosure_type:
        raise CollectionError("one_company_all_type_history_required")
    started = datetime.now(UTC)
    files: dict[str, bytes] = {}
    responses: list[dict[str, object]] = []

    def capture(endpoint: str, params: dict[str, str]) -> bytes:
        if endpoint != "list.json":
            raise CollectionError("history_listing_endpoint_required")
        payload = fetch(endpoint, params)
        filename = f"history/response-{len(responses) + 1:02}.json"
        files[filename] = payload
        responses.append(
            {
                "file": filename,
                "parameters": dict(params),
                "response_sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
        return payload

    result = collect_list(request, max_requests=10, fetch=capture)
    return {
        "purpose": "all-type one-company filing history; no correction or financial selection",
        "mode": "filing_history",
        "complete": True,
        "started_at": started.isoformat(),
        "collected_at": datetime.now(UTC).isoformat(),
        "request_count": result.requests,
        "request": {
            "corp_code": request.corp_code,
            "start": request.start.isoformat(),
            "end": request.end.isoformat(),
            "corp_cls": "",
            "disclosure_type": "",
        },
        "items": [{**asdict(item), "filed_on": item.filed_on.isoformat()} for item in result.items],
        "responses": responses,
    }, files
