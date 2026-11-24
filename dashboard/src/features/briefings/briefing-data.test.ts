import { describe, expect, it } from "vitest";
import { briefings, highlightDiagram, linkTarget } from "./briefing-data";

describe("브리핑 화면 도우미", () => {
  it("문서 링크는 저장소의 docs로, 그 밖의 링크는 표시하지 않는다", () => {
    expect(linkTarget("../ci.md#a")).toMatch(/\/blob\/[^/]+\/docs\/ci\.md#a$/);
    expect(linkTarget("../evaluations/x.md")).toMatch(/\/docs\/evaluations\/x\.md$/);
    expect(linkTarget("../../secret.md")).toBeNull();
    expect(linkTarget("../a/b/c.md")).toBeNull();
    expect(linkTarget("https://github.com/YUJAEYUN/Dartness/pull/28")).toBe(
      "https://github.com/YUJAEYUN/Dartness/pull/28",
    );
    expect(linkTarget("https://example.com")).toBeNull();
    expect(linkTarget("javascript:alert(1)")).toBeNull();
  });
  it("바뀐 단계만 강조하고 단계가 없으면 지도를 바꾸지 않는다", () => {
    expect(highlightDiagram("flowchart LR\n    A --> B", ["B"])).toContain("class B changed");
    expect(highlightDiagram("flowchart LR", [])).toBe("flowchart LR");
  });
  it("가장 최근 브리핑이 먼저 온다", () => {
    expect(briefings[0].pr).toBeGreaterThan(briefings[briefings.length - 1].pr);
  });
});
