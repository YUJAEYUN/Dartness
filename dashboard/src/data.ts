export const repository = "https://github.com/YUJAEYUN/Dartness";
export const sourceBase = `${repository}/blob/${import.meta.env.VITE_SOURCE_REF || "main"}`;
export type Item = {
  number: number;
  title: string;
  state: string;
  url: string;
  updatedAt: string;
  conclusion?: string | null;
};
export type Snapshot = {
  generatedAt: string;
  repository: string;
  limited: boolean;
  issues: Item[];
  pulls: Item[];
  runs: Item[];
};
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
function date(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
}
export function safeLink(value: unknown): value is string {
  if (typeof value !== "string") return false;
  try {
    const url = new URL(value);
    return (
      url.origin === "https://github.com" &&
      url.pathname.startsWith("/YUJAEYUN/Dartness/") &&
      !url.username &&
      !url.password
    );
  } catch {
    return false;
  }
}
function item(value: unknown): value is Item {
  return (
    record(value) &&
    Number.isSafeInteger(value.number) &&
    typeof value.title === "string" &&
    typeof value.state === "string" &&
    safeLink(value.url) &&
    date(value.updatedAt) &&
    (value.conclusion == null || typeof value.conclusion === "string")
  );
}
export function parseSnapshot(value: unknown): Snapshot {
  if (
    !record(value) ||
    !date(value.generatedAt) ||
    value.repository !== repository ||
    typeof value.limited !== "boolean" ||
    !Array.isArray(value.issues) ||
    !value.issues.every(item) ||
    !Array.isArray(value.pulls) ||
    !value.pulls.every(item) ||
    !Array.isArray(value.runs) ||
    !value.runs.every(item)
  )
    throw new Error(
      "자료 형식을 확인할 수 없습니다. GitHub 원본에서 확인해 주세요.",
    );
  return {
    generatedAt: value.generatedAt,
    repository,
    limited: value.limited,
    issues: value.issues,
    pulls: value.pulls,
    runs: value.runs,
  };
}
export function failedRuns(items: Item[]): Item[] {
  // Evaluate the latest run of each workflow, rather than old failures or in-progress runs.
  const latest = new Map<string, Item>();
  for (const item of items)
    if (
      !latest.has(item.title) ||
      Date.parse(item.updatedAt) > Date.parse(latest.get(item.title)!.updatedAt)
    )
      latest.set(item.title, item);
  return [...latest.values()].filter(
    (i) =>
      i.state === "completed" &&
      [
        "failure",
        "timed_out",
        "action_required",
        "cancelled",
        "startup_failure",
        "stale",
      ].includes(i.conclusion ?? ""),
  );
}
export function isStale(generatedAt: string, now = Date.now()): boolean {
  return (
    now - Date.parse(generatedAt) > 24 * 60 * 60 * 1000 ||
    Date.parse(generatedAt) > now + 5 * 60 * 1000
  );
}
