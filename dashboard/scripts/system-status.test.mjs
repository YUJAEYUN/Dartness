import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  generateSystemStatus,
  serializeStatus,
  root,
  sourcePath,
  outputPath,
} from "./system-status.mjs";
const source = readFileSync(resolve(root, sourcePath), "utf8");
describe("docs와 PO 화면의 동기화", () => {
  it("표에 없는 노드로 흐름을 연결하면 거절한다", () => {
    expect(() => generateSystemStatus(source.replace("    classDef done", "    I --> Z\n    classDef done"))).toThrow("단계 ID");
  });
  it("단계·질문·다음 작업과 규칙을 원문에서 가져온다", () => {
    const result = generateSystemStatus(source);
    expect(result.stages.find((s) => s.id === "D").status).toBe("일부");
    expect(result.decisions.length).toBeGreaterThan(0);
    expect(result.next.some((n) => n.status === "제안")).toBe(true);
    expect(result.rules.some((r) => r.id === "CASH-003")).toBe(true);
  });
  it("커밋한 화면 데이터가 원문으로부터 재생성한 결과와 같다", () => {
    expect(readFileSync(resolve(root, outputPath), "utf8")).toBe(
      serializeStatus(source),
    );
  });
  it("단계 표만 바꾸면 지도와의 불일치를 거절한다", () => {
    expect(() =>
      generateSystemStatus(
        source.replace(
          "| D | 현금 행·열 추출 | 일부 |",
          "| D | 현금 행·열 추출 | 구현 |",
        ),
      ),
    ).toThrow("흐름도");
  });
  it("지원하지 않는 상태와 중복 표를 거절한다", () => {
    expect(() =>
      generateSystemStatus(
        source.replace(
          "| D | 현금 행·열 추출 | 일부 |",
          "| D | 현금 행·열 추출 | 완료예정 |",
        ),
      ),
    ).toThrow("상태");
    expect(() =>
      generateSystemStatus(source + "\n<!-- system-status: stages -->"),
    ).toThrow("원본 표");
  });
  it("존재하지 않는 근거 파일을 거절한다", () => {
    expect(() => generateSystemStatus(source, () => false)).toThrow(
      "저장소 근거",
    );
  });
  it("구현이라고 쓰고 테스트 근거를 빼면 거절한다", () => {
    expect(() =>
      generateSystemStatus(source.replace("tests/test_cash_table.py, ", "")),
    ).toThrow("코드와 테스트");
  });
  it("미결 질문이 없는 단계를 가리키면 거절한다", () => {
    expect(() =>
      generateSystemStatus(source.replace("| A, D |", "| A, Z |")),
    ).toThrow("단계 ID");
  });
  it("원문 변경을 원본 해시와 생성 결과에 반영한다", () => {
    const changed = source.replace(
      "기본 조회 시점(기준일 기본값)",
      "조회 시점 선택",
    );
    expect(generateSystemStatus(changed).sourceSha256).not.toBe(
      generateSystemStatus(source).sourceSha256,
    );
    expect(serializeStatus(changed)).not.toBe(serializeStatus(source));
  });
});
