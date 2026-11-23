"""Real-dev source evidence and current safe candidate behavior, not a new resolver."""

import gzip
import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from dartness.disclosure_candidate import (
    CandidateKey,
    CandidateRequest,
    CandidateSource,
    DisclosureCandidate,
    select_candidate,
)
from dartness.query_contract import QueryRun, SnapshotRequest

FIXTURE = Path(__file__).parent / "fixtures/corrections/hd-construction-2025"
CASE = json.loads((FIXTURE / "expected.json").read_text())
NS = {"x": "http://www.xbrl.org/2003/instance", "d": "http://xbrl.org/2006/xbrldi"}
CASH = "{http://xbrl.ifrs.org/taxonomy/2021-03-24/ifrs-full}CashAndCashEquivalents"
AXIS = "ifrs-full:ConsolidatedAndSeparateFinancialStatementsAxis"


def source_xml(version: str) -> ET.Element:
    record = CASE["versions"][version]["excerpt"]
    packed = (FIXTURE / record["file"]).read_bytes()
    assert hashlib.sha256(packed).hexdigest() == record["compressed_sha256"]
    decoded = gzip.decompress(packed)
    assert hashlib.sha256(decoded).hexdigest() == record["decoded_sha256"]
    assert b"<!DOCTYPE" not in decoded.upper()
    return ET.fromstring(decoded)


@pytest.mark.parametrize("version", ["original", "correction"])
@pytest.mark.parametrize("basis", ["separate", "consolidated"])
def test_pdf_preverified_current_cash_matches_native_xbrl_context(version: str, basis: str) -> None:
    # Fixed expected.json values were read from PDF rows before writing this test.
    expected = CASE["expected"]["current_cash"][basis]
    root = source_xml(version)
    context = root.find(f"x:context[@id='{expected['context_id']}']", NS)
    assert context is not None
    assert context.findtext("x:entity/x:identifier", namespaces=NS) == "01205842"
    assert context.findtext("x:period/x:instant", namespaces=NS) == "2025-12-31"
    members = context.findall(".//d:explicitMember", NS)
    assert len(members) == 1
    assert members[0].attrib["dimension"] == AXIS
    assert members[0].text == expected["member"]
    facts = [f for f in root.findall(CASH) if f.attrib["contextRef"] == expected["context_id"]]
    assert len(facts) == 1
    fact = facts[0]
    assert fact.attrib["unitRef"] == "KRW"
    assert root.findtext("x:unit[@id='KRW']/x:measure", namespaces=NS) == "iso4217:KRW"
    assert fact.attrib["decimals"] == "-3"
    assert fact.text is not None
    assert Decimal(fact.text) == Decimal(expected["amount_krw"])
    pdf = CASE["versions"][version]["pdf_text_excerpts"][basis]
    data = (FIXTURE / pdf["file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == pdf["sha256"]
    text = data.decode()
    assert "2025.12.31" in text
    assert "천원" in text
    assert "현금및현금성자산" in text
    assert expected["pdf_raw_thousand_krw"] in text
    assert Decimal(expected["pdf_raw_thousand_krw"].replace(",", "")) * 1000 == Decimal(
        expected["amount_krw"]
    )


def fact_signatures(root: ET.Element) -> set[tuple[str, str, str, str, str]]:
    """Source comparison only; this is not an extraction API or version choice."""
    contexts = {c.attrib["id"]: c for c in root.findall("x:context", NS)}
    result = set()
    for f in root.findall(CASH):
        c = contexts[f.attrib["contextRef"]]
        # Compare actual entity/period/dimensions too, not just context ID spelling.
        semantic = ET.canonicalize(ET.tostring(c, encoding="unicode"), strip_text=True)
        result.add(
            (
                f.attrib["contextRef"],
                f.attrib["unitRef"],
                f.attrib["decimals"],
                f.text or "",
                semantic,
            )
        )
    return result


def test_the_14_cash_fact_signatures_match_but_full_sources_are_different() -> None:
    before, after = (
        fact_signatures(source_xml("original")),
        fact_signatures(source_xml("correction")),
    )
    assert len(before) == len(after) == 14
    assert before == after
    a, b = CASE["versions"]["original"], CASE["versions"]["correction"]
    assert a["instance_sha256"] != b["instance_sha256"]
    assert a["pdf"]["sha256"] != b["pdf"]["sha256"]
    assert a["xbrl_archive"]["sha256"] != b["xbrl_archive"]["sha256"]


@pytest.mark.parametrize("version", ["original", "correction"])
def test_other_periods_and_rounded_contexts_are_present_not_silently_substituted(
    version: str,
) -> None:
    root = source_xml(version)
    contexts = {c.attrib["id"]: c for c in root.findall("x:context", NS)}
    facts = root.findall(CASH)
    assert len(facts) == 14
    assert {
        contexts[f.attrib["contextRef"]].findtext("x:period/x:instant", namespaces=NS)
        for f in facts
    } == {"2023-12-31", "2024-12-31", "2025-12-31"}
    rounded = [f for f in facts if f.attrib["decimals"] == "-6"]
    assert {f.text for f in rounded} >= {"69788000000", "337873000000"}
    assert all(
        len(contexts[f.attrib["contextRef"]].findall(".//d:explicitMember", NS)) > 1
        for f in rounded
    )


@pytest.mark.parametrize("version", ["original", "correction"])
def test_cover_and_errata_keep_original_submission_and_correction_dates_separate(
    version: str,
) -> None:
    records = CASE["versions"][version]["pdf_text_excerpts"]
    for part in records.values():
        data = (FIXTURE / part["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == part["sha256"]
    cover = (FIXTURE / records["cover"]["file"]).read_text()
    assert "2025년 01월 01일" in cover and "2025년 12월 31일" in cover
    assert "03월" in cover and "18일" in cover
    if version == "correction":
        errata = (FIXTURE / records["errata"]["file"]).read_text()
        assert "2026년 06월 02일" in errata
        assert "2026년 03월 18일" in errata
        assert "디테일 태깅" in errata and "블록 태깅" in errata


def candidate(version: str, basis: str) -> DisclosureCandidate:
    version_record = CASE["versions"][version]
    receipt = CASE[version + "_receipt"]
    expected = CASE["expected"]["current_cash"][basis]
    return DisclosureCandidate(
        CandidateKey("01205842", "cash", "cash-and-cash-equivalents", basis, "KRW"),
        date(2025, 12, 31),
        CandidateSource(
            receipt,
            date.fromisoformat(CASE[version + "_submission_date"]),
            version_record["pdf"]["url"],
            version_record["pdf"]["sha256"],
            f"PDF physical page {version_record['pdf_text_excerpts'][basis]['physical_pdf_page']}",
            f"{basis}; 2025-12-31; 천원; {expected['pdf_raw_thousand_krw']}",
        ),
    )


def request(executed_at: datetime, basis: str) -> CandidateRequest:
    return CandidateRequest(
        QueryRun(SnapshotRequest("cash", "as_of", 0, date(2025, 12, 31)), executed_at),
        candidate("original", basis).key,
    )


@pytest.mark.parametrize("basis", ["separate", "consolidated"])
def test_real_sources_before_correction_cutoff_keep_full_original_pdf_provenance(
    basis: str,
) -> None:
    original, correction = candidate("original", basis), candidate("correction", basis)
    result = select_candidate(
        request(datetime(2026, 5, 1, 0, tzinfo=UTC), basis), [original, correction]
    )
    assert result.status == "selected"
    assert result.candidate is original
    assert result.candidate.source.document_id == "20260318001192"
    assert (
        result.candidate.source.document_sha256
        == "e02855fea4ca6b6210aa4faeae347b28c0288a954f98fe09d145b6042a25aa01"
    )
    assert result.candidates == (original, correction)


@pytest.mark.parametrize("basis", ["separate", "consolidated"])
def test_equal_cash_values_do_not_bypass_unimplemented_correction_resolution(basis: str) -> None:
    wanted = request(datetime(2026, 11, 23, 0, tzinfo=UTC), basis)
    inputs = [candidate("original", basis), candidate("correction", basis)]
    for rows in (inputs, reversed(inputs)):
        result = select_candidate(wanted, rows)
        assert result.status == "needs_review"
        assert result.reason == "ambiguous_candidate"
        assert result.candidate is None
        assert {c.source.document_id for c in result.candidates} == {
            "20260318001192",
            "20260602000456",
        }


def test_real_consolidated_source_cannot_replace_separate_request() -> None:
    with pytest.raises(ValueError, match="target"):
        select_candidate(
            request(datetime(2026, 11, 23, 0, tzinfo=UTC), "separate"),
            [candidate("correction", "consolidated")],
        )
