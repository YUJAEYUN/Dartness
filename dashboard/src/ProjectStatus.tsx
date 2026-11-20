import { useEffect, useId, useRef, useState } from "react";
import { BookOpen, CircleHelp, GitBranch } from "lucide-react";
import status from "./generated/system-status.json";
import { sourceBase } from "./data";

function SourceText({ text }: { text: string }) {
  const chunks = text.split(
    /(\[[^\]]+\]\([^)]+\)|(?:src|tests|\.github)\/[A-Za-z0-9_./-]+)/g,
  );
  return (
    <>
      {chunks.map((chunk, index) => {
        const match = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(chunk);
        if (!match && /^(?:src|tests|\.github)\//.test(chunk))
          return (
            <a key={index} href={`${sourceBase}/${chunk}`}>
              {chunk}
            </a>
          );
        return match ? (
          <a key={index} href={`${sourceBase}/docs/${match[2]}`}>
            {match[1]}
          </a>
        ) : (
          <span key={index}>{chunk}</span>
        );
      })}
    </>
  );
}

function Flowchart() {
  const target = useRef<HTMLDivElement>(null);
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    async function render() {
      try {
        const { default: mermaid } = await import("mermaid");
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "neutral",
          flowchart: { htmlLabels: false, useMaxWidth: false },
        });
        const { svg } = await mermaid.render(`flow${id}`, status.diagram);
        if (active && target.current) target.current.innerHTML = svg;
      } catch {
        if (active) setFailed(true);
      }
    }
    void render();
    return () => {
      active = false;
    };
  }, [id]);
  return (
    <>
      {failed && (
        <p role="status" className="alert">
          흐름도를 표시하지 못했습니다. 아래 단계별 설명에서 같은 상태를 확인할
          수 있습니다.
        </p>
      )}
      <div
        ref={target}
        className="flowchart"
        role="img"
        aria-label="조회 조건부터 엑셀 결과까지의 구현 상태. 동일한 내용이 아래 단계 목록에 있습니다."
      />
    </>
  );
}

export function ProjectStatus() {
  const [selected, setSelected] = useState(status.stages[0].id);
  const stage =
    status.stages.find((item) => item.id === selected) ?? status.stages[0];
  return (
    <>
      <section id="system" className="panel system-panel">
        <div className="section-title">
          <h2>
            <GitBranch size={21} />
            전체 구현 상태
          </h2>
          <a href={`${sourceBase}/${status.source}`}>기준 원문</a>
        </div>
        <p className="muted">
          어느 단계가 준비됐고 무엇이 남았는지 확인하세요. 단계의 구현 여부는
          docs의 검토 기록이며, CI 통과와 공시 전반의 정확성은 별개입니다.
        </p>
        <div className="legend">
          <span className="badge success">구현</span>
          <span className="badge amber">일부 구현</span>
          <span className="badge">미구현</span>
        </div>
        <Flowchart />
        <div className="stage-list" aria-label="단계별 구현 상태">
          {status.stages.map((item) => (
            <button
              key={item.id}
              className={`stage-button state-${item.status}`}
              aria-pressed={selected === item.id}
              onClick={() => setSelected(item.id)}
            >
              <strong>{item.name}</strong>
              <span>{item.status === "일부" ? "일부 구현" : item.status}</span>
            </button>
          ))}
        </div>
        <div className="stage-detail" aria-live="polite">
          <h3>
            {stage.name} <span className="badge">{stage.status}</span>
          </h3>
          <p>
            <strong>남은 범위</strong>
            <br />
            {stage.missing}
          </p>
          <p className="source-evidence">
            <strong>구현·검사 근거</strong>
            <br />
            <SourceText text={stage.evidence} />
          </p>
        </div>
        <small>
          원본: {status.source} · 원본 해시 {status.sourceSha256.slice(0, 12)} ·
          배포 코드와 함께 생성
        </small>
      </section>
      <section id="decisions" className="panel">
        <div className="section-title">
          <h2>
            <CircleHelp size={21} />
            아직 정하지 않은 것
          </h2>
          <span className="badge amber">{status.decisions.length}개 미결</span>
        </div>
        <p className="muted">
          다음 항목은 기준을 확정하기 전에 함께 정할 질문입니다. 모두 지금
          답해야 하는 승인 요청은 아닙니다.
        </p>
        <ul className="rows">
          {status.decisions.map((item) => (
            <li key={item.question}>
              <div>
                <strong>{item.question}</strong>
                <small>
                  영향받는 단계:{" "}
                  {item.affected
                    .split(",")
                    .map(
                      (id) =>
                        status.stages.find((s) => s.id === id.trim())?.name ??
                        id,
                    )
                    .join(" · ")}
                </small>
              </div>
              <a
                href={`${sourceBase}/${status.source}#답을-기다리는-결정`}
              >
                근거
              </a>
            </li>
          ))}
        </ul>
      </section>
      <section id="next" className="panel">
        <div className="section-title">
          <h2>
            <BookOpen size={21} />
            지금과 다음 작업
          </h2>
          <span className="muted">제안은 아직 확정한 작업이 아닙니다</span>
        </div>
        <ul className="rows">
          {status.next.map((item) => (
            <li key={item.task}>
              <div>
                <span className="badge">{item.group}</span>
                <p className="next-task">{item.task}</p>
                <small>{item.status}</small>
              </div>
            </li>
          ))}
        </ul>
      </section>
      <details className="panel">
        <summary>규칙별 검사 근거 확인</summary>
        <ul className="rows">
          {status.rules.map((item) => (
            <li key={item.id}>
              <div>
                <strong>
                  {item.id} · {item.description}
                </strong>
                <p className="source-evidence">
                  <SourceText text={item.evidence} />
                </p>
              </div>
            </li>
          ))}
        </ul>
      </details>
    </>
  );
}
