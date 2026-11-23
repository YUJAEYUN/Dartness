"""Feature and specification PRs must carry a work briefing (docs/briefings/index.md)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_briefing_required import SPEC_PATHS, briefing_required, check

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "changed",
    [["src/dartness/cash_table.py"], ["docs/query-types.md"], ["README.md", "docs/amounts.md"]],
)
def test_feature_or_specification_changes_require_briefing(changed: list[str]) -> None:
    assert briefing_required(changed)


@pytest.mark.parametrize(
    "changed",
    [[], ["docs/ci.md"], ["tests/test_amounts.py"], ["dashboard/src/App.tsx"], ["docs/src/x.md"]],
)
def test_other_changes_do_not_require_briefing(changed: list[str]) -> None:
    assert not briefing_required(changed)


def test_missing_briefing_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "docs" / "briefings").mkdir(parents=True)
    with pytest.raises(ValueError, match="docs/briefings/0040-"):
        check(40, ["src/dartness/amounts.py"], tmp_path)


def test_matching_briefing_is_accepted(tmp_path: Path) -> None:
    folder = tmp_path / "docs" / "briefings"
    folder.mkdir(parents=True)
    (folder / "0040-amounts.md").write_text("")
    check(40, ["src/dartness/amounts.py"], tmp_path)
    with pytest.raises(ValueError):
        check(41, ["src/dartness/amounts.py"], tmp_path)


def test_specification_paths_exist_and_are_documented() -> None:
    index = (ROOT / "docs" / "briefings" / "index.md").read_text(encoding="utf-8")
    for path in SPEC_PATHS:
        assert (ROOT / path).exists(), path
        assert path in index, path


def test_ci_command_reads_the_pull_request_event(tmp_path: Path) -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=ROOT
    ).stdout.strip()
    event = tmp_path / "event.json"
    script = ROOT / "scripts" / "check_briefing_required.py"
    pull = {"number": 9999, "base": {"sha": head}, "head": {"sha": head}}
    event.write_text(json.dumps({"pull_request": pull}))
    ok = subprocess.run([sys.executable, str(script), str(event)], capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr
    event.write_text(json.dumps({"pull_request": {"number": 9999}}))
    bad = subprocess.run([sys.executable, str(script), str(event)], capture_output=True, text=True)
    assert bad.returncode == 1
