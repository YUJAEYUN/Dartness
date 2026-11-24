import type { Snapshot } from "../src/data.ts";

export function refreshOnBuild(
  env: Record<string, string | undefined>,
): boolean;
export function collectSnapshot(
  fetchImpl?: typeof fetch,
  now?: Date,
): Promise<Snapshot>;
