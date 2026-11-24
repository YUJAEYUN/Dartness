"""Detect newly added quality bypasses against the PR base, without approving exceptions."""

import argparse
import ast
import io
import json
import os
import re
import subprocess
import sys
import tokenize
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = ("src/", "tests/", "scripts/", "dashboard/src/", "dashboard/scripts/")
JS_SUFFIXES = (".ts", ".tsx", ".js", ".mjs", ".mts", ".cjs")
SKIPS = {
    "pytest.mark.skip",
    "pytest.mark.skipif",
    "pytest.mark.xfail",
    "pytest.skip",
    "pytest.xfail",
    "pytest.importorskip",
    "unittest.skip",
    "unittest.skipIf",
    "unittest.skipUnless",
    "unittest.expectedFailure",
}
DIRECTIVE = re.compile(
    r"^#\s*(?:(?:ruff:\s*)?noqa\b|type:\s*ignore\b|fmt:\s*(?:off|skip)\b|"
    r"mypy:\s*(?:ignore-errors|disable-error-code))",
    re.I,
)


@dataclass(frozen=True)
class Marker:
    kind: str
    line: int
    signature: str


def python_markers(text: str) -> list[Marker]:
    tree = ast.parse(text)
    lines = text.splitlines()
    markers = []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT and DIRECTIVE.search(token.string):
            markers.append(
                Marker("검사 무시", token.start[0], " ".join(token.line.strip().split()))
            )
    names: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                names[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    def name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return names.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return f"{name(node.value)}.{node.attr}"
        return ""

    call_functions = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and name(node.func) in SKIPS:
            markers.append(Marker("테스트 비활성", node.lineno, ast.dump(node)))
        elif isinstance(node, ast.Name | ast.Attribute):
            target = name(node)
            if target == "typing.Any":
                # Keep the annotation context when comparing existing uses.
                markers.append(Marker("명시적 Any", node.lineno, lines[node.lineno - 1].strip()))
            elif target in SKIPS and id(node) not in call_functions:
                markers.append(Marker("테스트 비활성", node.lineno, ast.dump(node)))
    return markers


def git(*args: str, root: Path = ROOT) -> bytes:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, check=True).stdout


def changed_pairs(base: str, head: str, root: Path = ROOT) -> list[tuple[str | None, str | None]]:
    fields = (
        git("diff", "--name-status", "-z", "--find-renames", base, head, "--", root=root)
        .decode()
        .split("\0")
    )
    pairs: list[tuple[str | None, str | None]] = []
    index = 0
    while fields[index]:
        status, path = fields[index], fields[index + 1]
        index += 2
        if status.startswith("R"):
            pairs.append((path, fields[index]))
            index += 1
        elif status == "D":
            pairs.append((path, None))
        else:
            pairs.append((None if status == "A" else path, path))
    return pairs


def tracked_source(path: str) -> bool:
    return path.startswith(PREFIXES) and path.endswith((".py", *JS_SUFFIXES))


def scan(files: dict[str, str]) -> dict[str, list[Marker]]:
    result = {p: python_markers(t) for p, t in files.items() if p.endswith(".py")}
    js = {p: t for p, t in files.items() if p.endswith(JS_SUFFIXES)}
    if js:
        raw: object = json.loads(
            subprocess.run(
                ["node", str(ROOT / "dashboard/scripts/quality-markers.mjs")],
                input=json.dumps(js),
                text=True,
                capture_output=True,
                check=True,
            ).stdout
        )
        if not isinstance(raw, dict) or set(raw) != set(js):
            raise ValueError("JS/TS 검사 결과의 파일 목록이 다릅니다")
        for path, rows in raw.items():
            if not isinstance(path, str) or not isinstance(rows, list):
                raise ValueError("JS/TS 검사 결과 형식 오류")
            result[path] = []
            for row in rows:
                if (
                    not isinstance(row, dict)
                    or not isinstance(row.get("kind"), str)
                    or not isinstance(row.get("line"), int)
                    or not isinstance(row.get("signature"), str)
                ):
                    raise ValueError("JS/TS 검사 결과 항목 오류")
                result[path].append(Marker(row["kind"], row["line"], row["signature"]))
    return result


def added(before: list[Marker], after: list[Marker]) -> list[Marker]:
    remaining = Counter((m.kind, m.signature) for m in before)
    new = []
    for marker in after:
        key = (marker.kind, marker.signature)
        if remaining[key]:
            remaining[key] -= 1
        else:
            new.append(marker)
    return new


def settings_changed(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return (
        name
        in {
            "pyproject.toml",
            "pytest.ini",
            "mypy.ini",
            "setup.cfg",
            "tox.ini",
            "ruff.toml",
            ".ruff.toml",
            ".oxlintrc.json",
            ".oxlintignore",
            ".gitignore",
            ".gitattributes",
            "package.json",
            "package-lock.json",
        }
        or path.startswith(".github/workflows/")
        or name.startswith(("tsconfig", "vite.config.", "vitest.config.", "requirements"))
        or path in {"scripts/check_quality_changes.py", "dashboard/scripts/quality-markers.mjs"}
    )


def compare(base: str, head: str, root: Path = ROOT) -> tuple[list[tuple[str, Marker]], list[str]]:
    pairs = changed_pairs(base, head, root)
    before = {
        p: git("show", f"{base}:{p}", root=root).decode()
        for p, _ in pairs
        if p and tracked_source(p)
    }
    after = {
        p: git("show", f"{head}:{p}", root=root).decode()
        for _, p in pairs
        if p and tracked_source(p)
    }
    old, new = scan(before), scan(after)
    findings = [
        (path, marker)
        for previous, path in pairs
        if path and path in new
        for marker in added(old.get(previous or "", []), new[path])
    ]
    settings = sorted({p for pair in pairs for p in pair if p and settings_changed(p)})
    return findings, settings


def main(root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    try:
        base = (
            git("rev-parse", "--verify", "--end-of-options", f"{args.base}^{{commit}}", root=root)
            .decode()
            .strip()
        )
        head = (
            git("rev-parse", "--verify", "--end-of-options", f"{args.head}^{{commit}}", root=root)
            .decode()
            .strip()
        )
        findings, settings = compare(base, head, root)
        report = [
            "## 새 검사 우회 구문 확인",
            f"비교: `{base[:12]}` → `{head[:12]}`",
            f"새 구문 {len(findings)}건. "
            "기존 예외를 승인하거나 테스트 정답을 검증한 결과는 아닙니다.",
        ]
        report.extend(f"- {path}:{marker.line} · {marker.kind}" for path, marker in findings)
        report.append("### 검사 설정·검사기 변경 (자동 승인 아님)")
        report.extend(f"- {path}" for path in settings)
        if not settings:
            report.append("변경 없음")
        if findings:
            report.append(
                "우회를 제거하거나 필요·영향을 설명하고 사용자 확인을 받으세요. "
                "검사 기준을 임의로 낮추지 마세요."
            )
        rendered = "\n\n".join(report) + "\n"
        print(rendered)
        if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
            with Path(summary).open("a") as file:
                file.write(rendered)
        return int(bool(findings))
    except (ValueError, SyntaxError, tokenize.TokenError, OSError, subprocess.CalledProcessError):
        print(
            "검사 우회 비교 실패: Git·구문·Node 실행 결과를 확인하세요. "
            "정상으로 처리하지 않습니다.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
