"""Mechanical checks for references written in human-readable docs.

These checks only confirm that referenced paths and rule IDs exist and that
docs/work-state.md keeps its agreed shape. They do not establish that the
prose and the implementation mean the same thing.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Repository paths written in prose, e.g. src/dartness/amounts.py or dashboard/dist/.
PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_/.-])((?:src|tests|dashboard|docs|\.github)/[A-Za-z0-9_./-]*[A-Za-z0-9_/])"
)

# Build outputs that exist only after a local or CI build (see .gitignore files).
GENERATED_PATHS = {"dashboard/dist"}

RULE_ID_PATTERN = re.compile(r"\b[A-Z]{2,}-\d{3}\b")
NON_RULE_TOKENS = {"SHA-256"}
RULE_DEFINITION_PATTERN = re.compile(r'<a id="([a-z]+-\d{3})"></a>\s*\n규칙 \*\*([A-Z]+-\d{3})\*\*')

WORK_STATE_HEADINGS = [
    "## 현재 상태",
    "## 진행 중인 작업",
    "## 다음에 정할 것",
    "## 알려진 한계",
]


def _documents() -> list[Path]:
    return [ROOT / "AGENTS.md", ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]


def _referenced_paths(text: str) -> set[str]:
    return {match.rstrip("/") for match in PATH_PATTERN.findall(text)}


def test_path_pattern_examples() -> None:
    text = "구현은 src/dartness/amounts.py, 결과물은 dashboard/dist/입니다. ../amounts.md 제외"
    assert _referenced_paths(text) == {"src/dartness/amounts.py", "dashboard/dist"}


def test_documented_repository_paths_exist() -> None:
    missing = [
        f"{document.relative_to(ROOT)}: {path}"
        for document in _documents()
        for path in sorted(_referenced_paths(document.read_text(encoding="utf-8")))
        if path not in GENERATED_PATHS and not (ROOT / path).exists()
    ]
    assert missing == []


def _defined_rule_ids() -> set[str]:
    text = (ROOT / "docs" / "consistency.md").read_text(encoding="utf-8")
    definitions = RULE_DEFINITION_PATTERN.findall(text)
    assert all(anchor == rule.lower() for anchor, rule in definitions)
    return {rule for _, rule in definitions}


def test_used_rule_ids_are_defined() -> None:
    defined = _defined_rule_ids()
    assert "AMOUNT-001" in defined
    sources = [*_documents(), *sorted((ROOT / "src").rglob("*.py"))]
    sources += sorted((ROOT / "tests").glob("*.py"))
    undefined = [
        f"{source.relative_to(ROOT)}: {rule}"
        for source in sources
        for rule in sorted(set(RULE_ID_PATTERN.findall(source.read_text(encoding="utf-8"))))
        if rule not in NON_RULE_TOKENS and rule not in defined
    ]
    assert undefined == []


def test_work_state_keeps_current_state_format() -> None:
    text = (ROOT / "docs" / "work-state.md").read_text(encoding="utf-8")
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings == WORK_STATE_HEADINGS
