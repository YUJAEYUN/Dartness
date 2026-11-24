import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { root } from "./system-status.mjs";
import { parseBlocks } from "./briefings.mjs";

export const resultsSource = "docs/work-results.md";
export const resultsOutput = "dashboard/src/generated/work-results.json";
const headers = ["PR", "이슈", "확인일", "구분", "확인할 내용", "결과", "근거"];
const allowed = {
  "완료 조건": ["확인됨", "미충족", "미확인"],
  "사람의 개입": ["있음", "없음", "미기록"],
  "병합 후 문제": ["있음", "없음", "미기록"],
};
function evidenceLink(value) {
  const match = /^\[([^\]]+)\]\((https:\/\/[^\s)]+)\)$/.exec(value);
  if (!match) throw new Error("근거는 설명이 있는 GitHub 링크 하나여야 합니다");
  const url = new URL(match[2]);
  if (
    url.origin !== "https://github.com" ||
    url.username ||
    url.password ||
    !/^\/YUJAEYUN\/Dartness\/(?:issues\/\d+|pull\/\d+|actions\/runs\/\d+|commit\/[a-f0-9]{40}|blob\/[^/]+\/.+)$/.test(
      url.pathname,
    )
  )
    throw new Error("근거 링크는 이 저장소의 작업·검사·코드여야 합니다");
  return { label: match[1], url: url.href };
}
export function parseResults(text, briefings) {
  const parts = text.split(/^## 실행 기록\s*$/m);
  if (parts.length !== 2) throw new Error("실행 기록 구간은 하나여야 합니다");
  const blocks = parseBlocks(parts[1], resultsSource);
  const table = blocks[0];
  if (
    blocks.length !== 1 ||
    table?.type !== "table" ||
    table.header.join("|") !== headers.join("|") ||
    !table.rows.length
  )
    throw new Error("실행 기록 표의 열과 행을 확인하세요");
  const seen = new Set();
  const records = table.rows.map(
    ([prText, issueText, date, kind, content, result, evidence]) => {
      if (!/^[1-9]\d*$/.test(prText) || !/^[1-9]\d*$/.test(issueText))
        throw new Error("PR·이슈 번호를 확인하세요");
      const pr = Number(prText),
        issue = Number(issueText);
      const briefing = briefings.find((b) => b.pr === pr);
      if (!briefing || briefing.issue !== issue)
        throw new Error("PR·이슈가 브리핑과 다릅니다");
      if (
        !/^\d{4}-\d{2}-\d{2}$/.test(date) ||
        !Number.isFinite(Date.parse(date)) ||
        new Date(date).toISOString().slice(0, 10) !== date
      )
        throw new Error("확인일은 실제 날짜여야 합니다");
      if (!Object.hasOwn(allowed, kind) || !allowed[kind].includes(result))
        throw new Error("구분별 결과 상태를 확인하세요");
      if (!content.trim()) throw new Error("확인할 내용을 적어 주세요");
      const key = `${pr}|${kind}|${content}`;
      if (seen.has(key)) throw new Error("같은 결과를 중복 기록했습니다");
      seen.add(key);
      return {
        pr,
        issue,
        date,
        kind,
        content,
        result,
        evidence: evidenceLink(evidence),
      };
    },
  );
  const groups = briefings
    .map((briefing) => {
      const rows = records.filter((r) => r.pr === briefing.pr);
      if (
        rows.length &&
        (rows.filter((r) => r.kind === "완료 조건").length < 1 ||
          rows.filter((r) => r.kind === "사람의 개입").length !== 1 ||
          rows.filter((r) => r.kind === "병합 후 문제").length !== 1)
      )
        throw new Error(
          "기록한 PR은 완료 조건과 개입·문제 각 한 줄이 필요합니다",
        );
      return {
        pr: briefing.pr,
        issue: briefing.issue,
        title: briefing.title,
        records: rows,
      };
    })
    .sort((a, b) => b.pr - a.pr);
  return {
    source: resultsSource,
    sha256: createHash("sha256").update(text).digest("hex"),
    groups,
  };
}
export function serializeResults() {
  const text = readFileSync(resolve(root, resultsSource), "utf8");
  const { briefings } = JSON.parse(
    readFileSync(
      resolve(root, "dashboard/src/generated/briefings.json"),
      "utf8",
    ),
  );
  return JSON.stringify(parseResults(text, briefings), null, 2) + "\n";
}
if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const generated = serializeResults(),
    output = resolve(root, resultsOutput);
  if (process.argv.includes("--check")) {
    if (!existsSync(output) || readFileSync(output, "utf8") !== generated) {
      console.error(
        "작업 결과와 화면 데이터가 다릅니다. npm run docs:generate를 실행하세요.",
      );
      process.exitCode = 1;
    }
  } else writeFileSync(output, generated);
}
