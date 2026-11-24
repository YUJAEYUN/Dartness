import { parseSync } from "vite";
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const bypass =
  /(?:^|\n)\s*\*?\s*(?:@ts-(?:ignore|nocheck|expect-error)|(?:eslint|oxlint)-disable|prettier-ignore)/i;
const disabled = new Set(["skip", "skipIf", "runIf", "only", "todo", "fails"]);
function stable(node) {
  if (Array.isArray(node)) return node.map(stable);
  if (!node || typeof node !== "object") return node;
  return Object.fromEntries(
    Object.entries(node)
      .filter(([key]) => !["start", "end", "loc", "range", "raw"].includes(key))
      .map(([key, value]) => [key, stable(value)]),
  );
}
export function jsMarkers(file, text) {
  const { program, comments, errors } = parseSync(file, text);
  if (errors.length) throw new Error(`${file}: 구문 분석 실패`);
  const line = (offset) => text.slice(0, offset).split("\n").length;
  const result = comments
    .filter((c) => bypass.test(c.value))
    .map((c) => ({
      kind: "검사 무시",
      line: line(c.start),
      signature: c.value.trim().replace(/\s+/g, " "),
    }));
  const aliases = new Map([
    ["it", "it"],
    ["test", "test"],
    ["describe", "describe"],
  ]);
  for (const node of program.body)
    if (node.type === "ImportDeclaration" && node.source.value === "vitest")
      for (const spec of node.specifiers) {
        if (spec.type === "ImportSpecifier")
          aliases.set(
            spec.local.name,
            spec.imported.name ?? spec.imported.value,
          );
        else if (spec.type === "ImportNamespaceSpecifier")
          aliases.set(spec.local.name, "vitest");
      }
  function chain(node) {
    if (node?.type === "Identifier")
      return [aliases.get(node.name) ?? node.name];
    if (node?.type === "CallExpression") return chain(node.callee);
    if (node?.type === "MemberExpression") {
      const key = node.computed ? node.property.value : node.property.name;
      return [...chain(node.object), key];
    }
    return [];
  }
  const candidates = [];
  function visit(node) {
    if (!node || typeof node !== "object") return;
    if (node.type === "TSAnyKeyword")
      result.push({
        kind: "명시적 Any",
        line: line(node.start),
        signature: JSON.stringify(stable(node)),
      });
    if (["CallExpression", "MemberExpression"].includes(node.type)) {
      const names = chain(node);
      if (names[0] === "vitest") names.shift();
      if (
        ["it", "test", "describe"].includes(names[0]) &&
        names.slice(1).some((name) => disabled.has(name))
      )
        candidates.push(node);
    }
    for (const value of Object.values(node)) {
      if (Array.isArray(value)) value.forEach(visit);
      else if (value && typeof value === "object") visit(value);
    }
  }
  visit(program);
  candidates.sort((a, b) => a.start - b.start || b.end - a.end);
  let end = -1;
  for (const node of candidates) {
    if (node.end <= end) continue;
    end = node.end;
    result.push({
      kind: "테스트 비활성",
      line: line(node.start),
      signature: JSON.stringify(stable(node)),
    });
  }
  return result;
}
if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const files = JSON.parse(readFileSync(0, "utf8"));
  process.stdout.write(
    JSON.stringify(
      Object.fromEntries(
        Object.entries(files).map(([file, text]) => [
          file,
          jsMarkers(file, text),
        ]),
      ),
    ),
  );
}
