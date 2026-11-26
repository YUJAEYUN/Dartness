"""Read existing collection outputs without trusting summaries or fetching new data."""

import hashlib
import json
import re
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from dartness.cash_report_candidates import StoredCashReport
from dartness.correction_binding import CorrectionWebInputs
from dartness.dart_smoke import read_archive
from dartness.disclosure_list import Disclosure, ListRequest
from dartness.filing_history import FilingHistory, HistoryResponse
from dartness.latest_cash import BodyObservation, CorrectionPair


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise ValueError("collection_object_required")
    return dict(value)


def _array(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("collection_array_required")
    return list(value)


def _text(value: object, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value):
        raise ValueError("collection_text_required")
    return value


def _integer(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("collection_nonnegative_integer_required")
    return value


def _read(root: Path, name: str, limit: int) -> bytes:
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("collection_path_outside_root")
    with target.open("rb") as stream:
        payload = stream.read(limit + 1)
    if len(payload) > limit:
        raise ValueError("collection_file_too_large")
    return payload


def _json(path: Path) -> dict[str, object]:
    return _object(json.loads(_read(path.parent, path.name, 1024 * 1024)))


def load_history(root: Path, executed_at: datetime) -> tuple[FilingHistory, tuple[Disclosure, ...]]:
    manifest = _json(root / "manifest.json")
    if manifest.get("mode") != "filing_history" or manifest.get("complete") is not True:
        raise ValueError("complete_filing_history_required")
    r = _object(manifest.get("request"))
    request = ListRequest(
        date.fromisoformat(_text(r.get("start"))),
        date.fromisoformat(_text(r.get("end"))),
        _text(r.get("corp_code")),
        _text(r.get("corp_cls", ""), empty=True),
        _text(r.get("disclosure_type", ""), empty=True),
    )
    responses = []
    for value in _array(manifest.get("responses")):
        record = _object(value)
        params = _object(record.get("parameters"))
        responses.append(
            HistoryResponse(
                tuple((key, _text(v)) for key, v in params.items()),
                _read(root, _text(record.get("file")), 32 * 1024 * 1024),
                _text(record.get("response_sha256")),
            )
        )
    history = FilingHistory(
        request,
        tuple(responses),
        datetime.fromisoformat(_text(manifest.get("started_at"))),
        datetime.fromisoformat(_text(manifest.get("collected_at"))),
    )
    result = history.replay(executed_at)
    actual = [{**asdict(row), "filed_on": row.filed_on.isoformat()} for row in result.items]
    if (
        manifest.get("items") != actual
        or _integer(manifest.get("request_count")) != result.requests
    ):
        raise ValueError("history_summary_mismatch")
    return history, result.items


def _verified_archive(root: Path, filename: str, record: dict[str, object], digest: str) -> bytes:
    archive = _read(root, filename, 32 * 1024 * 1024)
    if hashlib.sha256(archive).hexdigest() != digest:
        raise ValueError("archive_hash_mismatch")
    members = read_archive(archive)
    declared: dict[str, dict[str, object]] = {}
    for value in _array(record.get("documents")):
        item = _object(value)
        name = _text(item.get("name"))
        if name in declared:
            raise ValueError("duplicate_member_declaration")
        declared[name] = item
    if set(declared) != set(members):
        raise ValueError("archive_member_set_mismatch")
    for name, payload in members.items():
        item = declared[name]
        if (
            _integer(item.get("bytes")) != len(payload)
            or item.get("sha256") != hashlib.sha256(payload).hexdigest()
        ):
            raise ValueError("archive_member_declaration_mismatch")
    return archive


def load_reports(
    roots: tuple[Path, ...], rows: tuple[Disclosure, ...]
) -> tuple[StoredCashReport, ...]:
    expected = {
        r.receipt: r
        for r in rows
        if any(k in r.report_name for k in ("사업보고서", "반기보고서", "분기보고서"))
    }
    loaded: dict[str, StoredCashReport] = {}
    for root in roots:
        manifest = _json(root / "manifest.json")
        exact = manifest.get("mode") == "exact_receipts"
        if exact:
            if manifest.get("complete") is not True:
                raise ValueError("complete_receipt_collection_required")
            records = _array(manifest.get("reports"))
        elif manifest.get("mode") in (None, "annual"):
            records = _array(manifest.get("companies"))
        else:
            raise ValueError("unsupported_source_collection_mode")
        if exact and not 1 <= len(records) <= 2:
            raise ValueError("invalid_collection_receipt_count")
        receipts = []
        for value in records:
            record = _object(value)
            if record.get("status") != "collected":
                raise ValueError("source_collection_incomplete")
            receipt = _text(record.get("receipt" if exact else "rcept_no"))
            if not re.fullmatch(r"[0-9]{14}", receipt) or receipt not in expected:
                raise ValueError("unexpected_report_receipt")
            if receipt in loaded:
                raise ValueError("duplicate_report_archive")
            row = expected[receipt]
            if record.get("dart_url") != row.source_url:
                raise ValueError("archive_source_url_mismatch")
            if exact:
                filename = receipt + "/document.zip"
                digest = _text(record.get("archive_sha256"))
            else:
                if (
                    record.get("corp_code") != row.corp_code
                    or record.get("stock_code") != row.stock_code
                ):
                    raise ValueError("annual_collection_company_mismatch")
                filename = row.stock_code + "/document.zip"
                digest = _text(record.get("zip_sha256"))
            archive = _verified_archive(root, filename, record, digest)
            members = read_archive(archive)
            main = receipt + ".xml"
            if main not in members:
                raise ValueError("main_document_missing")
            if exact and (
                record.get("main_document") != main
                or record.get("main_document_sha256") != hashlib.sha256(members[main]).hexdigest()
            ):
                raise ValueError("main_document_declaration_mismatch")
            loaded[receipt] = StoredCashReport(row, archive)
            receipts.append(receipt)
        if exact and (
            manifest.get("requested_receipts") != receipts
            or _integer(manifest.get("request_count")) != len(receipts)
        ):
            raise ValueError("receipt_summary_mismatch")
    if set(loaded) != set(expected):
        raise ValueError("periodic_archives_incomplete")
    return tuple(loaded[r.receipt] for r in rows if r.receipt in loaded)


def read_web_file(path: Path) -> bytes:
    return _read(path.parent, path.name, 2 * 1024 * 1024)


def load_body(receipt: str, path: Path, observed_at: datetime) -> BodyObservation:
    if not re.fullmatch(r"[0-9]{14}", receipt):
        raise ValueError("body_receipt_required")
    return BodyObservation(receipt, read_web_file(path), observed_at)


def load_correction_pair(path: Path) -> CorrectionPair:
    record = _json(path)
    original, correction = (
        _text(record.get("original_receipt")),
        _text(record.get("correction_receipt")),
    )
    if any(not re.fullmatch(r"[0-9]{14}", r) for r in (original, correction)):
        raise ValueError("correction_receipts_required")
    files = tuple(
        _read(path.parent, _text(record.get(field)), 2 * 1024 * 1024)
        for field in ("original_main", "correction_main", "errata_html")
    )
    web = CorrectionWebInputs(
        files[0],
        files[1],
        files[2],
        _text(record.get("errata_url")),
        datetime.fromisoformat(_text(record.get("observed_at"))),
    )
    return CorrectionPair(original, correction, web)
