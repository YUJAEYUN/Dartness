"""Manual runner configuration and exports use fixed sources; no real DART key or calls."""

import json
from pathlib import Path

import pytest
from test_universe_cash import Sources

from dartness import universe_cash_runner as runner


def config() -> dict[str, object]:
    return {
        "mode": "latest",
        "max_age_months": 12,
        "scope": "standalone",
        "minimum_krw": "600",
        "max_api_requests": 20,
        "max_web_requests": 10,
        "max_companies": 1,
        "max_reports_per_company": 8,
        "basis_by_corp": {"00000001": "separate"},
        "target_codes": ["00000001"],
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("minimum_krw", 600.0),
        ("minimum_krw", "500억원"),
        ("max_api_requests", True),
        ("target_codes", []),
        ("scope", "consolidated"),
    ],
)
def test_invalid_config_is_rejected_without_network(field: str, value: object) -> None:
    data = config()
    data[field] = value
    with pytest.raises(ValueError):
        runner.parse_plan(json.dumps(data), "2026-11-01")


def test_runner_exports_partial_scope_and_omits_profile_contact_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = Sources()
    target = tmp_path / "run"
    key = "A" * 40

    def api(endpoint: str, params: dict[str, str], credential: str) -> bytes:
        assert credential == key
        payload = source.fetch(endpoint, params)
        if endpoint == "company.json":
            data = json.loads(payload)
            data.update(ceo_nm="not-retained-contact", phn_no="not-retained-phone")
            return json.dumps(data).encode()
        return payload

    monkeypatch.setattr(runner, "fetch_bytes", api)
    monkeypatch.setattr(runner, "fetch_dart_viewer", source.web)
    monkeypatch.setenv("DART_API_KEY", key)
    monkeypatch.setenv("OUTPUT_DIR", str(target))
    monkeypatch.setenv("UNIVERSE_CASH_CONFIG", json.dumps(config()))
    monkeypatch.setenv("HISTORY_START", source.today.replace(day=1).isoformat())
    assert runner.main() == 0
    report = json.loads((target / "report.json").read_text())
    assert len(report["survey"]["companies"]) == 3
    assert report["survey"]["counts"]["not_processed"] == 2
    assert report["survey"]["all_values_verified"] is False
    assert (target / "matches.xlsx").exists()
    for path in target.rglob("*"):
        if path.is_file():
            assert b"not-retained-contact" not in path.read_bytes()
            assert b"not-retained-phone" not in path.read_bytes()
            assert key.encode() not in path.read_bytes()
    before = len(source.calls)
    assert runner.main() == 1 and len(source.calls) == before
    assert key not in capsys.readouterr().out
