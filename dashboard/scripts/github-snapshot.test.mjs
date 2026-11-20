import { describe, expect, it, vi } from "vitest";
import { collectSnapshot, refreshOnBuild } from "./github-snapshot.mjs";
const issue = {
  number: 13,
  title: "관리 화면",
  state: "closed",
  html_url: "https://github.com/YUJAEYUN/Dartness/issues/13",
  updated_at: "2026-11-20T00:00:00Z",
  body: "not published",
  token: "not published",
};
function responses(issues = [issue]) {
  return vi.fn(async (url) => ({
    ok: true,
    status: 200,
    json: async () =>
      url.includes("/issues?")
        ? issues
        : url.includes("/pulls?")
          ? []
          : { workflow_runs: [] },
  }));
}
describe("배포 시 스냅샷 갱신", () => {
  it("Vercel에서 갱신하고 일반 CI에서는 외부 조회하지 않는다", () => {
    expect(refreshOnBuild({ VERCEL: "1" })).toBe(true);
    expect(refreshOnBuild({ CI: "true" })).toBe(false);
  });
  it("종료 상태를 유지하고 본문·토큰 필드를 배포하지 않는다", async () => {
    const fetcher = responses();
    const result = await collectSnapshot(
      fetcher,
      new Date("2026-11-20T01:00:00Z"),
    );
    expect(result.issues[0].state).toBe("closed");
    expect(result.generatedAt).toBe("2026-11-20T01:00:00.000Z");
    expect(JSON.stringify(result)).not.toContain("not published");
    expect(fetcher).toHaveBeenCalledTimes(3);
    expect(fetcher.mock.calls[0][1].headers).not.toHaveProperty(
      "Authorization",
    );
  });
  it("429 응답을 정상 자료나 빈 작업 목록으로 대체하지 않는다", async () => {
    await expect(
      collectSnapshot(async () => ({ ok: false, status: 429 })),
    ).rejects.toThrow("HTTP 429");
  });
  it("목록 누락을 정상 상태로 대체하지 않는다", async () => {
    await expect(
      collectSnapshot(async () => ({ ok: true, json: async () => ({}) })),
    ).rejects.toThrow("목록");
  });
  it("요청 장애를 삼키지 않는다", async () => {
    await expect(
      collectSnapshot(async () => {
        throw new Error("timeout");
      }),
    ).rejects.toThrow("timeout");
  });
  it("변조된 원본 링크를 거절한다", async () => {
    await expect(
      collectSnapshot(
        responses([{ ...issue, html_url: "https://evil.example/issues/13" }]),
      ),
    ).rejects.toThrow("원본 링크");
  });
  it("GitHub issue 목록에 섞인 PR을 진행 이슈로 표시하지 않는다", async () => {
    const result = await collectSnapshot(
      responses([{ ...issue, pull_request: {} }]),
    );
    expect(result.issues).toEqual([]);
  });
});
