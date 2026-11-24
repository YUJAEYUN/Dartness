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
export { parseSnapshot, safeLink } from "../../scripts/snapshot-schema.mjs";
