"""Exercise the configured Ruff rules with real violations, not duplicated implementations."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def lint(code: str) -> tuple[int, set[str]]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--config",
            str(ROOT / "pyproject.toml"),
            "--stdin-filename",
            "src/example.py",
            "--output-format",
            "json",
            "-",
        ],
        input=code,
        text=True,
        capture_output=True,
        cwd=ROOT,
    )
    assert result.returncode in (0, 1), result.stderr
    return result.returncode, {item["code"] for item in json.loads(result.stdout)}


@pytest.mark.parametrize(
    ("rule", "code"),
    [
        ("BLE001", "try:\n    int('x')\nexcept Exception:\n    print('ok')\n"),
        ("S110", "try:\n    int('x')\nexcept ValueError:\n    pass\n"),
        (
            "S112",
            "for x in []:\n    try:\n        int(x)\n    except ValueError:\n        continue\n",
        ),
        ("PGH003", "x = 1  # type: ignore\n"),
        ("PGH004", "print('ok')  # noqa\n"),
        ("RUF100", "x = 1  # noqa: F821\n"),
    ],
)
def test_enabled_rule_rejects_real_violation(rule: str, code: str) -> None:
    status, rules = lint(code)
    assert status == 1
    assert rule in rules


def test_specific_error_handling_remains_valid() -> None:
    assert lint("try:\n    int('x')\nexcept ValueError:\n    print('invalid number')\n") == (
        0,
        set(),
    )
