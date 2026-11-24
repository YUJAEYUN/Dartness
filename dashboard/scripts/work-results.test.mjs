import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { root } from "./system-status.mjs";
import {
  parseResults,
  serializeResults,
  resultsOutput,
} from "./work-results.mjs";
const briefing = [
  { pr: 70, issue: 69, title: "최신 조회" },
  { pr: 71, issue: 69, title: "저장본" },
];
const evidence = "[확인 근거](https://github.com/YUJAEYUN/Dartness/issues/69)";
const header =
  "## 실행 기록\n\n| PR | 이슈 | 확인일 | 구분 | 확인할 내용 | 결과 | 근거 |\n|---|---|---|---|---|---|---|\n";
const rows = [
  `| 70 | 69 | 2026-11-24 | 완료 조건 | 운영 배포 | 미충족 | ${evidence} |`,
  `| 70 | 69 | 2026-11-24 | 사람의 개입 | 로그 제공 필요 | 있음 | ${evidence} |`,
  `| 70 | 69 | 2026-11-24 | 병합 후 문제 | 배포 장애 | 있음 | ${evidence} |`,
];
const text = header + rows.join("\n") + "\n";
describe("작업 결과 원본과 화면", () => {
  it("생성물이 docs 원본과 같다", () =>
    expect(readFileSync(resolve(root, resultsOutput), "utf8")).toBe(
      serializeResults(),
    ));
  it("실패·개입을 보존하고 미기록 PR의 결과를 만들어내지 않는다", () => {
    const result = parseResults(text, briefing);
    expect(result.groups.map((g) => g.pr)).toEqual([71, 70]);
    expect(result.groups[0].records).toEqual([]);
    expect(result.groups[1].records.map((r) => r.result)).toEqual([
      "미충족",
      "있음",
      "있음",
    ]);
  });
  it("미확인·미기록과 없음을 구분한다", () => {
    const result = parseResults(
      text
        .replace("미충족", "미확인")
        .replace("로그 제공 필요 | 있음", "로그 제공 필요 | 미기록")
        .replace("배포 장애 | 있음", "배포 장애 | 없음"),
      briefing,
    );
    expect(result.groups[1].records.map((r) => r.result)).toEqual([
      "미확인",
      "미기록",
      "없음",
    ]);
  });
  it.each([
    ["없는 브리핑", text.replaceAll("| 70 |", "| 99 |")],
    ["다른 이슈", text.replaceAll("| 69 |", "| 68 |")],
    ["중복", text + rows[0] + "\n"],
    ["개입 누락", header + [rows[0], rows[2]].join("\n")],
    ["조건 누락", header + rows.slice(1).join("\n")],
    ["잘못된 상태", text.replace("미충족", "성공")],
    ["다른 구분의 상태", text.replace("미충족", "없음")],
    ["불가능한 날짜", text.replaceAll("2026-11-24", "2026-02-30")],
    ["표 열 변경", text.replace("확인할 내용 | 결과", "내용 | 결과")],
    ["원본 구간 중복", text + "\n## 실행 기록\n"],
  ])("%s을 거절한다", (_, invalid) =>
    expect(() => parseResults(invalid, briefing)).toThrow(),
  );
  it.each([
    "https://evil.example/a",
    "https://github.com/other/repo/issues/69",
    "https://github.com/YUJAEYUN/Dartness/evil/69",
    "javascript:alert(1)",
    "https://github.com.evil.example/YUJAEYUN/Dartness/issues/69",
  ])("위험하거나 다른 출처인 링크 %s 거절", (url) => {
    expect(() =>
      parseResults(
        text.replaceAll("https://github.com/YUJAEYUN/Dartness/issues/69", url),
        briefing,
      ),
    ).toThrow();
  });
  it("근거 없는 확인됨과 HTML을 거절한다", () => {
    expect(() =>
      parseResults(text.replaceAll(evidence, "없음"), briefing),
    ).toThrow();
    expect(() =>
      parseResults(text.replace("운영 배포", "<script>bad</script>"), briefing),
    ).toThrow();
  });
});
