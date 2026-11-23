import { useState } from "react";
import { ClipboardList } from "lucide-react";
import status from "./generated/system-status.json";
import { sourceBase } from "./data";
import {
  briefings,
  highlightDiagram,
  linkTarget,
  type Block,
} from "./briefing-data";
import { Flowchart } from "./ProjectStatus";

function Inline({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g);
  return (
    <>
      {parts.map((part, index) => {
        if (/^\*\*[^*]+\*\*$/.test(part))
          return <strong key={index}>{part.slice(2, -2)}</strong>;
        if (/^`[^`]+`$/.test(part)) {
          const code = part.slice(1, -1);
          return /^(?:src|tests|dashboard|docs|scripts|\.github)\/[\w./-]+$/.test(code) ? (
            <a key={index} href={`${sourceBase}/${code}`}>
              <code>{code}</code>
            </a>
          ) : (
            <code key={index}>{code}</code>
          );
        }
        const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(part);
        const href = link && linkTarget(link[2]);
        if (link) return href ? <a key={index} href={href}>{link[1]}</a> : <span key={index}>{link[1]}</span>;
        return <span key={index}>{part}</span>;
      })}
    </>
  );
}

function Blocks({ blocks }: { blocks: Block[] }) {
  return (
    <>
      {blocks.map((block, index) => {
        if (block.type === "paragraph")
          return (
            <p key={index}>
              <Inline text={block.text} />
            </p>
          );
        if (block.type === "label")
          return (
            <h4 key={index} className="briefing-label">
              {block.text}
            </h4>
          );
        if (block.type === "list") {
          const List = block.ordered ? "ol" : "ul";
          return (
            <List key={index}>
              {block.items.map((item) => (
                <li key={item}>
                  <Inline text={item} />
                </li>
              ))}
            </List>
          );
        }
        return (
          <div key={index} className="table-scroll">
            <table>
              <thead>
                <tr>
                  {block.header.map((cell) => (
                    <th key={cell}>
                      <Inline text={cell} />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {block.rows.map((row, r) => (
                  <tr key={r}>
                    {row.map((cell, c) => (
                      <td key={c}>
                        <Inline text={cell} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </>
  );
}

const stageName = (id: string) => status.stages.find((s) => s.id === id)?.name ?? id;

export function Briefings() {
  const [selected, setSelected] = useState(briefings[0].pr);
  const briefing = briefings.find((b) => b.pr === selected) ?? briefings[0];
  const summary = briefing.sections.summary[0];
  return (
    <section id="briefings" className="panel">
      <div className="section-title">
        <h2>
          <ClipboardList size={21} />
          작업 브리핑
        </h2>
        <a href={`${sourceBase}/docs/briefings/index.md`}>양식과 목록</a>
      </div>
      <p className="muted">
        작업 하나를 따라가기 위한 요약입니다. 원본은 PR·코드·테스트이며, 다르면
        원본이 우선합니다.
      </p>
      <div className="briefing-layout">
        <ul className="briefing-list" aria-label="브리핑 목록">
          {briefings.map((item) => (
            <li key={item.pr}>
              <button aria-pressed={item.pr === briefing.pr} onClick={() => setSelected(item.pr)}>
                <strong>
                  #{item.pr} {item.title}
                </strong>
                <small>
                  {item.merged} 병합 ·{" "}
                  {item.stages.length
                    ? `바뀐 단계: ${item.stages.map(stageName).join(", ")}`
                    : "단계 변화 없음"}
                </small>
              </button>
            </li>
          ))}
        </ul>
        <article className="briefing-detail" aria-live="polite">
          <h3>
            #{briefing.pr} {briefing.title}
          </h3>
          {summary?.type === "paragraph" && (
            <p className="briefing-summary">
              <Inline text={summary.text} />
            </p>
          )}
          <div className="briefing-confirm">
            <h4>확인해 주세요</h4>
            <Blocks blocks={briefing.sections.confirm} />
          </div>
          <h4>지도에서의 위치</h4>
          {briefing.stages.length > 0 && (
            <Flowchart
              diagram={highlightDiagram(status.diagram, briefing.stages)}
              label={`이번 작업에서 바뀐 단계: ${briefing.stages.map(stageName).join(", ")}. 파란 굵은 테두리로 표시합니다.`}
            />
          )}
          <Blocks blocks={briefing.sections.location} />
          <h4>무엇이 달라졌나</h4>
          <Blocks blocks={briefing.sections.changes} />
          <h4>누가 무엇을 정했나</h4>
          <Blocks blocks={briefing.sections.decisions} />
          <h4>확인한 것과 못 한 것</h4>
          <Blocks blocks={briefing.sections.checked} />
          <h4>근거</h4>
          <Blocks blocks={briefing.sections.evidence} />
          <small>
            원본: {briefing.file} · 원본 해시 {briefing.sha256.slice(0, 12)}
          </small>
        </article>
      </div>
    </section>
  );
}
