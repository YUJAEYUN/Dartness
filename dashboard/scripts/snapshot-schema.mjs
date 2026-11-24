const repository = "https://github.com/YUJAEYUN/Dartness";
function record(value) {
  return typeof value === "object" && value !== null;
}
function date(value) {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
}
export function safeLink(value) {
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
function item(value) {
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
export function parseSnapshot(value) {
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
