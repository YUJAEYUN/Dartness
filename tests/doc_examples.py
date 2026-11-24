"""Load executable examples written in docs/ (rules: docs/guides/testing.md#doc-examples).

Expected values are written by people from specifications or source documents.
Never regenerate them from implementation output.
"""

import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, is_dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {"synthetic", "real-dev", "modified"}
_BLOCK = re.compile(r"<!-- dartness-example: ([a-z0-9-]+) -->\s*\n```json\n(.*?)\n```", re.DOTALL)
_FIELDS = {"id", "rule", "source", "input", "expect"}


@dataclass(frozen=True)
class DocExample:
    block: str
    document: str
    id: str
    source: str
    input: dict[str, Any]
    expect: dict[str, Any]
    rule: str | None = None


def _parse(block: str, document: str, row: object) -> DocExample:
    where = f"{document} [{block}]"
    if not isinstance(row, dict) or not set(row) <= _FIELDS:
        raise ValueError(f"{where}: rows are objects with only {sorted(_FIELDS)}")
    example_id, source = row.get("id"), row.get("source")
    data, expect, rule = row.get("input"), row.get("expect"), row.get("rule")
    if not isinstance(example_id, str) or not example_id:
        raise ValueError(f"{where}: id required")
    if source not in SOURCES:
        raise ValueError(f"{where} {example_id}: source must be one of {sorted(SOURCES)}")
    if not isinstance(data, dict) or not isinstance(expect, dict) or not expect:
        raise ValueError(f"{where} {example_id}: input and nonempty expect objects required")
    if rule is not None and not isinstance(rule, str):
        raise ValueError(f"{where} {example_id}: rule must be text")
    assert isinstance(source, str)
    return DocExample(block, document, example_id, source, data, expect, rule)


def all_examples() -> list[DocExample]:
    examples: list[DocExample] = []
    blocks: set[str] = set()
    for path in sorted((ROOT / "docs").rglob("*.md")):
        document = str(path.relative_to(ROOT))
        for block, body in _BLOCK.findall(path.read_text(encoding="utf-8")):
            if block in blocks:
                raise ValueError(f"{document}: duplicate example block {block}")
            blocks.add(block)
            rows = json.loads(body)
            if not isinstance(rows, list) or not rows:
                raise ValueError(f"{document} [{block}]: nonempty JSON list required")
            examples.extend(_parse(block, document, row) for row in rows)
    ids = [example.id for example in examples]
    duplicates = sorted({example_id for example_id in ids if ids.count(example_id) > 1})
    if duplicates:
        raise ValueError(f"duplicate example ids: {duplicates}")
    return examples


def load_examples(block: str) -> list[DocExample]:
    examples = [example for example in all_examples() if example.block == block]
    if not examples:
        raise ValueError(f"no documented examples named {block}")
    return examples


def check_example(example: DocExample, run: Callable[[dict[str, Any]], object]) -> None:
    """Compare every expected field. A null expectation means the field must be absent.

    An error expectation may add "message", a text the raised error must contain.
    """
    label = f"{example.document} {example.id}"
    expected_error = example.expect.get("error")
    if expected_error is not None:
        try:
            run(example.input)
        except Exception as error:  # noqa: BLE001 - the expected class is compared below.
            assert type(error).__name__ == expected_error, label
            assert str(example.expect.get("message", "")) in str(error), f"{label}: {error}"
            return
        raise AssertionError(f"{label}: expected {expected_error}")
    result = run(example.input)
    assert is_dataclass(result) and not isinstance(result, type), label
    fields = asdict(result)
    for key, want in example.expect.items():
        if want is None:
            assert key not in fields, f"{label}: {key} must be absent"
            continue
        assert key in fields, f"{label}: missing {key}"
        actual = fields[key]
        if isinstance(actual, Decimal):
            assert actual == Decimal(want), f"{label}: {key}={actual}"
        else:
            assert str(actual) == want, f"{label}: {key}={actual}"
