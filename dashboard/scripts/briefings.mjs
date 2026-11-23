import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { root } from "./system-status.mjs";

export const briefingDir = "docs/briefings";
export const briefingOutput = "dashboard/src/generated/briefings.json";
const repositoryUrl = "https://github.com/YUJAEYUN/Dartness/";

// Same order as docs/briefings/index.md and tests/test_docs_consistency.py.
export const sections = [
  ["summary", "한 줄 요약"],
  ["location", "지도에서의 위치"],
  ["changes", "무엇이 달라졌나"],
  ["decisions", "누가 무엇을 정했나"],
  ["confirm", "확인해 주세요"],
  ["checked", "확인한 것과 못 한 것"],
  ["evidence", "근거"],
];

function checkInline(text, where) {
  if (/<|!\[/.test(text))
    throw new Error(`${where}: HTML과 이미지는 화면에 표시하지 않습니다`);
  for (const [, target] of text.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)) {
    const relativeDoc = /^\.\.\/(?:[a-z0-9-]+\/)?[a-z0-9-]+\.md(?:#[^)\s]+)?$/.test(target);
    if (!relativeDoc && !target.startsWith(repositoryUrl))
      throw new Error(`${where}: 지원하지 않는 링크입니다: ${target}`);
  }
  return text;
}

function cells(line, where) {
  return line
    .slice(1, -1)
    .split("|")
    .map((cell) => checkInline(cell.trim(), where));
}

export function parseBlocks(body, where) {
  const lines = body.split("\n");
  const blocks = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
    } else if (line.startsWith("```mermaid")) {
      // The dashboard highlights the shared flow map from `stages` instead.
      const end = lines.indexOf("```", index + 1);
      if (end < 0) throw new Error(`${where}: 닫히지 않은 흐름도입니다`);
      index = end + 1;
    } else if (line.startsWith("|")) {
      const header = cells(line, where);
      if (!/^\|[- :|]+\|$/.test(lines[index + 1] ?? ""))
        throw new Error(`${where}: 표 구분선이 필요합니다`);
      const rows = [];
      index += 2;
      while (lines[index]?.startsWith("|")) {
        const row = cells(lines[index], where);
        if (row.length !== header.length)
          throw new Error(`${where}: 표의 열 수가 다릅니다`);
        rows.push(row);
        index += 1;
      }
      blocks.push({ type: "table", header, rows });
    } else if (/^(?:- |\d+\. )/.test(line)) {
      const ordered = /^\d+\. /.test(line);
      const items = [];
      while (/^(?:- |\d+\. )/.test(lines[index] ?? "")) {
        if (/^\d+\. /.test(lines[index]) !== ordered)
          throw new Error(`${where}: 목록 종류가 섞였습니다`);
        items.push(checkInline(lines[index].replace(/^(?:- |\d+\. )/, ""), where));
        index += 1;
      }
      blocks.push({ type: "list", ordered, items });
    } else if (/^\*\*[^*]+\*\*$/.test(line)) {
      blocks.push({ type: "label", text: line.slice(2, -2) });
      index += 1;
    } else if (/^(?:#|>|```|\s)/.test(line)) {
      throw new Error(`${where}: 지원하지 않는 형식입니다: ${line.slice(0, 20)}`);
    } else {
      const paragraph = [];
      while (lines[index]?.trim() && !/^(?:\||- |\d+\. |```|\*\*[^*]+\*\*$)/.test(lines[index])) {
        paragraph.push(lines[index]);
        index += 1;
      }
      blocks.push({ type: "paragraph", text: checkInline(paragraph.join(" "), where) });
    }
  }
  return blocks;
}

export function parseBriefing(file, text, stageIds) {
  const meta =
    /^---\npr: (\d+)\nissue: (\d+|null)\ndate: (\d{4}-\d{2}-\d{2})\nstages: \[([A-Z, ]*)\]\n---\n\n# (.+)\n/.exec(
      text,
    );
  if (!meta) throw new Error(`${file}: 메타데이터와 제목을 확인하세요`);
  const [header, pr, issue, date, stageText, title] = meta;
  if (!file.startsWith(`${pr.padStart(4, "0")}-`))
    throw new Error(`${file}: 파일 이름과 PR 번호가 다릅니다`);
  const stages = stageText.split(",").map((s) => s.trim()).filter(Boolean);
  if (stages.some((id) => !stageIds.includes(id)))
    throw new Error(`${file}: 처리 흐름에 없는 단계입니다`);
  const parts = text.slice(header.length).split(/^## /m).slice(1);
  if (parts.map((part) => part.split("\n")[0]).join("|") !== sections.map(([, h]) => h).join("|"))
    throw new Error(`${file}: 일곱 칸의 이름과 순서를 확인하세요`);
  const body = Object.fromEntries(
    parts.map((part, i) => [
      sections[i][0],
      parseBlocks(part.split("\n").slice(1).join("\n"), `${file} ${sections[i][1]}`),
    ]),
  );
  if (body.summary.length !== 1 || body.summary[0].type !== "paragraph")
    throw new Error(`${file}: 한 줄 요약은 문단 하나여야 합니다`);
  return {
    file: `${briefingDir}/${file}`,
    sha256: createHash("sha256").update(text).digest("hex"),
    pr: Number(pr),
    issue: issue === "null" ? null : Number(issue),
    date,
    stages,
    title,
    sections: body,
  };
}

export function generateBriefings(stageIds, readDir = readdirSync, readFile = readFileSync) {
  const files = readDir(resolve(root, briefingDir))
    .filter((name) => /^\d{4}-[a-z0-9-]+\.md$/.test(name))
    .sort()
    .reverse();
  if (!files.length) throw new Error("브리핑이 하나 이상 필요합니다");
  return {
    source: briefingDir,
    briefings: files.map((file) =>
      parseBriefing(file, readFile(resolve(root, briefingDir, file), "utf8"), stageIds),
    ),
  };
}

export function serializeBriefings(stageIds) {
  return JSON.stringify(generateBriefings(stageIds), null, 2) + "\n";
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const status = JSON.parse(
    readFileSync(resolve(root, "dashboard/src/generated/system-status.json"), "utf8"),
  );
  const generated = serializeBriefings(status.stages.map((s) => s.id));
  const output = resolve(root, briefingOutput);
  if (process.argv.includes("--check")) {
    if (!existsSync(output) || readFileSync(output, "utf8") !== generated) {
      console.error(
        "브리핑과 화면 데이터가 다릅니다. dashboard에서 npm run docs:generate를 실행하세요.",
      );
      process.exitCode = 1;
    }
  } else writeFileSync(output, generated);
}
