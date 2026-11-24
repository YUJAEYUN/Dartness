import { readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { collectSnapshot, refreshOnBuild } from "./github-snapshot.mjs";
import { parseSnapshot } from "./snapshot-schema.mjs";

export async function buildSnapshot({
  env = process.env,
  collect = collectSnapshot,
  file = new URL("../public/data/snapshot.json", import.meta.url),
  warn = console.warn,
} = {}) {
  if (!refreshOnBuild(env)) return;
  let data;
  try {
    data = parseSnapshot(await collect());
  } catch {
    // Validate the existing file without changing its contents or timestamp.
    const saved = parseSnapshot(JSON.parse(readFileSync(file, "utf8")));
    warn(
      `GitHub 최신 상태 조회 실패. 저장본(${saved.generatedAt})으로 배포합니다. 화면에서 최신 상태를 다시 확인합니다.`,
    );
    return;
  }
  // Disk failures must not be mistaken for a GitHub outage.
  writeFileSync(file, JSON.stringify(data, null, 2) + "\n");
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href)
  await buildSnapshot();
