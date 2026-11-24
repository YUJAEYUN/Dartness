const repo = "YUJAEYUN/Dartness";
const repository = `https://github.com/${repo}`;

export function refreshOnBuild(env) {
  return env.VERCEL === "1";
}

function item(
  value,
  state = value.state,
  title = value.title,
  number = value.number,
) {
  if (
    !Number.isSafeInteger(number) ||
    typeof title !== "string" ||
    typeof state !== "string" ||
    typeof value.html_url !== "string" ||
    typeof value.updated_at !== "string" ||
    !Number.isFinite(Date.parse(value.updated_at))
  ) {
    throw new Error("GitHub 상태 자료의 필수 필드를 확인할 수 없습니다.");
  }
  const url = new URL(value.html_url);
  if (
    url.origin !== "https://github.com" ||
    !url.pathname.startsWith(`/${repo}/`) ||
    url.username ||
    url.password
  ) {
    throw new Error("GitHub 상태 자료의 원본 링크가 올바르지 않습니다.");
  }
  return {
    number,
    title,
    state,
    url: value.html_url,
    updatedAt: value.updated_at,
  };
}

export async function collectSnapshot(fetchImpl = fetch, now = new Date()) {
  async function read(path) {
    const response = await fetchImpl(
      `https://api.github.com/repos/${repo}/${path}`,
      {
        headers: { Accept: "application/vnd.github+json" },
        signal: AbortSignal.timeout(15000),
        cache: "no-store",
        credentials: "omit",
        redirect: "error",
      },
    );
    if (!response.ok)
      throw new Error(
        `GitHub 공개 상태 조회 실패 (HTTP ${response.status}).`,
      );
    return response.json();
  }
  const [issues, pulls, actions] = await Promise.all([
    read("issues?state=all&per_page=100"),
    read("pulls?state=all&per_page=100"),
    read("actions/runs?branch=main&per_page=10"),
  ]);
  if (
    !Array.isArray(issues) ||
    !Array.isArray(pulls) ||
    !Array.isArray(actions?.workflow_runs)
  )
    throw new Error("GitHub 상태 목록을 확인할 수 없습니다.");
  return {
    generatedAt: now.toISOString(),
    repository,
    limited: issues.length === 100 || pulls.length === 100,
    issues: issues.filter((i) => !i.pull_request).map((i) => item(i)),
    pulls: pulls.map((p) => item(p, p.merged_at ? "merged" : p.state)),
    runs: actions.workflow_runs.map((r) => {
      if (r.conclusion !== null && typeof r.conclusion !== "string")
        throw new Error("검사 결과를 확인할 수 없습니다.");
      return { ...item(r, r.status, r.name, r.id), conclusion: r.conclusion };
    }),
  };
}
