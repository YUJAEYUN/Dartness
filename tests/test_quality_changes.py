"""Quality bypasses must be visible against the base, including moves and normal test fixtures."""

import subprocess
from pathlib import Path

import pytest

from scripts.check_quality_changes import Marker, added, changed_pairs, compare, python_markers


def test_strings_and_ordinary_comments_are_not_suppressions() -> None:
    text = 'value = "# type: ignore[misc]"\n# Docs mention noqa without enabling it.\n'
    assert python_markers(text) == []


@pytest.mark.parametrize(
    "directive",
    ["type: ignore[misc]", "noqa: BLE001", "ruff: noqa", "fmt: off", "mypy: ignore-errors"],
)
def test_real_comments_are_detected(directive: str) -> None:
    result = python_markers(f"value = 1  # {directive}\n")
    assert len(result) == 1
    assert result[0].kind == "검사 무시"


@pytest.mark.parametrize(
    "code",
    [
        "import pytest as p\np.skip('reason')",
        "from pytest import mark as m\n@m.skipif(True, reason='x')\ndef test_x(): pass",
        "from pytest import importorskip as optional\noptional('missing')",
        "from unittest import skip as disabled\n@disabled('reason')\ndef test_x(): pass",
        "import pytest\npytestmark = pytest.mark.xfail",
    ],
)
def test_test_disabling_aliases_are_detected(code: str) -> None:
    assert [m.kind for m in python_markers(code)] == ["테스트 비활성"]


def test_explicit_any_is_detected_but_not_builtin_any() -> None:
    result = python_markers("from typing import Any as Unknown\nx: Unknown = 1\nany([True])\n")
    assert [m.kind for m in result] == ["명시적 Any"]


def test_existing_or_removed_markers_do_not_fail_but_duplicates_and_changes_do() -> None:
    old = python_markers("x = 1 # type: ignore[misc]\n")
    moved = python_markers("\n\nx = 1 # type: ignore[misc]\n")
    assert added(old, moved) == []
    assert added(old, []) == []
    assert len(added(old, old + old)) == 1
    assert len(added(old, python_markers("x = 2 # type: ignore[misc]\n"))) == 1


def test_invalid_python_fails_instead_of_appearing_clean() -> None:
    with pytest.raises(SyntaxError):
        python_markers("def broken(")


def run_git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


def commit(root: Path) -> str:
    run_git(root, "add", ".")
    run_git(
        root,
        "-c",
        "user.name=Guard test",
        "-c",
        "user.email=guard@example.invalid",
        "commit",
        "-qm",
        "case",
    )
    return run_git(root, "rev-parse", "HEAD")


def test_git_comparison_keeps_moved_exceptions_and_finds_new_ones(tmp_path: Path) -> None:
    run_git(tmp_path, "init", "-q")
    (tmp_path / "tests").mkdir()
    old = tmp_path / "tests/original.py"
    old.write_text(
        "x = 1 # type: ignore[misc]\n" + "\n".join(f"v{i} = {i}" for i in range(15)) + "\n"
    )
    base = commit(tmp_path)
    new = tmp_path / "tests/moved.py"
    old.rename(new)
    new.write_text(new.read_text() + "y = 1 # type: ignore[misc]\n")
    (tmp_path / "pyproject.toml").write_text("# setting change\n")
    (tmp_path / "dashboard").mkdir()
    (tmp_path / "dashboard/vitest.config.ts").write_text(
        "export default { test: { exclude: [] } };\n"
    )
    head = commit(tmp_path)
    assert ("tests/original.py", "tests/moved.py") in changed_pairs(base, head, tmp_path)
    findings, settings = compare(base, head, tmp_path)
    assert [(path, marker.kind) for path, marker in findings] == [("tests/moved.py", "검사 무시")]
    assert settings == ["dashboard/vitest.config.ts", "pyproject.toml"]


def test_marker_counts_ignore_line_numbers() -> None:
    assert added([Marker("x", 1, "same")], [Marker("x", 20, "same")]) == []


def test_ci_entrypoint_reports_and_fails_then_ignores_uncommitted_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import sys

    from scripts.check_quality_changes import main

    run_git(tmp_path, "init", "-q")
    (tmp_path / "tests").mkdir()
    file = tmp_path / "tests/test_case.py"
    file.write_text("value = 1\n")
    base = commit(tmp_path)
    file.write_text("value = 1 # type: ignore[misc]\n")
    head = commit(tmp_path)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr(sys, "argv", ["check", "--base", base, "--head", head])
    assert main(tmp_path) == 1
    assert "tests/test_case.py:1" in summary.read_text()
    assert "새 구문 1건" in capsys.readouterr().out
    file.write_text("not valid python !\n")
    assert main(tmp_path) == 1  # The committed head is inspected, not workspace edits.
    monkeypatch.setattr(sys, "argv", ["check", "--base", base, "--head", base])
    assert main(tmp_path) == 0


def test_ci_entrypoint_fails_closed_for_bad_git_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import sys

    from scripts.check_quality_changes import main

    run_git(tmp_path, "init", "-q")
    monkeypatch.setattr(sys, "argv", ["check", "--base", "missing", "--head", "missing"])
    assert main(tmp_path) == 2
    assert "정상으로 처리하지 않습니다" in capsys.readouterr().err


def test_briefing_checker_change_is_reported_as_quality_configuration() -> None:
    from scripts.check_quality_changes import settings_changed

    assert settings_changed("scripts/check_briefing_required.py")
    assert not settings_changed("src/dartness/disclosure_list.py")
