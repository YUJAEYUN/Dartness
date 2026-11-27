"""Synthetic whole-universe pilot; no live source calls or listing completeness claim."""

import io
import json
import zipfile
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook
from test_listed_universe import REGISTRATIONS, archive, profile
from test_small_cash_e2e import fixture

from dartness.cash_survey import write_cash_survey_workbook
from dartness.dart_smoke import CollectionError
from dartness.query_contract import SnapshotRequest
from dartness.universe_cash import UniverseCashPlan, collect_universe_cash


class Sources:
    def __init__(self) -> None:
        self.today, self.payloads = fixture()
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.web_calls: list[str] = []
        self.rows = json.loads(self.payloads["list.json"])
        self.rows["list"][0].update(corp_code="00000001", stock_code="100001")
        self.payloads["list.json"] = json.dumps(self.rows).encode()
        raw = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.payloads["document.xml"])) as original:
            name = original.namelist()[0]
            body = original.read(name).replace(b"01205842", b"00000001")
        with zipfile.ZipFile(raw, "w") as document:
            document.writestr(name, body)
        self.payloads["document.xml"] = raw.getvalue()
        self.payloads["body"] = self.payloads["body"].replace(b"01205842", b"00000001")

    def fetch(self, endpoint: str, params: dict[str, str]) -> bytes:
        self.calls.append((endpoint, dict(params)))
        if endpoint == "corpCode.xml":
            return archive(REGISTRATIONS)
        if endpoint == "company.json":
            code = params["corp_code"]
            return profile(
                {"00000001": "Y", "00000002": "K", "00000003": "N"}[code],
                {"00000001": "100001", "00000002": "200002", "00000003": "300003"}[code],
            )
        return self.payloads[endpoint]

    def web(self, url: str) -> bytes:
        self.web_calls.append(url)
        return self.payloads["body"]

    def plan(self) -> UniverseCashPlan:
        return UniverseCashPlan(
            SnapshotRequest("cash", "latest", 12),
            "standalone",
            Decimal(600),
            self.today.replace(day=1),
            20,
            10,
            1,
            8,
            (("00000001", "separate"),),
        )


def test_full_membership_is_preserved_while_only_one_source_is_collected(tmp_path: Path) -> None:
    source = Sources()
    result = collect_universe_cash(source.plan(), fetch=source.fetch, web=source.web)
    assert result.api_requests == 6 and result.web_requests == 1
    assert result.survey.universe.requests == 4
    assert result.selected_codes == ("00000001",)
    assert result.survey.counts == {
        "document_match": 1,
        "document_non_match": 0,
        "needs_review": 0,
        "not_processed": 2,
    }
    assert result.survey.entries[1].reason == "company_limit_reached"
    assert result.survey.entries[2].reason == "company_limit_reached"
    assert result.survey.all_targets_processed is False
    assert [p["corp_code"] for e, p in source.calls if e == "company.json"] == [
        "00000001",
        "00000002",
        "00000003",
    ]
    assert [p["corp_code"] for e, p in source.calls if e == "list.json"] == ["00000001"]
    path = tmp_path / "matches.xlsx"
    write_cash_survey_workbook(result.survey, path)
    sheet = load_workbook(path).active
    assert sheet is not None and sheet["B3"].value == 0.000007
    assert sheet["A3"].value == result.survey.universe.companies[0].name
    exported = result.to_dict()["survey"]
    assert isinstance(exported, dict)
    assert len(exported["companies"]) == 3


def test_unconfirmed_scope_uses_no_source_requests_and_never_guesses_separate() -> None:
    source = Sources()
    result = collect_universe_cash(
        replace(source.plan(), basis_by_corp=()), fetch=source.fetch, web=source.web
    )
    assert result.api_requests == 4 and result.web_requests == 0
    assert result.survey.entries[0].reason == "basis_not_confirmed_for_requested_scope"
    assert result.survey.entries[0].result is None
    assert result.survey.counts["needs_review"] == 1 and result.survey.counts["not_processed"] == 2


def test_one_api_budget_covers_universe_and_source_fetch_without_dropping_targets() -> None:
    source = Sources()
    result = collect_universe_cash(
        replace(source.plan(), max_api_requests=5), fetch=source.fetch, web=source.web
    )
    assert result.api_requests == 5 and len(source.calls) == 5
    assert result.survey.entries[0].reason == "universe_cash_api_budget"
    assert result.survey.counts["needs_review"] == 1 and len(result.survey.entries) == 3


def test_incomplete_universe_does_not_become_a_smaller_success() -> None:
    source = Sources()
    with pytest.raises(CollectionError, match="universe_request_budget"):
        collect_universe_cash(
            replace(source.plan(), max_api_requests=3), fetch=source.fetch, web=source.web
        )
    assert len(source.calls) == 1


def test_source_failure_is_not_zero_or_nonmatch() -> None:
    source = Sources()
    source.payloads["document.xml"] = b"broken"
    result = collect_universe_cash(source.plan(), fetch=source.fetch, web=source.web)
    assert result.survey.entries[0].reason == "invalid_xml"
    assert result.survey.entries[0].result is None
    assert result.survey.counts["document_non_match"] == 0


def test_explicit_targets_must_belong_to_the_current_full_universe() -> None:
    source = Sources()
    with pytest.raises(ValueError, match="outside_current_universe"):
        collect_universe_cash(
            replace(source.plan(), target_codes=("99999999",)), fetch=source.fetch, web=source.web
        )
    assert len(source.calls) == 4


def test_configurable_amount_is_exact_and_not_fixed_to_the_demo_threshold() -> None:
    source = Sources()
    result = collect_universe_cash(
        replace(source.plan(), minimum_krw=Decimal(800)), fetch=source.fetch, web=source.web
    )
    assert result.survey.counts["document_non_match"] == 1
    report = result.survey.entries[0].result
    assert report is not None and report.report is not None
    assert report.report.to_dict()["amount_krw"] == "700"


@pytest.mark.parametrize("change", ["zero", "many", "bool", "nan"])
def test_invalid_plans_are_rejected_before_network(change: str) -> None:
    source = Sources()
    with pytest.raises(ValueError):
        if change == "zero":
            replace(source.plan(), max_companies=0)
        elif change == "many":
            replace(source.plan(), max_companies=11)
        elif change == "bool":
            replace(source.plan(), max_api_requests=True)
        else:
            replace(source.plan(), minimum_krw=Decimal("NaN"))
    assert source.calls == []


def test_future_history_start_is_rejected_without_io() -> None:
    source = Sources()
    with pytest.raises(ValueError, match="history_start_after_execution"):
        collect_universe_cash(
            replace(source.plan(), history_start=date(2099, 1, 1)),
            fetch=source.fetch,
            web=source.web,
        )
    assert source.calls == []


def test_report_limit_never_silently_keeps_only_one_of_two_listed_sources() -> None:
    source = Sources()
    extra = {**source.rows["list"][0], "rcept_no": "20260318001193"}
    source.rows.update(total_count=2, list=[source.rows["list"][0], extra])
    source.payloads["list.json"] = json.dumps(source.rows).encode()
    result = collect_universe_cash(
        replace(source.plan(), max_reports_per_company=1), fetch=source.fetch, web=source.web
    )
    assert result.api_requests == 5 and result.web_requests == 0
    assert result.survey.entries[0].reason == "company_report_budget_exceeded"
    assert result.survey.entries[0].result is None
    assert len(result.survey.entries) == 3


def test_wrong_company_response_does_not_leak_another_company_value() -> None:
    source = Sources()
    plan = replace(
        source.plan(), target_codes=("00000002",), basis_by_corp=(("00000002", "separate"),)
    )
    result = collect_universe_cash(plan, fetch=source.fetch, web=source.web)
    assert result.selected_codes == ("00000002",)
    assert result.survey.entries[0].reason == "company_limit_reached"
    assert result.survey.entries[1].result is None
    assert result.survey.entries[1].reason == "listing_scope_mismatch"
    assert result.survey.counts["document_match"] == 0
    assert result.survey.counts["needs_review"] == 1


@pytest.mark.parametrize(
    "web_limit,reason,web_calls",
    [(10, "same_day_publication_ambiguous", 3), (1, "universe_cash_web_budget", 1)],
)
def test_multiple_receipt_batches_and_web_budget_preserve_the_complete_target_set(
    web_limit: int,
    reason: str,
    web_calls: int,
) -> None:
    source = Sources()
    with zipfile.ZipFile(io.BytesIO(source.payloads["document.xml"])) as archive:
        xml = archive.read(archive.namelist()[0])
    first = source.rows["list"][0]
    rows = [first, {**first, "rcept_no": "20260318001193"}, {**first, "rcept_no": "20260318001194"}]
    source.rows.update(total_count=3, list=rows)
    source.payloads["list.json"] = json.dumps(source.rows).encode()

    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        if endpoint != "document.xml":
            return source.fetch(endpoint, params)
        source.calls.append((endpoint, dict(params)))
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr(params["rcept_no"] + ".xml", xml)
        return output.getvalue()

    result = collect_universe_cash(
        replace(source.plan(), max_reports_per_company=3, max_web_requests=web_limit),
        fetch=fetch,
        web=source.web,
    )
    assert result.api_requests == 8 and result.web_requests == web_calls
    assert [p["rcept_no"] for e, p in source.calls if e == "document.xml"] == [
        "20260318001192",
        "20260318001193",
        "20260318001194",
    ]
    assert result.survey.entries[0].reason == reason
    assert result.survey.counts["needs_review"] == 1 and result.survey.counts["not_processed"] == 2
    assert result.survey.entries[0].result is None or result.survey.entries[0].result.report is None


def test_day_change_after_universe_stops_before_collecting_source_data() -> None:
    from datetime import UTC, datetime, timedelta

    source = Sources()
    started = datetime.now(UTC)
    calls = 0

    def clock() -> datetime:
        nonlocal calls
        calls += 1
        return started if calls <= 6 else started + timedelta(days=1)

    with pytest.raises(ValueError, match="universe_cash_execution_day_changed"):
        collect_universe_cash(source.plan(), fetch=source.fetch, web=source.web, clock=clock)
    assert len(source.calls) == 4 and source.web_calls == []
    assert not any(endpoint == "list.json" for endpoint, _ in source.calls)
