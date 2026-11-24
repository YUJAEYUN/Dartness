import { useEffect, useRef, useState } from "react";
import {
  BookOpen,
  CheckCheck,
  CircleHelp,
  ClipboardList,
  GitBranch,
  CodeXml,
  LayoutDashboard,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { Button } from "./components/ui/button";
import { failedRuns, isStale, repository, sourceBase, type Item } from "./data";
import { loadSnapshot, type SnapshotState } from "./snapshot-loader";
import "./App.css";
import { ProjectStatus } from "./ProjectStatus";
import { Briefings } from "./Briefings";
import { WorkResults } from "./WorkResults";
const docs = [
  ["시스템 상태", "system-status.md", "처리 흐름의 구현 상태와 다음 작업"],
  ["요구사항", "specs/requirements.md", "조회·출력에서 지켜야 할 기준"],
  ["에이전트 위임 범위", "guides/delegation.md", "자동으로 처리할 일과 확인할 일"],
  ["테스트 기준", "guides/testing.md", "정답과 근거를 확인하는 방법"],
  [
    "개발 원칙과 평가",
    "design/engineering-principles.md",
    "다섯 원칙과 실행 결과를 확인하는 방법",
  ],
  [
    "현금 조회 계약",
    "specs/cash-query-contract.md",
    "확정한 범위와 구현 전에 확인할 항목",
  ],
  ["구조와 판단 경계", "design/architecture.md", "코드와 에이전트의 역할"],
];
const date = (value: string) =>
  new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Seoul",
  }).format(new Date(value));
function Rows({ items, empty }: { items: Item[]; empty: string }) {
  return items.length ? (
    <ul className="rows">
      {items.map((item) => (
        <li key={item.number}>
          <div>
            <a href={item.url} target="_blank" rel="noreferrer">
              {item.title}
            </a>
            <small>
              #{item.number} · {date(item.updatedAt)}
            </small>
          </div>
          <span className={`badge ${item.state === "merged" ? "success" : ""}`}>
            {(
              {
                open: "열린 작업",
                closed: "종료",
                merged: "병합 완료",
                completed: item.conclusion === "success" ? "통과" : "결과 확인",
                in_progress: "검사 중",
                queued: "대기 중",
              } as Record<string, string>
            )[item.state] ?? item.state}
          </span>
        </li>
      ))}
    </ul>
  ) : (
    <p className="empty">{empty}</p>
  );
}
export default function App() {
  const [view, setView] = useState<SnapshotState>({
    snapshot: null,
    source: null,
    error: "",
  });
  const previous = useRef<SnapshotState | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  const [search, setSearch] = useState("");
  const { snapshot, error, source } = view;
  function load() {
    setLoading(true);
    setRefreshKey((key) => key + 1);
  }
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    void loadSnapshot(previous.current, fetch, controller.signal)
      .then((next) => {
        if (active) {
          previous.current = next;
          setView(next);
        }
      })
      .catch((cause: unknown) => {
        if (active)
          setView((current) => ({
            ...current,
            error: cause instanceof Error ? cause.message : "상태 조회 오류",
          }));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [refreshKey]);
  const matching = (item: Item) =>
    item.title.toLocaleLowerCase().includes(search.toLocaleLowerCase()) ||
    String(item.number).includes(search);
  return (
    <div className="shell">
      <aside>
        <a className="brand" href="#overview">
          <span className="brand-icon">D</span>Dartness
        </a>
        <p className="sidebar-label">프로젝트 관리</p>
        <nav aria-label="화면 메뉴">
          <a href="#overview">
            <LayoutDashboard size={18} />
            한눈에 보기
          </a>
          <a href="#query-policy">
            <BookOpen size={18} />
            공통 조회 조건
          </a>
          <a href="#query-types">
            <BookOpen size={18} />
            올인원 조회 범위
          </a>
          <a href="#system">
            <GitBranch size={18} />
            현금 조회 경로
          </a>
          <a href="#next">
            <BookOpen size={18} />
            다음 작업
          </a>
          <a href="#decisions">
            <CircleHelp size={18} />
            아직 정하지 않은 것
          </a>
          <a href="#work-results"><ClipboardList size={18} />작업 결과</a>
          <a href="#briefings">
            <ClipboardList size={18} />
            작업 브리핑
          </a>
          <a href="#progress">
            <GitBranch size={18} />
            열린 작업
          </a>
          <a href="#completed">
            <CheckCheck size={18} />
            완료한 일
          </a>
          <a href="#exceptions">
            <ShieldAlert size={18} />
            문제와 예외
          </a>
          <a href="#docs">
            <BookOpen size={18} />
            기준 문서
          </a>
        </nav>
        <div className="sidebar-bottom">
          <span className="badge">조회 전용</span>
          <p>
            중요한 결정은 함께.
            <br />
            일반 작업은 에이전트가.
          </p>
          <a href={repository}>
            <CodeXml size={16} /> GitHub 저장소
          </a>
        </div>
      </aside>
      <main id="overview">
        <header>
          <div>
            <p className="eyebrow">DARTNESS / WORKSPACE</p>
            <h1>프로젝트 한눈에 보기</h1>
            <p className="muted">
              결정할 일과 작업 결과를 한곳에서 확인하세요.
            </p>
          </div>
          <Button variant="outline" onClick={load} disabled={loading}>
            <RefreshCw size={16} />
            {loading ? "불러오는 중" : "GitHub 상태 다시 확인"}
          </Button>
        </header>
        <div className="snapshot-info">
          <span>
            {source === "github"
              ? "GitHub에서 마지막으로 확인한 상태"
              : source === "saved"
                ? "배포 저장본 · 대체 자료"
                : "GitHub 상태 조회"}
          </span>
          <span>
            {snapshot
              ? `${date(snapshot.generatedAt)} 기준 · 한국 시간`
              : "아직 확인하지 못했습니다"}
          </span>
        </div>
        <p className="notice">
          화면을 열거나 다시 확인할 때 공개 GitHub 상태를 조회합니다. 이후
          변경은 자동 추적하지 않습니다. 정책·구현 상태·브리핑은 배포된 문서
          기준입니다.
        </p>
        {error && (
          <div role="alert" className="alert">
            {error}{" "}
            {snapshot &&
              (source === "saved"
                ? "아래는 배포에 저장된 대체 자료입니다."
                : "아래는 마지막 정상 조회 자료입니다.")}{" "}
            <a href={repository}>GitHub에서 확인</a>
          </div>
        )}
        {snapshot && isStale(snapshot.generatedAt) && (
          <div className="alert">
            자료 생성 시각을 확인해 주세요. 24시간이 지났거나 시각이 올바르지
            않습니다.
          </div>
        )}
        {snapshot?.limited && (
          <div className="alert">
            최근 100건까지만 조회했습니다. 전체 작업은 GitHub에서 확인하세요.
          </div>
        )}
        <ProjectStatus />
        <WorkResults />
        <Briefings />
        <div className="search">
          <label htmlFor="search">작업 찾기</label>
          <input
            id="search"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="작업 이름 또는 번호"
          />
        </div>
        <div className="columns">
          <section id="progress" className="panel">
            <div className="section-title">
              <h2>
                <GitBranch size={20} />
                열린 작업
              </h2>
              {snapshot && (
                <span className="count">
                  {snapshot.issues.filter((i) => i.state === "open").length}
                </span>
              )}
            </div>
            {snapshot ? (
              <Rows
                items={snapshot.issues.filter(
                  (i) => i.state === "open" && matching(i),
                )}
                empty={
                  search
                    ? "검색 결과가 없습니다."
                    : "저장 시점에 열린 이슈가 없습니다."
                }
              />
            ) : (
              <p className="empty">
                {loading
                  ? "자료를 불러오는 중입니다."
                  : "작업 상태를 확인할 수 없습니다."}
              </p>
            )}
          </section>
          <section id="completed" className="panel">
            <div className="section-title">
              <h2>
                <CheckCheck size={20} />
                완료한 일
              </h2>
              <a href={`${repository}/pulls?q=is%3Apr+is%3Amerged`}>전체 PR</a>
            </div>
            {snapshot ? (
              <Rows
                items={snapshot.pulls
                  .filter((i) => i.state === "merged" && matching(i))
                  .slice(0, 6)}
                empty="조건에 맞는 병합 결과가 없습니다."
              />
            ) : (
              <p className="empty">작업 상태를 확인할 수 없습니다.</p>
            )}
          </section>
        </div>
        <section id="exceptions" className="panel">
          <div className="section-title">
            <h2>
              <ShieldAlert size={20} />
              문제와 예외
            </h2>
            <a href={`${repository}/actions`}>검사 원본</a>
          </div>
          <p className="muted">
            main의 최근 실행을 확인합니다. 진행 중인 검사를 통과로 표시하지
            않습니다. 문서와 코드의 의미상 일치는 별도 검토가 필요합니다.
          </p>
          {snapshot ? (
            <>
              <Rows
                items={failedRuns(snapshot.runs)}
                empty={
                  snapshot.runs.length
                    ? "저장된 최근 검사에서 완료된 실패 결과는 없습니다."
                    : "검사 자료가 없습니다. 정상 여부를 확인할 수 없습니다."
                }
              />
              <details>
                <summary>최근 검사 결과 확인</summary>
                <Rows
                  items={snapshot.runs.slice(0, 4)}
                  empty="검사 자료가 없습니다. 정상 여부를 확인할 수 없습니다."
                />
              </details>
            </>
          ) : (
            <p className="empty">검사 상태를 확인할 수 없습니다.</p>
          )}
        </section>
        <section id="docs">
          <div className="section-title">
            <h2>
              <BookOpen size={20} />
              현재 기준
            </h2>
            <span className="muted">docs가 기준 원본입니다</span>
          </div>
          <div className="doc-grid">
            {docs.map(([title, file, description]) => (
              <a
                key={file}
                href={`${sourceBase}/docs/${file}`}
                className="doc-card"
              >
                <BookOpen size={20} />
                <strong>{title}</strong>
                <span>{description}</span>
              </a>
            ))}
          </div>
        </section>
        <div className="page-footer">
          Dartness · 공개 저장소 자료만 표시 · 승인과 병합은 GitHub에서
        </div>
      </main>
    </div>
  );
}
