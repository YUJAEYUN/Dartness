"""Latest publication policy: synthetic cases plus already-inspected real-dev reports."""

import gzip
import hashlib
import io
import json
import zipfile
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from test_native_correction import INPUTS, A, B

from dartness.cash_contract import CashValue
from dartness.cash_report_candidates import StoredCashReport
from dartness.dart_history import collect_history
from dartness.disclosure_list import Disclosure, ListRequest
from dartness.filing_history import FilingHistory, HistoryResponse
from dartness.latest_cash import BodyObservation, CorrectionPair, query_latest_cash
from dartness.query_contract import QueryRun, SnapshotRequest

NOW = datetime(2026, 11, 26, 2, tzinfo=UTC)
CORP = "01205842"
FIXTURE = Path(__file__).parent / "fixtures/corrections/hd-history-2026"


def request(day: date | None = date(2025, 12, 31)) -> QueryRun:
    return QueryRun(
        SnapshotRequest(
            "cash", "latest" if day is None else "as_of", 12 if day is None else 0, day
        ),
        NOW,
    )


def history_for(rows: tuple[Disclosure, ...]) -> FilingHistory:
    def fetch(endpoint: str, params: dict[str, str]) -> bytes:
        selected = [
            r for r in rows if params["bgn_de"] <= r.filed_on.strftime("%Y%m%d") <= params["end_de"]
        ]
        if not selected:
            return b'{"status":"013"}'
        return json.dumps(
            {
                "status": "000",
                "page_no": 1,
                "page_count": 100,
                "total_count": len(selected),
                "total_page": 1,
                "list": [
                    {
                        "rcept_no": r.receipt,
                        "corp_code": r.corp_code,
                        "corp_name": r.corp_name,
                        "corp_cls": r.corp_cls,
                        "stock_code": r.stock_code,
                        "report_nm": r.report_name,
                        "rcept_dt": r.filed_on.strftime("%Y%m%d"),
                        "flr_nm": r.filer_name,
                        "rm": r.remarks,
                    }
                    for r in selected
                ],
            }
        ).encode()

    req = ListRequest(date(2026, 3, 18), date(2026, 11, 26), CORP)
    manifest, files = collect_history(fetch, req)
    responses = manifest["responses"]
    assert isinstance(responses, list)
    return FilingHistory(
        req,
        tuple(
            HistoryResponse(tuple(r["parameters"].items()), files[r["file"]], r["response_sha256"])
            for r in responses
        ),
        NOW,
        NOW,
    )


def body(source: StoredCashReport) -> BodyObservation:
    d = source.disclosure
    kind = "분기보고서" if "분기" in d.report_name else "사업보고서"
    html = f'''<span onclick="openCorpInfoNew('{CORP}', 'x')"></span><select id="family">
<option value="rcpNo={d.receipt}" title="{kind}" selected>{d.filed_on:%Y.%m.%d} {kind}</option>
</select>'''
    return BodyObservation(d.receipt, html.encode(), NOW)


def synthetic(interim: bool, amount: str = "600") -> StoredCashReport:
    receipt, filed, kind, code, end = (
        ("20261116001470", date(2026, 11, 16), "분기보고서", "11013", "2026.09.30")
        if interim
        else ("20260318001192", date(2026, 3, 18), "사업보고서", "11011", "2025.12.31")
    )
    current = "제10기3분기말" if interim else "제9기"
    previous = "제9기말" if interim else "제8기"
    prior = "2025.12.31" if interim else "2024.12.31"
    start = "20260101" if interim else "20250101"
    endvalue = end.replace(".", "")
    titlemonth = end[:7].replace(".", ".")
    raw = f'''<DOCUMENT><DOCUMENT-NAME ACODE="{code}">{kind}</DOCUMENT-NAME>
<COMPANY-NAME AREGCIK="{CORP}">HD건설기계</COMPANY-NAME><BODY><COVER>
<TU AUNIT="PERIODFROM" AUNITVALUE="{start}">{start[:4]}년01월01일</TU>
<TU AUNIT="PERIODTO" AUNITVALUE="{endvalue}">{endvalue[:4]}년{endvalue[4:6]}월{endvalue[6:]}일</TU>
</COVER><TABLE-GROUP ACLASS="{{XBRL}}BS_S"><TABLE><TR><TD>재무상태표</TD></TR>
<TR><TD>{current} {end} 현재</TD></TR><TR><TD>{previous} {prior} 현재</TD></TR>
<TR><TD>(단위:원)</TD></TR></TABLE><TABLE><TR><TH></TH><TH>{current}</TH><TH>{previous}</TH></TR>
<TR><TD>현금및현금성자산</TD><TD>700</TD><TD>{amount}</TD></TR></TABLE></TABLE-GROUP></BODY></DOCUMENT>'''
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr(receipt + ".xml", raw)
    return StoredCashReport(
        Disclosure(
            receipt,
            CORP,
            "HD건설기계",
            "Y",
            "267270",
            f"{kind} ({titlemonth})",
            filed,
            "HD건설기계",
            "",
        ),
        out.getvalue(),
    )


def test_newer_valid_source_wins_even_when_amount_differs_from_old_source() -> None:
    a, b = synthetic(False), synthetic(True, "650")
    result = query_latest_cash(
        request(),
        CORP,
        "separate",
        Decimal(640),
        history_for((a.disclosure, b.disclosure)),
        (b, a),
        (body(b),),
    )
    assert result.reason is None and result.status == "document_match"
    assert result.report is not None and isinstance(result.report.value, CashValue)
    assert result.report.disclosure.receipt == b.disclosure.receipt
    assert result.report.value.amount_krw == Decimal(650)  # older source has 700 for 2025-12-31
    assert result.report.value.as_of == date(2025, 12, 31)


@pytest.mark.parametrize(
    "failure", ["missing", "corrupt", "body", "remarks", "same_day", "attachment", "withdrawal"]
)
def test_unverified_latest_is_never_replaced_with_older_source(failure: str) -> None:
    a, b = synthetic(False), synthetic(True)
    rows: tuple[Disclosure, ...] = (a.disclosure, b.disclosure)
    reports: tuple[StoredCashReport, ...] = (a, b)
    observations: tuple[BodyObservation, ...] = (body(b),)
    if failure == "missing":
        reports = (a,)
    elif failure == "corrupt":
        reports = (a, replace(b, archive=b"broken"))
    elif failure == "body":
        observations = ()
    elif failure == "remarks":
        b = replace(b, disclosure=replace(b.disclosure, remarks="정"))
        rows, reports = (a.disclosure, b.disclosure), (a, b)
    else:
        name = {
            "same_day": "분기보고서 (2026.09)",
            "attachment": "[첨부정정]분기보고서 (2026.09)",
            "withdrawal": "철회신고서",
        }[failure]
        extra = replace(b.disclosure, receipt="20261116001471", report_name=name)
        rows += (extra,)
        with zipfile.ZipFile(io.BytesIO(b.archive)) as source:
            raw = source.read(b.disclosure.receipt + ".xml")
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as target:
            target.writestr(extra.receipt + ".xml", raw)
        reports += (StoredCashReport(extra, out.getvalue()),)
    result = query_latest_cash(
        request(), CORP, "separate", Decimal(0), history_for(rows), reports, observations
    )
    assert result.status == "needs_review" and result.report is None and result.reason
    assert result.to_dict()["selected_receipt"] is None
    expected = {
        "missing": "periodic_source_set_incomplete_or_duplicate",
        "corrupt": "source_incomplete:expected_zip",
        "body": "selected_body_observation_required",
        "remarks": "correction_unresolved",
        "same_day": "same_day_publication_ambiguous",
        "attachment": "unsupported_periodic_filing",
        "withdrawal": "withdrawal_or_order_requires_review",
    }
    assert result.reason == expected[failure]


@pytest.mark.parametrize(
    "change", ["hash", "parameters", "missing", "extra", "filtered", "old_day", "future"]
)
def test_history_complete_flag_cannot_hide_invalid_raw_capture(change: str) -> None:
    source = synthetic(True)
    h = history_for((source.disclosure,))
    if change == "hash":
        h = replace(h, responses=(replace(h.responses[0], sha256="0" * 64), *h.responses[1:]))
    elif change == "parameters":
        h = replace(h, responses=(replace(h.responses[0], parameters=()), *h.responses[1:]))
    elif change == "missing":
        h = replace(h, responses=h.responses[:-1])
    elif change == "extra":
        h = replace(h, responses=h.responses + (h.responses[0],))
    elif change == "filtered":
        h = replace(h, request=replace(h.request, disclosure_type="A"))
    elif change == "old_day":
        h = replace(
            h,
            collected_at=datetime(2026, 11, 25, tzinfo=UTC),
            started_at=datetime(2026, 11, 25, tzinfo=UTC),
        )
    elif change == "future":
        h = replace(h, collected_at=datetime(2026, 11, 27, tzinfo=UTC))
    result = query_latest_cash(
        request(), CORP, "separate", Decimal(0), h, (source,), (body(source),)
    )
    assert result.report is None and result.reason


def real_inputs() -> tuple[
    FilingHistory, tuple[StoredCashReport, ...], tuple[BodyObservation, ...]
]:
    m = json.loads((FIXTURE / "history-manifest.json").read_text())
    h = FilingHistory(
        ListRequest(date(2026, 3, 18), date(2026, 11, 26), CORP),
        tuple(
            HistoryResponse(
                tuple(r["parameters"].items()),
                (FIXTURE / r["file"]).read_bytes(),
                r["response_sha256"],
            )
            for r in m["responses"]
        ),
        datetime.fromisoformat(m["started_at"]),
        datetime.fromisoformat(m["collected_at"]),
    )
    rows = h.replay(NOW).items
    reports = [
        replace(source, disclosure=next(r for r in rows if r.receipt == source.disclosure.receipt))
        for source in (A, B)
    ]
    for name in ("later-reports", "first-quarter"):
        origin = json.loads((FIXTURE / (name + "-manifest.json")).read_text())
        for record in origin["reports"]:
            archive = (FIXTURE / (record["receipt"] + ".zip")).read_bytes()
            assert hashlib.sha256(archive).hexdigest() == record["archive_sha256"]
            reports.append(
                StoredCashReport(next(r for r in rows if r.receipt == record["receipt"]), archive)
            )
    v = json.loads((FIXTURE / "viewer-origin.json").read_text())
    observations = tuple(
        BodyObservation(
            r["receipt"],
            gzip.decompress((FIXTURE / (r["receipt"] + "-viewer.html.gz")).read_bytes()),
            datetime.fromisoformat(r["observed_at"]),
        )
        for r in v
    )
    return h, tuple(reports), observations


@pytest.mark.parametrize(
    "day,amount", [(date(2025, 12, 31), "69787650000"), (None, "134070870000")]
)
def test_real_dev_full_history_uses_latest_quarter_and_correct_period_column(
    day: date | None, amount: str
) -> None:
    h, sources, bodies = real_inputs()
    result = query_latest_cash(
        request(day), CORP, "separate", Decimal(50000000000), h, sources, bodies
    )
    assert result.reason is None and result.status == "document_match"
    assert result.report is not None and isinstance(result.report.value, CashValue)
    assert result.report.disclosure.receipt == "20261116001470"
    assert result.report.value.amount_krw == Decimal(amount)
    assert result.report.value.as_of == (day or date(2026, 9, 30))
    assert len(result.sources) == 6 and result.to_dict()["latest_correction_verified"] is True
    assert (
        result.report.document_sha256
        == "341f438db7311b58d6d9b7ae22c0fe9fcbe2508edccb73f2cf1e9d5eaf1bdbb4"
    )


def test_real_annual_pair_with_synthetic_listing_uses_verified_corrected_source() -> None:
    # Real source pair/web; synthetic restricted history is NOT a new real full-history evaluation.
    a = replace(A, disclosure=replace(A.disclosure, report_name="사업보고서 (2025.12)"))
    b = replace(B, disclosure=replace(B.disclosure, report_name="[기재정정]사업보고서 (2025.12)"))
    h = history_for((a.disclosure, b.disclosure))
    observation = BodyObservation(B.disclosure.receipt, INPUTS.correction_main, NOW)
    result = query_latest_cash(
        request(),
        CORP,
        "separate",
        Decimal(0),
        h,
        (a, b),
        (observation,),
        (CorrectionPair(A.disclosure.receipt, B.disclosure.receipt, INPUTS),),
    )
    assert result.reason is None and result.report is not None
    assert result.report.disclosure.receipt == B.disclosure.receipt
    assert result.validity is not None and "correction_binding" in result.validity


@pytest.mark.parametrize("problem", ["missing_proof", "extra_family", "later_marker"])
def test_real_annual_correction_is_not_applied_without_complete_pair_evidence(problem: str) -> None:
    a = replace(A, disclosure=replace(A.disclosure, report_name="사업보고서 (2025.12)"))
    b = replace(B, disclosure=replace(B.disclosure, report_name="[기재정정]사업보고서 (2025.12)"))
    if problem == "later_marker":
        b = replace(b, disclosure=replace(b.disclosure, remarks="정"))
    h = history_for((a.disclosure, b.disclosure))
    payload = INPUTS.correction_main
    if problem == "extra_family":
        pos = payload.index(b"</select>", payload.index(b'id="family"'))
        extra = (
            '<option value="rcpNo=20260702000001" title="사업보고서">'
            "2026.07.02 [정정]사업보고서</option>"
        ).encode()
        payload = payload[:pos] + extra + payload[pos:]
    pairs = (
        ()
        if problem == "missing_proof"
        else (CorrectionPair(a.disclosure.receipt, b.disclosure.receipt, INPUTS),)
    )
    result = query_latest_cash(
        request(),
        CORP,
        "separate",
        Decimal(0),
        h,
        (a, b),
        (BodyObservation(b.disclosure.receipt, payload, NOW),),
        pairs,
    )
    assert result.report is None
    expected = {
        "missing_proof": "correction_pair_evidence_required",
        "extra_family": "body_listing_history_mismatch",
        "later_marker": "further_correction_unresolved",
    }
    assert result.reason == expected[problem]


def test_latest_date_is_selected_before_the_latest_document_for_an_older_date() -> None:
    a, b = synthetic(False), synthetic(True)
    # A late-filed annual report still only contains older financial dates.
    a = replace(a, disclosure=replace(a.disclosure, filed_on=date(2026, 11, 20)))
    result = query_latest_cash(
        request(None),
        CORP,
        "separate",
        Decimal(0),
        history_for((a.disclosure, b.disclosure)),
        (a, b),
        (body(b),),
    )
    assert result.report is not None and isinstance(result.report.value, CashValue)
    assert result.report.disclosure.receipt == b.disclosure.receipt
    assert result.report.value.as_of == date(2026, 9, 30)


def test_newer_unobserved_body_and_wrong_company_are_not_accepted() -> None:
    a, b = synthetic(False), synthetic(True)
    h = history_for((a.disclosure, b.disclosure))
    proof = replace(body(b), observed_at=datetime(2026, 11, 27, tzinfo=UTC))
    result = query_latest_cash(request(), CORP, "separate", Decimal(0), h, (a, b), (proof,))
    assert result.reason == "body_observation_execution_day_required" and result.report is None
    with zipfile.ZipFile(io.BytesIO(b.archive)) as archive:
        raw = archive.read(b.disclosure.receipt + ".xml")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(b.disclosure.receipt + ".xml", raw.replace(CORP.encode(), b"00000001"))
    changed = replace(b, archive=buffer.getvalue())
    result = query_latest_cash(request(), CORP, "separate", Decimal(0), h, (a, changed), (body(b),))
    assert result.report is None and result.reason == "source_incomplete:document_company_mismatch"
