"""Cross-check literal official web evidence, without selecting or binding full documents."""

import hashlib
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from dartness.correction_evidence import ViewerRelation
from dartness.correction_html import BodyEntry, ErrataObservation, read_body_history, read_errata
from dartness.dart_viewer import viewer_section_url
from dartness.disclosure_list import Disclosure


@dataclass(frozen=True)
class CorrectionWebObservation:
    corp_code: str
    original_history: tuple[BodyEntry, ...]
    correction_history: tuple[BodyEntry, ...]
    errata: ErrataObservation
    viewer_relation: ViewerRelation
    correction_viewer_sha256: str
    errata_url: str
    errata_response_sha256: str
    observed_at: datetime

    def to_dict(self) -> dict[str, object]:
        def entries(history: tuple[BodyEntry, ...]) -> list[dict[str, object]]:
            return [{**asdict(entry), "filed_on": entry.filed_on.isoformat()} for entry in history]

        return {
            "status": "web_evidence_observed",
            "corp_code": self.corp_code,
            "original_receipt": self.viewer_relation.original_receipt,
            "correction_receipt": self.viewer_relation.correction_receipt,
            "original_history": entries(self.original_history),
            "correction_history": entries(self.correction_history),
            "original_viewer_url": self.viewer_relation.source_url,
            "original_viewer_response_sha256": self.viewer_relation.response_sha256,
            "correction_viewer_response_sha256": self.correction_viewer_sha256,
            "correction_viewer_url": (
                "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="
                + self.viewer_relation.correction_receipt
            ),
            "errata_url": self.errata_url,
            "errata_response_sha256": self.errata_response_sha256,
            "first_submitted_on": self.errata.first_submitted_on.isoformat(),
            "corrected_on": self.errata.corrected_on.isoformat(),
            "report_kind": self.errata.report_kind,
            "changes": [list(row) for row in self.errata.changes],
            "first_submission_locator": self.errata.first_submission_locator,
            "observed_at": self.observed_at.isoformat(),
            "full_document_binding_verified": False,
            "cash_impact_verified": False,
            "latest_correction_verified": False,
            "selected_receipt": None,
        }


def _validate_metadata(original: Disclosure, correction: Disclosure, observed_at: datetime) -> None:
    if not isinstance(observed_at, datetime) or observed_at.utcoffset() is None:
        raise ValueError("aware_observation_time_required")
    if not isinstance(original, Disclosure) or not isinstance(correction, Disclosure):
        raise ValueError("two_disclosures_required")
    if not isinstance(original.corp_code, str) or not re.fullmatch(r"[0-9]{8}", original.corp_code):
        raise ValueError("eight_digit_company_required")
    if original.corp_code != correction.corp_code:
        raise ValueError("same_company_required")
    for disclosure in (original, correction):
        if not isinstance(disclosure.receipt, str) or not re.fullmatch(
            r"[0-9]{14}", disclosure.receipt
        ):
            raise ValueError("fourteen_digit_receipt_required")
    if original.receipt == correction.receipt:
        raise ValueError("distinct_receipts_required")


def observe_correction_web(
    original: Disclosure,
    correction: Disclosure,
    original_main: bytes,
    correction_main: bytes,
    errata_html: bytes,
    observed_at: datetime,
    *,
    errata_url: str,
) -> CorrectionWebObservation:
    _validate_metadata(original, correction, observed_at)
    a = read_body_history(original_main, original.corp_code, original.receipt)
    b = read_body_history(correction_main, correction.corp_code, correction.receipt)
    if set(a) != set(b):
        raise ValueError("body_history_conflict")
    wanted = {original.receipt: original, correction.receipt: correction}
    for receipt, disclosure in wanted.items():
        matches = [entry for entry in a if entry.receipt == receipt]
        if len(matches) != 1 or matches[0].filed_on != disclosure.filed_on:
            raise ValueError("body_history_conflict")
        if matches[0].is_correction != (receipt == correction.receipt):
            raise ValueError("body_correction_marker_mismatch")
    expected_url = viewer_section_url(
        correction_main, correction.receipt, correction.corp_code, "정정신고(보고)"
    )
    if expected_url is None or errata_url != expected_url:
        raise ValueError("errata_location_mismatch")
    errata = read_errata(errata_html)
    if errata.first_submitted_on != original.filed_on:
        raise ValueError("first_submission_mismatch")
    if errata.corrected_on != correction.filed_on:
        raise ValueError("correction_date_mismatch")
    if errata.report_kind != "사업보고서" or any(
        entry.report_kind != errata.report_kind for entry in a
    ):
        raise ValueError("report_kind_mismatch")
    if max(entry.filed_on for entry in a) > observed_at.astimezone(ZoneInfo("Asia/Seoul")).date():
        raise ValueError("history_after_observation_time")
    relation = ViewerRelation(
        original.receipt,
        correction.receipt,
        original.source_url,
        hashlib.sha256(original_main).hexdigest(),
        "select#family / 본문 관계 목록",
        "\n".join(f"{entry.receipt}: {entry.label}" for entry in a),
    )
    return CorrectionWebObservation(
        original.corp_code,
        a,
        b,
        errata,
        relation,
        hashlib.sha256(correction_main).hexdigest(),
        errata_url,
        hashlib.sha256(errata_html).hexdigest(),
        observed_at,
    )


def collect_correction_web(
    original: Disclosure,
    correction: Disclosure,
    fetch: Callable[[str], bytes],
    observed_at: datetime,
) -> CorrectionWebObservation:
    """At most three sequential official web requests; no API key, version choice or retries."""
    _validate_metadata(original, correction, observed_at)
    original_main = fetch(original.source_url)
    correction_main = fetch(correction.source_url)
    # Validate both histories before fetching an errata location from the correction TOC.
    read_body_history(original_main, original.corp_code, original.receipt)
    read_body_history(correction_main, correction.corp_code, correction.receipt)
    errata_url = viewer_section_url(
        correction_main, correction.receipt, correction.corp_code, "정정신고(보고)"
    )
    if errata_url is None:
        raise ValueError("errata_location_required")
    return observe_correction_web(
        original,
        correction,
        original_main,
        correction_main,
        fetch(errata_url),
        observed_at,
        errata_url=errata_url,
    )
