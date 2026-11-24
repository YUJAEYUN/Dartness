import type { Item } from "../../shared/snapshot";
export { parseSnapshot, safeLink } from "../../shared/snapshot";
export type { Item, Snapshot } from "../../shared/snapshot";
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
