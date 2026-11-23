import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve, relative } from "node:path";

export const root = fileURLToPath(new URL("../../", import.meta.url));
export const sourcePath = "docs/system-status.md";
export const policyPath = "docs/common-query-contract.md";
export const catalogPath = "docs/query-types.md";
export const outputPath = "dashboard/src/generated/system-status.json";
const classes = { 구현: "done", 일부: "partial", 미구현: "todo" };

export function table(text, marker, width) {
  const token = `<!-- system-status: ${marker} -->`;
  if (text.split(token).length !== 2)
    throw new Error(`${marker}: 원본 표 표시가 하나 필요합니다`);
  const lines = text.split(token)[1].trimStart().split(/\r?\n/);
  if (!lines[0]?.startsWith("|") || !/^\|[- :|]+\|$/.test(lines[1] ?? ""))
    throw new Error(`${marker}: Markdown 표가 필요합니다`);
  const rows = [];
  for (const line of lines.slice(2)) {
    if (!line.startsWith("|")) break;
    const cells = line
      .slice(1, -1)
      .split("|")
      .map((c) => c.trim());
    if (cells.length !== width || cells.some((c) => !c))
      throw new Error(`${marker}: 표의 열 수·내용을 확인하세요`);
    rows.push(cells);
  }
  if (!rows.length) throw new Error(`${marker}: 빈 표는 허용하지 않습니다`);
  return rows;
}

function checkReferences(text, fileExists) {
  const paths = [
    ...text.matchAll(
      /(?:src|tests|dashboard|docs|\.github)\/[A-Za-z0-9_./-]+/g,
    ),
  ].map((m) => m[0]);
  const links = [...text.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)].map((m) => m[1]);
  for (const path of [
    ...paths,
    ...links.map((link) => `docs/${link.split("#")[0]}`),
  ]) {
    const full = resolve(root, path);
    if (relative(root, full).startsWith("..") || !fileExists(full))
      throw new Error(`존재하는 저장소 근거가 필요합니다: ${path}`);
  }
}

export function readQueryTypes(text) {
  const types = table(text, "query-types", 7).map(
    ([id, name, status, input, result, evidence, unresolved]) => {
      if (!/^[a-z]+(?:-[a-z]+)*$/.test(id) || !Object.hasOwn(classes, status))
        throw new Error("조회 유형 ID·구현 상태를 확인하세요");
      return { id, name, status, input, result, evidence, unresolved };
    },
  );
  if (new Set(types.map((t) => t.id)).size !== types.length)
    throw new Error("중복 조회 유형입니다");
  return types;
}

export function readQueryPolicy(text) {
  const rows = table(text, "query-policy", 3).map(([id, label, value]) => {
    if (!/^[a-z]+(?:-[a-z]+)*$/.test(id))
      throw new Error("잘못된 공통 정책 ID입니다");
    return { id, label, value };
  });
  if (new Set(rows.map((r) => r.id)).size !== rows.length)
    throw new Error("중복 공통 정책입니다");
  return rows;
}

export function generateSystemStatus(
  text,
  fileExists = existsSync,
  catalogText = readFileSync(resolve(root, catalogPath), "utf8"),
  policyText = readFileSync(resolve(root, policyPath), "utf8"),
) {
  const diagrams = [...text.matchAll(/```mermaid\n([\s\S]*?)\n```/g)];
  if (diagrams.length !== 1) throw new Error("흐름도는 하나여야 합니다");
  const diagram = diagrams[0][1];
  if (
    !diagram.startsWith("flowchart LR\n") ||
    /\b(?:click|href)\b|<|>[^\n]*</.test(diagram)
  )
    throw new Error("지원하는 조회용 흐름도만 사용하세요");
  const stages = table(text, "stages", 5).map(
    ([id, name, status, evidence, missing]) => {
      if (!/^[A-Z]$/.test(id) || !Object.hasOwn(classes, status))
        throw new Error(`잘못된 단계 ID·상태: ${id} ${status}`);
      checkReferences(evidence, fileExists);
      if (
        status !== "미구현" &&
        (!evidence.includes("src/") || !evidence.includes("tests/"))
      )
        throw new Error(`${id}: 구현 단계에는 코드와 테스트 근거가 필요합니다`);
      return { id, name, status, evidence, missing };
    },
  );
  const ids = stages.map((s) => s.id);
  for (const edge of diagram.matchAll(
    /\b([A-Z])(?:\[[^\]]+\])?\s*-->\s*([A-Z])/g,
  )) {
    if (!ids.includes(edge[1]) || !ids.includes(edge[2]))
      throw new Error("흐름도에 없는 단계 ID가 있습니다");
  }
  if (new Set(ids).size !== ids.length) throw new Error("중복 단계 ID입니다");
  const labels = new Map(
    [...diagram.matchAll(/\b([A-Z])\[([^\]]+)\]/g)].map((m) => [m[1], m[2]]),
  );
  const drawn = new Map();
  for (const match of diagram.matchAll(/^\s*class ([A-Z,]+) (\w+)$/gm)) {
    for (const id of match[1].split(",")) {
      if (drawn.has(id)) throw new Error(`단계 색이 중복됩니다: ${id}`);
      drawn.set(id, match[2]);
    }
  }
  if (
    labels.size !== stages.length ||
    drawn.size !== stages.length ||
    stages.some(
      (s) =>
        labels.get(s.id) !== s.name || drawn.get(s.id) !== classes[s.status],
    )
  )
    throw new Error("흐름도 이름·색과 단계 표가 다릅니다");
  const next = table(text, "next", 3).map(([group, task, status]) => ({
    group,
    task,
    status,
  }));
  const decisions = table(text, "decisions", 2).map(([question, affected]) => {
    if (affected.split(",").some((id) => !ids.includes(id.trim())))
      throw new Error("결정에 없는 단계 ID가 있습니다");
    return { question, affected };
  });
  const rules = table(text, "rules", 3).map(([id, description, evidence]) => {
    checkReferences(evidence, fileExists);
    return { id, description, evidence };
  });
  return {
    policySource: policyPath,
    policySha256: createHash("sha256").update(policyText).digest("hex"),
    queryPolicy: readQueryPolicy(policyText),
    catalogSource: catalogPath,
    catalogSha256: createHash("sha256").update(catalogText).digest("hex"),
    queryTypes: readQueryTypes(catalogText),
    source: sourcePath,
    sourceSha256: createHash("sha256").update(text).digest("hex"),
    diagram,
    stages,
    next,
    decisions,
    rules,
  };
}

export function serializeStatus(text, fileExists = existsSync) {
  return JSON.stringify(generateSystemStatus(text, fileExists), null, 2) + "\n";
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const generated = serializeStatus(
    readFileSync(resolve(root, sourcePath), "utf8"),
  );
  const output = resolve(root, outputPath);
  if (process.argv.includes("--check")) {
    if (!existsSync(output) || readFileSync(output, "utf8") !== generated) {
      console.error(
        "docs와 화면 데이터가 다릅니다. dashboard에서 npm run docs:generate를 실행하세요.",
      );
      process.exitCode = 1;
    }
  } else writeFileSync(output, generated);
}
