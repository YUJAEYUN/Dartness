import { parseSync } from "vite";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { resolve, relative, posix } from "node:path";
import { root } from "./system-status.mjs";

const source = "dashboard/src/";
const bridges = new Map([
  ["dashboard/src/shared/snapshot.ts", "dashboard/scripts/snapshot-schema.mjs"],
  [
    "dashboard/src/features/github-status/snapshot-loader.ts",
    "dashboard/scripts/github-snapshot.mjs",
  ],
]);
export function importTargets(file, text) {
  const { program, errors } = parseSync(file, text);
  if (errors.length)
    throw new Error(`${file}: import 검사 전에 구문 오류를 수정하세요`);
  const targets = [];
  function add(node) {
    if (node?.type !== "Literal" || typeof node.value !== "string")
      throw new Error(`${file}: import 경로는 분석 가능한 문자열이어야 합니다`);
    targets.push(node.value);
  }
  function visit(node) {
    if (!node || typeof node !== "object") return;
    if (
      [
        "ImportDeclaration",
        "ExportNamedDeclaration",
        "ExportAllDeclaration",
        "ImportExpression",
        "TSImportType",
      ].includes(node.type) &&
      node.source
    )
      add(node.source);
    if (
      node.type === "TSImportEqualsDeclaration" &&
      node.moduleReference?.type === "TSExternalModuleReference"
    )
      add(node.moduleReference.expression);
    if (
      node.type === "CallExpression" &&
      node.callee?.type === "Identifier" &&
      node.callee.name === "require"
    )
      add(node.arguments[0]);
    for (const value of Object.values(node)) {
      if (Array.isArray(value)) value.forEach(visit);
      else if (value && typeof value === "object") visit(value);
    }
  }
  visit(program);
  return targets;
}
export function checkDirection(file, target) {
  if (!target.startsWith(source)) {
    if (bridges.get(file) !== target)
      throw new Error(`${file}: 허용하지 않은 src 밖 참조 ${target}`);
    return;
  }
  const from = file.slice(source.length).split("/");
  const to = target.slice(source.length).split("/");
  if (
    ["features", "shared", "components"].includes(from[0]) &&
    !["features", "shared", "components", "generated"].includes(to[0])
  )
    throw new Error(
      `${file}: 기능·공통 모듈은 진입점이나 미분류 모듈을 참조할 수 없습니다: ${target}`,
    );
  if (from[0] === "features") {
    if (to[0] === "app" || (to[0] === "features" && from[1] !== to[1]))
      throw new Error(
        `${file}: 다른 기능이나 app을 참조할 수 없습니다: ${target}`,
      );
  } else if (
    ["shared", "components"].includes(from[0]) &&
    ["features", "app"].includes(to[0])
  ) {
    throw new Error(
      `${file}: 공통 모듈이 기능이나 app을 역참조할 수 없습니다: ${target}`,
    );
  }
}
export function checkImports(file, text, fileExists = existsSync) {
  for (const target of importTargets(file, text)) {
    // Packages are resolved by TypeScript/Vite. Local imports have no configured aliases.
    if (!target.startsWith(".")) {
      if (target.startsWith("/"))
        throw new Error(`${file}: 절대 import 대신 상대 경로를 사용하세요`);
      continue;
    }
    const base = posix.normalize(posix.join(posix.dirname(file), target));
    const found = [
      base,
      ...[
        ".ts",
        ".tsx",
        ".json",
        ".css",
        ".mjs",
        "/index.ts",
        "/index.tsx",
      ].map((ext) => base + ext),
    ].find((path) => fileExists(resolve(root, path)));
    if (!found) throw new Error(`${file}: import 대상이 없습니다: ${target}`);
    checkDirection(file, found);
  }
}
export function checkArchitecture(dir = resolve(root, source)) {
  for (const item of readdirSync(dir, { withFileTypes: true })) {
    const file = resolve(dir, item.name);
    if (item.isDirectory()) checkArchitecture(file);
    else if (/\.tsx?$/.test(item.name))
      checkImports(
        relative(root, file).replaceAll("\\", "/"),
        readFileSync(file, "utf8"),
      );
  }
}
