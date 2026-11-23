"""Mechanical checks for references written in human-readable docs.

These checks confirm that referenced paths and rule IDs exist, that every rule ID
has an example or test, that every documented example is executed by a test, and
that docs/work-state.md keeps its agreed shape. They do not establish that the
prose and the implementation mean the same thing.
"""

import re
from pathlib import Path

from doc_examples import all_examples

ROOT = Path(__file__).resolve().parents[1]

# Repository paths written in prose, e.g. src/dartness/amounts.py or dashboard/dist/.
PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_/.-])((?:src|tests|dashboard|docs|\.github)/[A-Za-z0-9_./-]*[A-Za-z0-9_/])"
)

# Build outputs that exist only after a local or CI build (see .gitignore files).
GENERATED_PATHS = {"dashboard/dist"}

RULE_ID_PATTERN = re.compile(r"\b[A-Z]{2,}-\d{3}\b")
NON_RULE_TOKENS = {"SHA-256"}
RULE_DEFINITION_PATTERN = re.compile(
    r'<a id="([a-z]+-\d{3})"></a>\s*\n규칙 \*\*([A-Z]+-\d{3})\*\*( \(미구현\))?'
)

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


def _rule_definitions() -> dict[str, bool]:
    """Map each defined rule ID to whether it is marked unimplemented."""
    text = (ROOT / "docs" / "consistency.md").read_text(encoding="utf-8")
    definitions = RULE_DEFINITION_PATTERN.findall(text)
    assert all(anchor == rule.lower() for anchor, rule, _ in definitions)
    return {rule: bool(unimplemented) for _, rule, unimplemented in definitions}


def _defined_rule_ids() -> set[str]:
    return set(_rule_definitions())


def _test_sources() -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "tests").glob("test_*.py"))
        if path.name != Path(__file__).name
    }


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


def test_documented_examples_are_executed_by_tests() -> None:
    sources = "\n".join(_test_sources().values())
    blocks = sorted({example.block for example in all_examples()})
    assert blocks, "docs/amounts.md and docs/cash-query-contract.md hold examples"
    unread = [block for block in blocks if f'load_examples("{block}")' not in sources]
    assert unread == []


def test_example_rules_are_defined() -> None:
    defined = _defined_rule_ids()
    undefined = [
        f"{example.document} {example.id}: {example.rule}"
        for example in all_examples()
        if example.rule is not None and example.rule not in defined
    ]
    assert undefined == []


def test_implemented_rules_have_an_example_or_test() -> None:
    covered = {example.rule for example in all_examples() if example.rule is not None}
    sources = "\n".join(_test_sources().values())
    uncovered = [
        rule
        for rule, unimplemented in sorted(_rule_definitions().items())
        if not unimplemented and rule not in covered and rule not in sources
    ]
    assert uncovered == []


STATUS_CLASSES = {"구현": "done", "일부": "partial", "미구현": "todo"}


def _status_table(text: str, marker: str) -> list[list[str]]:
    lines = text.split(f"<!-- system-status: {marker} -->\n", 1)[1].splitlines()
    rows = []
    for line in lines[2:]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    assert rows, marker
    return rows


def test_system_status_map_matches_stage_table() -> None:
    text = (ROOT / "docs" / "system-status.md").read_text(encoding="utf-8")
    table = {row[0]: STATUS_CLASSES[row[2]] for row in _status_table(text, "stages")}
    drawn: dict[str, str] = {}
    for ids, css in re.findall(r"^\s*class ([A-Z,]+) (\w+)$", text, re.MULTILINE):
        for node in ids.split(","):
            assert node not in drawn, f"{node} colored twice"
            drawn[node] = css
    assert drawn == table


def test_system_status_lists_every_rule() -> None:
    text = (ROOT / "docs" / "system-status.md").read_text(encoding="utf-8")
    listed = {row[0] for row in _status_table(text, "rules")}
    assert listed == _defined_rule_ids()


BRIEFING_HEADINGS = [
    "## 한 줄 요약",
    "## 지도에서의 위치",
    "## 무엇이 달라졌나",
    "## 누가 무엇을 정했나",
    "## 확인해 주세요",
    "## 확인한 것과 못 한 것",
    "## 근거",
]
BRIEFING_META = re.compile(
    r"\A---\npr: (\d+)\nissue: (\d+|null)\ndate: (\d{4}-\d{2}-\d{2})\n"
    r"stages: \[([A-Z, ]*)\]\n---\n"
)


def _briefings() -> list[Path]:
    paths = sorted((ROOT / "docs" / "briefings").glob("[0-9][0-9][0-9][0-9]-*.md"))
    assert paths, "docs/briefings holds at least one briefing"
    return paths


def test_briefings_keep_the_agreed_format() -> None:
    status = (ROOT / "docs" / "system-status.md").read_text(encoding="utf-8")
    stage_ids = {row[0] for row in _status_table(status, "stages")}
    for path in _briefings():
        text = path.read_text(encoding="utf-8")
        meta = BRIEFING_META.match(text)
        assert meta, f"{path.name}: metadata"
        pr, _, _, stages_text = meta.groups()
        assert path.name.startswith(f"{int(pr):04d}-"), f"{path.name}: file name and pr"
        stages = {stage.strip() for stage in stages_text.split(",") if stage.strip()}
        assert stages <= stage_ids, f"{path.name}: unknown stages {stages - stage_ids}"
        headings = [line for line in text.splitlines() if line.startswith("## ")]
        assert headings == BRIEFING_HEADINGS, f"{path.name}: headings"
        highlighted = {
            node
            for ids in re.findall(r"^\s*class ([A-Z,]+) changed$", text, re.MULTILINE)
            for node in ids.split(",")
        }
        assert highlighted == stages, f"{path.name}: map highlight and stages"


def test_briefing_index_lists_every_briefing() -> None:
    index = (ROOT / "docs" / "briefings" / "index.md").read_text(encoding="utf-8")
    missing = [path.name for path in _briefings() if f"]({path.name})" not in index]
    assert missing == []
