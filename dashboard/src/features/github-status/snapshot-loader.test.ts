import { describe, expect, it, vi } from "vitest";
import { loadSnapshot, type SnapshotState } from "./snapshot-loader";

const saved = {
  generatedAt: "2026-11-20T00:00:00Z",
  repository: "https://github.com/YUJAEYUN/Dartness",
  limited: false,
  issues: [
    {
      number: 67,
      title: "기준 기록",
      state: "open",
      url: "https://github.com/YUJAEYUN/Dartness/issues/67",
      updatedAt: "2026-11-20T00:00:00Z",
    },
  ],
  pulls: [],
  runs: [],
};
const liveIssue = {
  number: 67,
  title: "기준 기록",
  state: "closed",
  html_url: "https://github.com/YUJAEYUN/Dartness/issues/67",
  updated_at: "2026-11-23T08:00:00Z",
};
function source(input: RequestInfo | URL): unknown {
  const url = String(input);
  if (url.includes("/issues?")) return [liveIssue];
  if (url.includes("/pulls?")) return [];
  if (url.includes("/actions/runs?")) return { workflow_runs: [] };
  return saved;
}

describe("최신 GitHub 조회와 대체 자료", () => {
  it("배포 저장본이 open이어도 최신 closed를 읽고 저장본을 요청하지 않는다", async () => {
    const fetcher = vi.fn(
      async (input: RequestInfo | URL, _init?: RequestInit) =>
        Response.json(source(input)),
    );
    const result = await loadSnapshot(null, fetcher);
    expect(result.source).toBe("github");
    expect(result.error).toBe("");
    expect(result.snapshot?.issues[0].state).toBe("closed");
    expect(fetcher).toHaveBeenCalledTimes(3);
    for (const [url, init] of fetcher.mock.calls) {
      expect(String(url)).toMatch(
        /^https:\/\/api.github.com\/repos\/YUJAEYUN\/Dartness\//,
      );
      expect(init?.cache).toBe("no-store");
      expect(init?.credentials).toBe("omit");
      expect(new Headers(init?.headers).has("Authorization")).toBe(false);
      expect(init?.signal).toBeInstanceOf(AbortSignal);
    }
  });
  it.each([403, 429])(
    "HTTP %i 때 저장본의 원래 시각과 실패 경고를 유지한다",
    async (status) => {
      const fetcher = vi.fn(async (input: RequestInfo | URL) =>
        String(input).startsWith("https:")
          ? new Response(null, { status })
          : Response.json(saved),
      );
      const result = await loadSnapshot(null, fetcher);
      expect(result.source).toBe("saved");
      expect(result.snapshot).toEqual(saved);
      expect(result.error).toContain(`HTTP ${status}`);
      expect(fetcher).toHaveBeenCalledTimes(4);
    },
  );
  it.each(["github", "saved"] as const)(
    "재조회 실패 시 직전 %s 자료를 오래된 저장본으로 덮지 않는다",
    async (sourceType) => {
      const previous: SnapshotState = {
        snapshot: { ...saved, generatedAt: "2026-11-23T08:00:00Z" },
        source: sourceType,
        error: "",
      };
      const fetcher = vi.fn(async () => {
        throw new Error("network");
      });
      const result = await loadSnapshot(previous, fetcher);
      expect(result.snapshot).toBe(previous.snapshot);
      expect(result.source).toBe(sourceType);
      expect(result.error).toContain("network");
      expect(fetcher).toHaveBeenCalledTimes(3);
    },
  );
  it("후속 성공은 기존 실패를 해제하고 최신 상태와 출처로 교체한다", async () => {
    const result = await loadSnapshot(
      { snapshot: saved, source: "saved", error: "old error" },
      async (input) => Response.json(source(input)),
    );
    expect(result.source).toBe("github");
    expect(result.error).toBe("");
    expect(result.snapshot?.issues[0].state).toBe("closed");
  });
  it("일부 요청만 실패해도 성공한 목록을 섞어 최신 상태로 표시하지 않는다", async () => {
    const result = await loadSnapshot(null, async (input) =>
      String(input).includes("/pulls?")
        ? new Response(null, { status: 403 })
        : Response.json(source(input)),
    );
    expect(result.source).toBe("saved");
    expect(result.snapshot?.issues[0].state).toBe("open");
    expect(result.error).toContain("HTTP 403");
  });
  it.each(["missing", "bad-link"])(
    "잘못된 API 응답(%s)을 정상 상태로 처리하지 않는다",
    async (kind) => {
      const result = await loadSnapshot(null, async (input) =>
        Response.json(
          String(input).includes("/issues?")
            ? kind === "missing"
              ? {}
              : [{ ...liveIssue, html_url: "https://evil.example/issues/67" }]
            : source(input),
        ),
      );
      expect(result.source).toBe("saved");
      expect(result.error).not.toBe("");
      expect(result.snapshot).toEqual(saved);
    },
  );
  it("최신 자료와 저장본 모두 실패하면 빈 정상 목록을 만들지 않는다", async () => {
    const result = await loadSnapshot(null, async () => {
      throw new Error("offline");
    });
    expect(result.snapshot).toBeNull();
    expect(result.source).toBeNull();
    expect(result.error).toContain("offline");
  });
  it("저장본 형식 오류도 성공한 빈 목록으로 바꾸지 않는다", async () => {
    const result = await loadSnapshot(null, async (input) =>
      String(input).startsWith("https:")
        ? new Response(null, { status: 429 })
        : Response.json({}),
    );
    expect(result.snapshot).toBeNull();
    expect(result.error).toContain("저장");
  });
  it("시작 전에 취소되면 외부 요청이나 저장본 대체를 하지 않는다", async () => {
    const controller = new AbortController();
    controller.abort();
    const fetcher = vi.fn<typeof fetch>();
    await expect(
      loadSnapshot(null, fetcher, controller.signal),
    ).rejects.toMatchObject({ name: "AbortError" });
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("진행 중 취소는 직전 자료나 저장본을 새 결과로 반환하지 않는다", async () => {
    const controller = new AbortController();
    const fetcher = vi.fn(
      (_: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_, reject) => {
          init?.signal?.addEventListener(
            "abort",
            () => reject(init.signal?.reason),
            { once: true },
          );
        }),
    );
    const pending = loadSnapshot(
      { snapshot: saved, source: "saved", error: "" },
      fetcher,
      controller.signal,
    );
    controller.abort();
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
    expect(fetcher).toHaveBeenCalledTimes(3);
  });
});
