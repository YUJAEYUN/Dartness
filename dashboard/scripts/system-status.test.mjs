import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  generateSystemStatus,
  readQueryTypes,
  readQueryPolicy,
  serializeStatus,
  root,
  sourcePath,
  outputPath,
} from "./system-status.mjs";
const source = readFileSync(resolve(root, sourcePath), "utf8");
describe("docs와 PO 화면의 동기화", () => {
  it("표에 없는 노드로 흐름을 연결하면 거절한다", () => {
    expect(() =>
      generateSystemStatus(
        source.replace("    classDef done", "    I --> Z\n    classDef done"),
      ),
    ).toThrow("단계 ID");
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
    const question = generateSystemStatus(source).decisions[0].question;
    const changedQuestion = `${question} (검토)`;
    const changed = source.replace(`| ${question} |`, `| ${changedQuestion} |`);
    expect(generateSystemStatus(changed).decisions[0].question).toBe(
      changedQuestion,
    );
    expect(generateSystemStatus(changed).sourceSha256).not.toBe(
      generateSystemStatus(source).sourceSha256,
    );
    expect(serializeStatus(changed)).not.toBe(serializeStatus(source));
  });
});

describe("올인원 조회 유형 원본", () => {
  const catalog = readFileSync(resolve(root, "docs/query-types.md"), "utf8");
  it("사용자가 요청한 다섯 유형과 원본 필드를 보존한다", () => {
    const types = readQueryTypes(catalog);
    expect(types.map((t) => t.id)).toEqual([
      "cash",
      "try-assets",
      "us-bonds",
      "share-compensation",
      "stock-collateral-loan",
    ]);
    expect(
      types.every((t) => t.input && t.result && t.evidence && t.unresolved),
    ).toBe(true);
  });
  it("정의하지 않은 구현 상태와 중복 유형을 거절한다", () => {
    expect(() =>
      readQueryTypes(catalog.replace("| try-assets |", "| cash |")),
    ).toThrow("중복");
    expect(() =>
      readQueryTypes(
        catalog.replace(
          "| 현금및현금성자산 금액 | 일부 |",
          "| 현금및현금성자산 금액 | 준비됨 |",
        ),
      ),
    ).toThrow("구현 상태");
  });
  it("객체의 기본 속성 이름을 구현 상태로 받아들이지 않는다", () => {
    expect(() =>
      readQueryTypes(
        catalog.replace(
          "| 현금및현금성자산 금액 | 일부 |",
          "| 현금및현금성자산 금액 | toString |",
        ),
      ),
    ).toThrow("구현 상태");
  });
  it("원본에서 유형을 삭제하면 생성 화면 데이터도 달라진다", () => {
    const changed = catalog
      .split("\n")
      .filter((line) => !line.startsWith("| us-bonds |"))
      .join("\n");
    const before = generateSystemStatus(source, undefined, catalog);
    const after = generateSystemStatus(source, undefined, changed);
    expect(after.queryTypes.length).toBe(before.queryTypes.length - 1);
    expect(after.catalogSha256).not.toBe(before.catalogSha256);
  });
  it("열이나 필수 값이 누락된 유형을 거절한다", () => {
    expect(() => readQueryTypes(catalog.replace("| cash |", "|  |"))).toThrow();
  });
});

describe("합의한 공통 조회 정책", () => {
  const policy = readFileSync(
    resolve(root, "docs/common-query-contract.md"),
    "utf8",
  );
  it("합의한 정책 항목을 원문에서 읽는다", () => {
    expect(readQueryPolicy(policy).map((p) => p.id)).toEqual([
      "query-kind",
      "universe",
      "time",
      "fallback",
      "max-age",
      "disclosure-cutoff",
      "corrections",
      "export",
      "audit",
    ]);
  });
  it("중복 정책과 빈 값을 허용하지 않는다", () => {
    expect(() =>
      readQueryPolicy(policy.replace("| max-age |", "| fallback |")),
    ).toThrow("중복");
    expect(() =>
      readQueryPolicy(policy.replace("| 조사 대상 |", "|  |")),
    ).toThrow("내용");
  });
  it("공통 정책 원문 변경도 생성물과 해시에 반영된다", () => {
    const changed = policy.replace("별도 시트에 추가", "검토 시트에 추가");
    const original = generateSystemStatus(source, undefined, undefined, policy);
    const revised = generateSystemStatus(source, undefined, undefined, changed);
    expect(revised.policySha256).not.toBe(original.policySha256);
    expect(revised.queryPolicy).not.toEqual(original.queryPolicy);
  });
});
