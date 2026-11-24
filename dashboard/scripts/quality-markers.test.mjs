import { describe, expect, it } from "vitest";
import { jsMarkers } from "./quality-markers.mjs";
const file = "dashboard/src/example.test.ts";
describe("JS/TS의 검사 우회 구문", () => {
  it("문자열 속 가짜 지시문과 일반 테스트는 감지하지 않는다", () => {
    expect(
      jsMarkers(
        file,
        `import {it} from 'vitest'; const example='// @ts-ignore'; it('normal',()=>{});`,
      ),
    ).toEqual([]);
  });
  it.each([
    "@ts-ignore",
    "@ts-nocheck",
    "@ts-expect-error",
    "oxlint-disable",
    "eslint-disable-next-line",
    "prettier-ignore",
  ])("실제 주석 %s를 감지한다", (directive) => {
    expect(
      jsMarkers(file, `// ${directive}\nconst x=1;`).map((m) => m.kind),
    ).toEqual(["검사 무시"]);
  });
  it.each(["skip", "skipIf", "runIf", "only", "todo", "fails"])(
    "Vitest의 %s를 감지한다",
    (mode) => {
      const markers = jsMarkers(
        file,
        `import {test as check} from 'vitest'; check.${mode}('x',()=>{});`,
      );
      expect(markers).toHaveLength(1);
      expect(markers[0].kind).toBe("테스트 비활성");
    },
  );
  it("namespace·계산한 상수 속성·each 체인을 감지한다", () => {
    expect(
      jsMarkers(
        file,
        `import * as suite from 'vitest'; suite.it['skip'].each([1])('x',()=>{});`,
      ),
    ).toHaveLength(1);
  });
  it("명시적 any를 타입 문자열과 구분한다", () => {
    expect(
      jsMarkers(file, `type X=any;const text='any';`).map((m) => m.kind),
    ).toEqual(["명시적 Any"]);
  });
  it("줄 이동·서식 변경은 같은 AST 구문으로 비교한다", () => {
    const one = jsMarkers(file, `it.skip('x',()=>{});`)[0];
    const two = jsMarkers(file, `\n\nit.skip( 'x', () => {} );`)[0];
    expect(one.signature).toBe(two.signature);
    expect(one.line).not.toBe(two.line);
  });
  it("구문 오류는 빈 결과로 바꾸지 않는다", () =>
    expect(() => jsMarkers(file, `const x=;`)).toThrow());
});

it("설명 주석에서 언급한 무시 이름은 지시문이 아니다", () => {
  expect(
    jsMarkers(file, `// Do not use @ts-ignore in this function.\nconst x=1;`),
  ).toEqual([]);
});
