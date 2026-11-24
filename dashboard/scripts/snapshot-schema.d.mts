import type { Snapshot } from "../src/shared/snapshot.ts";
export function safeLink(value: unknown): value is string;
export function parseSnapshot(value: unknown): Snapshot;
