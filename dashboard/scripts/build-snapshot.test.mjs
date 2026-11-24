import { afterEach, describe, expect, it, vi } from "vitest";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { buildSnapshot } from "./build-snapshot.mjs";
const dirs = [];
afterEach(() => {
  for (const dir of dirs.splice(0))
    rmSync(dir, { recursive: true, force: true });
});
const saved = {
  generatedAt: "2026-11-20T00:00:00Z",
  repository: "https://github.com/YUJAEYUN/Dartness",
  limited: false,
  issues: [],
  pulls: [],
  runs: [],
};
function setup(value = saved) {
  const dir = mkdtempSync(join(tmpdir(), "dartness-build-"));
  dirs.push(dir);
  const file = join(dir, "snapshot.json");
  writeFileSync(file, JSON.stringify(value));
  return { file, env: { VERCEL: "1" }, warn: vi.fn() };
}
describe("빌드 저장본 대체", () => {
  it.each([403, 429])(
    "HTTP %s 때 기존 자료와 시각을 유지하고 경고한다",
    async (status) => {
      const options = setup();
      const before = readFileSync(options.file, "utf8");
      await buildSnapshot({
        ...options,
        collect: async () => {
          throw new Error(`HTTP ${status}`);
        },
      });
      expect(readFileSync(options.file, "utf8")).toBe(before);
      expect(options.warn).toHaveBeenCalledWith(
        expect.stringContaining(saved.generatedAt),
      );
    },
  );
  it("정상 조회는 저장본을 갱신한다", async () => {
    const options = setup();
    const fresh = { ...saved, generatedAt: "2026-11-24T00:00:00Z" };
    await buildSnapshot({ ...options, collect: async () => fresh });
    expect(JSON.parse(readFileSync(options.file, "utf8"))).toEqual(fresh);
    expect(options.warn).not.toHaveBeenCalled();
  });
  it.each([
    {},
    {
      ...saved,
      issues: [
        {
          number: 1,
          title: "x",
          state: "open",
          url: "https://evil.example/",
          updatedAt: saved.generatedAt,
        },
      ],
    },
  ])("잘못된 저장본은 빌드를 실패시킨다", async (value) => {
    const options = setup(value);
    await expect(
      buildSnapshot({
        ...options,
        collect: async () => {
          throw new Error("network");
        },
      }),
    ).rejects.toThrow();
    expect(options.warn).not.toHaveBeenCalled();
  });
  it("없는 저장본은 빌드를 실패시킨다", async () => {
    const options = setup();
    rmSync(options.file);
    await expect(
      buildSnapshot({
        ...options,
        collect: async () => {
          throw new Error("network");
        },
      }),
    ).rejects.toThrow();
  });
  it("일반 CI는 외부 조회하지 않는다", async () => {
    const collect = vi.fn();
    await buildSnapshot({ env: { CI: "true" }, collect });
    expect(collect).not.toHaveBeenCalled();
  });
  it("잘못된 최신 응답도 저장본으로 대체한다", async () => {
    const options = setup();
    await buildSnapshot({ ...options, collect: async () => ({}) });
    expect(options.warn).toHaveBeenCalledOnce();
  });
  it("저장 실패는 대체 성공으로 숨기지 않는다", async () => {
    const options = setup();
    await expect(
      buildSnapshot({
        ...options,
        file: join(options.file, "missing"),
        collect: async () => saved,
      }),
    ).rejects.toThrow();
    expect(options.warn).not.toHaveBeenCalled();
  });
});
