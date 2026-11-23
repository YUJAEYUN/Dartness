import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { root } from "./system-status.mjs";
import {
  briefingDir,
  briefingOutput,
  parseBriefing,
  serializeBriefings,
} from "./briefings.mjs";

const status = JSON.parse(
  readFileSync(resolve(root, "dashboard/src/generated/system-status.json"), "utf8"),
);
const stageIds = status.stages.map((s) => s.id);
const sample = readFileSync(resolve(root, briefingDir, "0028-cash-table.md"), "utf8");

describe("docs 브리핑과 화면 데이터", () => {
  it("커밋한 화면 데이터가 브리핑 원본에서 재생성한 결과와 같다", () => {
    expect(readFileSync(resolve(root, briefingOutput), "utf8")).toBe(
      serializeBriefings(stageIds),
    );
  });
  it("모든 브리핑을 최신 PR부터 읽는다", () => {
    const files = readdirSync(resolve(root, briefingDir)).filter((f) => /^\d{4}-/.test(f));
    const prs = JSON.parse(serializeBriefings(stageIds)).briefings.map((b) => b.pr);
    expect(prs).toHaveLength(files.length);
    expect([...prs].sort((a, b) => b - a)).toEqual(prs);
  });
  it("메타데이터·칸·표를 구조로 바꾼다", () => {
    const result = parseBriefing("0028-cash-table.md", sample, stageIds);
    expect(result.stages).toEqual(["D"]);
    expect(result.sections.confirm[0].type).toBe("list");
    expect(result.sections.changes[0].type).toBe("table");
  });
  it("처리 흐름에 없는 단계를 거절한다", () => {
    expect(() =>
      parseBriefing("0028-cash-table.md", sample.replace("stages: [D]", "stages: [Z]"), stageIds),
    ).toThrow("단계");
  });
  it("칸 이름이 바뀌면 거절한다", () => {
    expect(() =>
      parseBriefing("0028-cash-table.md", sample.replace("## 확인해 주세요", "## 질문"), stageIds),
    ).toThrow("일곱 칸");
  });
  it("HTML과 외부 링크를 화면 데이터로 만들지 않는다", () => {
    for (const unsafe of ["<script>x</script>", "[링크](https://example.com/a)", "[링크](javascript:x)"])
      expect(() =>
        parseBriefing(
          "0028-cash-table.md",
          sample.replace("## 근거\n", `## 근거\n\n${unsafe}\n`),
          stageIds,
        ),
      ).toThrow();
  });
  it("파일 이름과 PR 번호가 다르면 거절한다", () => {
    expect(() => parseBriefing("0029-cash-table.md", sample, stageIds)).toThrow("PR 번호");
  });
});
