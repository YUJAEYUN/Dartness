import type { Snapshot } from "../src/data.ts";
export function safeLink(value: unknown): value is string;
export function parseSnapshot(value: unknown): Snapshot;
