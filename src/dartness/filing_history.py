"""Replay captured all-type responses; a manifest's complete flag is not proof."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from dartness.disclosure_list import ListRequest, ListResult, collect_list


@dataclass(frozen=True)
class HistoryResponse:
    parameters: tuple[tuple[str, str], ...]
    payload: bytes
    sha256: str


@dataclass(frozen=True)
class FilingHistory:
    request: ListRequest
    responses: tuple[HistoryResponse, ...]
    started_at: datetime
    collected_at: datetime

    def replay(self, executed_at: datetime) -> ListResult:
        times = (self.started_at, self.collected_at, executed_at)
        if any(not isinstance(t, datetime) or t.utcoffset() is None for t in times):
            raise ValueError("aware_history_times_required")
        if not self.started_at <= self.collected_at <= executed_at:
            raise ValueError("history_observation_time_mismatch")
        day = executed_at.astimezone(ZoneInfo("Asia/Seoul")).date()
        if (
            self.request.end != day
            or self.collected_at.astimezone(ZoneInfo("Asia/Seoul")).date() != day
        ):
            raise ValueError("history_execution_day_required")
        if not self.request.corp_code or self.request.corp_cls or self.request.disclosure_type:
            raise ValueError("all_type_company_history_required")
        remaining = iter(self.responses)

        def fetch(endpoint: str, parameters: dict[str, str]) -> bytes:
            response = next(remaining, None)
            if response is None:
                raise ValueError("history_response_missing")
            if (
                endpoint != "list.json"
                or len(dict(response.parameters)) != len(response.parameters)
                or dict(response.parameters) != parameters
                or hashlib.sha256(response.payload).hexdigest() != response.sha256
            ):
                raise ValueError("history_response_mismatch")
            return response.payload

        result = collect_list(self.request, max_requests=10, fetch=fetch)
        if next(remaining, None) is not None:
            raise ValueError("unexpected_history_response")
        return result

    def to_dict(self) -> dict[str, object]:
        return {
            "start": self.request.start.isoformat(),
            "end": self.request.end.isoformat(),
            "corp_code": self.request.corp_code,
            "started_at": self.started_at.isoformat(),
            "collected_at": self.collected_at.isoformat(),
            "response_sha256": [response.sha256 for response in self.responses],
        }
