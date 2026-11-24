"""One open PR per issue, so agents do not work on the same issue
(docs/guides/development-workflow.md).

A PR takes on the issue named by its single `Refs #number` line. If an earlier open PR already
takes on the same issue, this PR fails. Only PRs that exist are seen: work done before a PR is
opened cannot be detected, which is why agents open a draft PR as soon as they start.
"""

import json
import os
import re
import sys
import urllib.request
from collections.abc import Callable, Iterable
from pathlib import Path

from scripts.check_briefing_required import briefing_required, changed_files

_REFS = re.compile(r"(?<![\w/])Refs\s+#([0-9]+)\b", re.IGNORECASE)

type OpenPr = tuple[int, str]
type FetchPage = Callable[[int], list[dict[str, object]]]


def claimed_issues(body: str) -> set[int]:
    return {int(number) for number in _REFS.findall(body)}


def check(number: int, body: str, required: bool, open_prs: Iterable[OpenPr]) -> None:
    issues = claimed_issues(body)
    if len(issues) > 1:
        found = ", ".join(f"#{issue}" for issue in sorted(issues))
        raise ValueError(
            f"PR 하나는 이슈 하나만 맡습니다. Refs가 여러 개입니다: {found}. "
            "맡은 이슈만 `Refs #번호`로 쓰고, 관련 이슈는 '관련: #번호'처럼 적으세요."
        )
    if not issues:
        if required:
            raise ValueError("기능·명세 PR은 본문에 `Refs #번호`로 맡은 이슈를 하나 적어야 합니다.")
        return
    (issue,) = issues
    earlier = sorted(
        other
        for other, other_body in open_prs
        if other < number and issue in claimed_issues(other_body)
    )
    if earlier:
        raise ValueError(
            f"이슈 #{issue}는 먼저 열린 PR #{earlier[0]}이 맡고 있습니다. "
            "그 PR을 이어받거나, 닫은 뒤 다시 실행하거나, 다른 이슈로 나누세요."
        )


def open_prs(fetch_page: FetchPage) -> list[OpenPr]:
    result: list[OpenPr] = []
    page = 1
    while True:
        rows = fetch_page(page)
        for row in rows:
            number, body = row.get("number"), row.get("body") or ""
            if not isinstance(number, int) or not isinstance(body, str):
                raise ValueError("열린 PR 목록을 해석할 수 없습니다")
            result.append((number, body))
        if len(rows) < 100:
            return result
        page += 1


def github_page(repository: str, token: str) -> FetchPage:
    def fetch(page: int) -> list[dict[str, object]]:
        url = f"https://api.github.com/repos/{repository}/pulls?state=open&per_page=100&page={page}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            rows: object = json.load(response)
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError("열린 PR 목록을 해석할 수 없습니다")
        return rows

    return fetch


def main() -> int:
    try:
        event = json.loads(Path(sys.argv[1]).read_text())
        pr = event.get("pull_request")
        if not isinstance(pr, dict):
            raise ValueError("pull_request 이벤트가 필요합니다")
        number, body = pr.get("number"), pr.get("body") or ""
        if not isinstance(number, int) or not isinstance(body, str):
            raise ValueError("PR 번호와 본문을 확인할 수 없습니다")
        required = briefing_required(changed_files(pr["base"]["sha"], pr["head"]["sha"]))
        fetch = github_page(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"])
        check(number, body, required, open_prs(fetch))
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
