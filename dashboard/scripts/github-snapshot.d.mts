import type { Snapshot } from "../src/shared/snapshot.ts";

export function refreshOnBuild(
  env: Record<string, string | undefined>,
): boolean;
export function collectSnapshot(
  fetchImpl?: typeof fetch,
  now?: Date,
): Promise<Snapshot>;
