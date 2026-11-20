"""Prevent PR descriptions from closing issues before post-merge checks."""

import json
import re
import sys
from pathlib import Path

_AUTOCLOSE = re.compile(
    r"\b(?:close[sd]?|fix(?:es|ed)?|resolve[sd]?)(?:\s*:\s*|\s+)"
    r"(?:\#[0-9]+|[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\#[0-9]+|"
    r"https://github\.com/[^/\s]+/[^/\s]+/issues/[0-9]+)",
    re.IGNORECASE,
)


def validate_pr_body(body: str) -> None:
    if _AUTOCLOSE.search(body):
        raise ValueError(
            "PR 자동 종료 문구를 제거하고 Refs로 연결하세요. "
            "이슈는 병합 후 완료 조건과 체크리스트를 확인한 뒤 별도로 닫습니다."
        )


def main() -> int:
    try:
        event = json.loads(Path(sys.argv[1]).read_text())
        pr = event.get("pull_request")
        if not isinstance(pr, dict):
            raise ValueError("pull_request 이벤트가 필요합니다")
        body = pr.get("body") or ""
        if not isinstance(body, str):
            raise ValueError("PR 본문을 확인할 수 없습니다")
        validate_pr_body(body)
    except (ValueError, IndexError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
