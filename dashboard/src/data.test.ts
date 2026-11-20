import { describe, it, expect } from "vitest";
import { failedRuns, isStale, parseSnapshot, safeLink } from "./data";
const good = {
  generatedAt: "2026-11-20T00:00:00Z",
  repository: "https://github.com/YUJAEYUN/Dartness",
  limited: false,
  issues: [],
  pulls: [],
  runs: [],
};
describe("스냅샷 신뢰 경계", () => {
  it("자료 누락을 빈 작업 목록으로 오인하지 않는다", () => {
    expect(() => parseSnapshot({})).toThrow();
    expect(parseSnapshot(good).issues).toEqual([]);
  });
  it("외부 링크와 실행 가능한 URL을 거절한다", () => {
    for (const url of [
      "javascript:alert(1)",
      "https://github.com.evil.test/YUJAEYUN/Dartness/issues/1",
      "https://github.com/other/repo/issues/1",
    ])
      expect(safeLink(url)).toBe(false);
    expect(safeLink("https://github.com/YUJAEYUN/Dartness/issues/13")).toBe(
      true,
    );
  });
  it("출처가 다른 자료를 거절한다", () =>
    expect(() => parseSnapshot({ ...good, repository: "other" })).toThrow());
  it("오래되거나 미래인 시각을 표시한다", () => {
    const now = Date.parse(good.generatedAt);
    expect(isStale(good.generatedAt, now + 86400001)).toBe(true);
    expect(isStale(good.generatedAt, now)).toBe(false);
    expect(isStale(good.generatedAt, now - 600000)).toBe(true);
  });
  it("후속 성공이 있는 과거 실패를 현재 문제로 표시하지 않는다", () => {
    const base = {
      number: 1,
      title: "Check code",
      url: "https://github.com/YUJAEYUN/Dartness/actions/runs/1",
      state: "completed",
    };
    expect(
      failedRuns([
        { ...base, conclusion: "failure", updatedAt: "2026-11-19T00:00:00Z" },
        {
          ...base,
          number: 2,
          conclusion: "success",
          updatedAt: good.generatedAt,
        },
      ]),
    ).toEqual([]);
  });
  it("진행 중인 검사를 성공으로 처리하지 않는다", () =>
    expect(
      failedRuns([
        {
          number: 1,
          title: "Check code",
          state: "in_progress",
          conclusion: null,
          url: "https://github.com/YUJAEYUN/Dartness/actions/runs/1",
          updatedAt: good.generatedAt,
        },
      ]),
    ).toEqual([]));
});
