import { describe, expect, it } from "vitest";
import {
  checkArchitecture,
  checkDirection,
  checkImports,
  importTargets,
} from "./architecture.mjs";
const feature = "dashboard/src/features/briefings/view.tsx";
describe("대시보드 참조 방향", () => {
  it("테스트를 포함한 실제 src 전체의 참조 방향과 경로를 검사한다", () =>
    expect(() => checkArchitecture()).not.toThrow());
  it("정적·타입·재내보내기·동적·import type 경로를 모두 읽는다", () => {
    expect(
      importTargets(
        feature,
        `import x from './a'; import type { A } from './b'; export { y } from './c'; const z=import('./d'); type X=import('./e').X;`,
      ),
    ).toEqual(["./a", "./b", "./c", "./d", "./e"]);
  });
  it("app은 기능을 조립하고 기능은 자기 코드·공통 UI·데이터를 쓸 수 있다", () => {
    expect(() =>
      checkDirection("dashboard/src/app/App.tsx", feature),
    ).not.toThrow();
    for (const target of [
      "features/briefings/data.ts",
      "components/Flowchart.tsx",
      "shared/repository.ts",
      "generated/briefings.json",
    ])
      expect(() =>
        checkDirection(feature, "dashboard/src/" + target),
      ).not.toThrow();
  });
  it.each(["features/work-results/WorkResults.tsx", "app/App.tsx"])(
    "기능에서 %s 참조를 거절한다",
    (target) =>
      expect(() =>
        checkDirection(feature, "dashboard/src/" + target),
      ).toThrow(),
  );
  it.each(["shared/data.ts", "components/ui/button.tsx"])(
    "공통 모듈 %s의 역참조를 거절한다",
    (from) => {
      for (const target of [feature, "dashboard/src/app/App.tsx"])
        expect(() => checkDirection("dashboard/src/" + from, target)).toThrow();
    },
  );
  it("기존 공유 스크립트 두 연결만 허용한다", () => {
    expect(() =>
      checkDirection(
        "dashboard/src/shared/snapshot.ts",
        "dashboard/scripts/snapshot-schema.mjs",
      ),
    ).not.toThrow();
    expect(() =>
      checkDirection(
        "dashboard/src/features/github-status/snapshot-loader.ts",
        "dashboard/scripts/github-snapshot.mjs",
      ),
    ).not.toThrow();
    expect(() =>
      checkDirection(feature, "dashboard/scripts/github-snapshot.mjs"),
    ).toThrow();
    expect(() =>
      checkDirection(
        "dashboard/src/shared/snapshot.ts",
        "dashboard/scripts/briefings.mjs",
      ),
    ).toThrow();
  });
  it("타입 참조와 재내보내기도 기능 경계를 우회하지 못한다", () => {
    for (const text of [
      `import type { X } from '../work-results/data'`,
      `export * from '../work-results/data'`,
      `const x=import('../work-results/data')`,
      `type X=import('../work-results/data').X`,
    ])
      expect(() => checkImports(feature, text, () => true)).toThrow();
  });
  it("계산형 동적 import와 누락된 상대 경로를 거절한다", () => {
    expect(() => importTargets(feature, "const x=import(path)")).toThrow(
      "문자열",
    );
    expect(() =>
      checkImports(feature, `import './missing'`, () => false),
    ).toThrow("대상");
  });
});

it("루트 중계 파일을 통한 경계 우회도 거절한다", () => {
  for (const from of [
    feature,
    "dashboard/src/shared/data.ts",
    "dashboard/src/components/view.tsx",
  ])
    expect(() => checkDirection(from, "dashboard/src/legacy.ts")).toThrow();
});
