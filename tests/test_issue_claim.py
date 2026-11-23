"""One open PR per issue (issue #55, docs/development-workflow.md)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_issue_claim import check, claimed_issues, open_prs

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("body", "issues"),
    [
        ("Refs #55", {55}),
        ("refs #55\n\n관련: #31", {55}),
        ("Refs #55\nRefs #55", {55}),
        ("Refs #31\nRefs #55", {31, 55}),
        ("관련: #31", set()),
        ("Refs YUJAEYUN/Dartness#55", set()),
        ("Prefs #55", set()),
        ("", set()),
    ],
)
def test_claimed_issues_reads_only_refs_lines(body: str, issues: set[int]) -> None:
    assert claimed_issues(body) == issues


def test_pr_without_other_claims_passes() -> None:
    check(60, "Refs #55", True, [(60, "Refs #55"), (59, "Refs #56"), (58, "관련: #55")])


def test_later_pr_on_the_same_issue_fails_and_names_the_earlier_pr() -> None:
    with pytest.raises(ValueError, match="이슈 #55는 먼저 열린 PR #58"):
        check(61, "Refs #55", False, [(58, "Refs #55"), (60, "Refs #55"), (61, "Refs #55")])


def test_earlier_pr_keeps_the_issue_when_a_later_pr_claims_it() -> None:
    # Otherwise both PRs would be blocked once the earlier one re-runs its checks.
    check(58, "Refs #55", True, [(58, "Refs #55"), (61, "Refs #55")])


def test_feature_or_specification_pr_must_name_an_issue() -> None:
    with pytest.raises(ValueError, match="맡은 이슈를 하나"):
        check(60, "관련: #31", True, [])


def test_other_pr_may_name_no_issue() -> None:
    check(60, "문서 오타 수정", False, [(58, "Refs #55")])


def test_pr_may_not_claim_two_issues() -> None:
    with pytest.raises(ValueError, match="Refs가 여러 개입니다: #31, #55"):
        check(60, "Refs #31\nRefs #55", False, [])


def test_open_prs_reads_every_page() -> None:
    pages: dict[int, list[dict[str, object]]] = {
        1: [{"number": n, "body": None} for n in range(100)],
        2: [{"number": 100, "body": "x"}],
    }
    result = open_prs(lambda page: pages.get(page, []))
    assert len(result) == 101 and result[0] == (0, "") and result[-1] == (100, "x")


def test_open_prs_rejects_unexpected_rows() -> None:
    with pytest.raises(ValueError, match="해석할 수 없습니다"):
        open_prs(lambda page: [{"number": "1", "body": ""}])


def test_cli_fails_without_a_pull_request_event(tmp_path: Path) -> None:
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"push": {}}))
    result = subprocess.run(
        [sys.executable, "-m", "scripts.check_issue_claim", str(event)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 1 and "pull_request" in result.stderr
