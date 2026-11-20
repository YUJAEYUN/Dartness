"""Regression for issue #32 closing while its completion checklist was unfinished."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_pr_policy import validate_pr_body


@pytest.mark.parametrize(
    "body",
    [
        "Closes #32",
        "Closes:#32",
        "fixes #32",
        "RESOLVED: #32",
        "close YUJAEYUN/Dartness#32",
        "Fixes https://github.com/YUJAEYUN/Dartness/issues/32",
    ],
)
def test_automatic_closure_is_rejected(body: str) -> None:
    with pytest.raises(ValueError, match="Refs"):
        validate_pr_body(body)


@pytest.mark.parametrize("body", ["Refs #32", "Related to #32", "Fix typo in docs", ""])
def test_reference_without_automatic_closure_is_allowed(body: str) -> None:
    validate_pr_body(body)


def test_ci_command_fails_on_automatic_closure(tmp_path: Path) -> None:
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"body": "Closes #32"}}))
    script = Path(__file__).resolve().parents[1] / "scripts/check_pr_policy.py"
    result = subprocess.run(
        [sys.executable, str(script), str(event)], capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "Refs" in result.stderr
