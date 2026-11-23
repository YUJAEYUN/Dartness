import data from "./generated/briefings.json";
import { repository, sourceBase } from "./data";

export type Block =
  | { type: "paragraph"; text: string }
  | { type: "label"; text: string }
  | { type: "list"; ordered: boolean; items: string[] }
  | { type: "table"; header: string[]; rows: string[][] };
export type SectionKey =
  | "summary"
  | "location"
  | "changes"
  | "decisions"
  | "confirm"
  | "checked"
  | "evidence";
export type Briefing = {
  file: string;
  sha256: string;
  pr: number;
  issue: number | null;
  merged: string;
  stages: string[];
  title: string;
  sections: Record<SectionKey, Block[]>;
};

export const briefings = data.briefings as Briefing[];

// Links were restricted to docs pages and this repository by the generator.
export function linkTarget(target: string): string | null {
  const doc = /^\.\.\/([a-z0-9-]+\.md(?:#\S+)?)$/.exec(target);
  if (doc) return `${sourceBase}/docs/${doc[1]}`;
  return target.startsWith(`${repository}/`) ? target : null;
}

export function highlightDiagram(diagram: string, stages: string[]): string {
  if (!stages.length) return diagram;
  return `${diagram}\n    classDef changed stroke:#2563eb,stroke-width:4px\n    class ${stages.join(",")} changed`;
}

