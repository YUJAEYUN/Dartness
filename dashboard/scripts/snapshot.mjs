import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
const repo = "YUJAEYUN/Dartness";
function read(path) {
  return JSON.parse(
    execFileSync("gh", ["api", `repos/${repo}/${path}`], {
      encoding: "utf8",
      maxBuffer: 4 * 1024 * 1024,
    }),
  );
}
// Allowlist fields: never publish credentials, arbitrary response objects or issue bodies.
const issues = read("issues?state=all&per_page=100");
const pulls = read("pulls?state=all&per_page=100");
const runs = read("actions/runs?branch=main&per_page=10").workflow_runs;
const data = {
  generatedAt: new Date().toISOString(),
  repository: `https://github.com/${repo}`,
  limited: issues.length === 100 || pulls.length === 100,
  issues: issues
    .filter((i) => !i.pull_request)
    .map((i) => ({
      number: i.number,
      title: i.title,
      state: i.state,
      url: i.html_url,
      updatedAt: i.updated_at,
    })),
  pulls: pulls.map((p) => ({
    number: p.number,
    title: p.title,
    state: p.merged_at ? "merged" : p.state,
    url: p.html_url,
    updatedAt: p.updated_at,
  })),
  runs: runs.map((r) => ({
    number: r.id,
    title: r.name,
    state: r.status,
    conclusion: r.conclusion,
    url: r.html_url,
    updatedAt: r.updated_at,
  })),
};
// Failed queries leave the previous snapshot intact and exit nonzero.
writeFileSync(
  new URL("../public/data/snapshot.json", import.meta.url),
  JSON.stringify(data, null, 2) + "\n",
);
console.log(`공개 상태 저장: ${data.generatedAt}`);
