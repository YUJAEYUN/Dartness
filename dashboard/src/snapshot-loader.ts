import { collectSnapshot } from "../scripts/github-snapshot.mjs";
import { parseSnapshot, type Snapshot } from "./data";

export type SnapshotState =
  | { snapshot: Snapshot; source: "github" | "saved"; error: string }
  | { snapshot: null; source: null; error: string };

function joinedSignal(external: AbortSignal | undefined, timeout: AbortSignal) {
  return external ? AbortSignal.any([external, timeout]) : timeout;
}
function message(cause: unknown): string {
  return cause instanceof Error ? cause.message : "조회 오류";
}

export async function loadSnapshot(
  previous: SnapshotState | null,
  fetchImpl: typeof fetch = fetch,
  signal?: AbortSignal,
): Promise<SnapshotState> {
  signal?.throwIfAborted();
  const liveFetch: typeof fetch = (input, init) =>
    fetchImpl(input, {
      ...init,
      cache: "no-store",
      credentials: "omit",
      signal: joinedSignal(signal, init?.signal ?? AbortSignal.timeout(15000)),
    });
  try {
    const snapshot = parseSnapshot(await collectSnapshot(liveFetch));
    signal?.throwIfAborted();
    return { snapshot, source: "github", error: "" };
  } catch (cause) {
    signal?.throwIfAborted();
    const error = `최신 GitHub 상태를 확인하지 못했습니다. ${message(cause)}`;
    if (previous?.snapshot) return { ...previous, error };
    try {
      const response = await fetchImpl(
        `${import.meta.env.BASE_URL}data/snapshot.json`,
        {
          cache: "no-store",
          signal: joinedSignal(signal, AbortSignal.timeout(15000)),
        },
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const snapshot = parseSnapshot(await response.json());
      signal?.throwIfAborted();
      return { snapshot, source: "saved", error };
    } catch (savedError) {
      signal?.throwIfAborted();
      return {
        snapshot: null,
        source: null,
        error: `${error} 저장 자료도 불러오지 못했습니다. ${message(savedError)}`,
      };
    }
  }
}
