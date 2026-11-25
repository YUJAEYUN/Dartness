"""Require a work briefing on feature and specification PRs (docs/briefings/index.md)."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Feature PRs change query code. Specification PRs change documents that define behavior.
FEATURE_PREFIXES = ("src/",)
SPEC_PATHS = (
    "docs/specs/requirements.md",
    "docs/specs/query-types.md",
    "docs/specs/common-query-contract.md",
    "docs/specs/disclosure-list.md",
    "docs/specs/listed-universe.md",
    "docs/specs/correction-evidence.md",
    "docs/specs/cash-query-contract.md",
    "docs/specs/cash-table-extraction.md",
    "docs/specs/amounts.md",
    "docs/specs/output-example.md",
)
# Keep legacy paths so deletion or migration cannot bypass briefing checks.
LEGACY_SPEC_PATHS = (
    "docs/requirements.md",
    "docs/query-types.md",
    "docs/common-query-contract.md",
    "docs/cash-query-contract.md",
    "docs/cash-table-extraction.md",
    "docs/amounts.md",
    "docs/output-example.md",
)


def briefing_required(changed: list[str]) -> bool:
    return any(
        path.startswith(FEATURE_PREFIXES) or path in (*SPEC_PATHS, *LEGACY_SPEC_PATHS)
        for path in changed
    )


def check(pr: int, changed: list[str], root: Path = ROOT) -> None:
    if not briefing_required(changed):
        return
    pattern = f"{pr:04d}-*.md"
    if not list((root / "docs" / "briefings").glob(pattern)):
        raise ValueError(
            f"기능·명세 PR에는 docs/briefings/{pattern} 브리핑이 필요합니다. "
            "PR을 연 뒤 docs/briefings/index.md 양식으로 작성해 같은 PR에 추가하세요."
        )


def changed_files(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    return [line for line in result.stdout.splitlines() if line]


def main() -> int:
    try:
        event = json.loads(Path(sys.argv[1]).read_text())
        pr = event.get("pull_request")
        if not isinstance(pr, dict):
            raise ValueError("pull_request 이벤트가 필요합니다")
        number, base, head = pr.get("number"), pr["base"]["sha"], pr["head"]["sha"]
        if not isinstance(number, int) or not isinstance(base, str) or not isinstance(head, str):
            raise ValueError("PR 번호와 기준 커밋을 확인할 수 없습니다")
        check(number, changed_files(base, head))
    except (ValueError, KeyError, TypeError, IndexError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        print(f"변경 파일을 확인하지 못했습니다: {error.stderr.strip()}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
