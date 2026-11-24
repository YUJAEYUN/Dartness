import { useEffect, useId, useRef, useState } from "react";

export function Flowchart({
  diagram,
  label = "조회 조건부터 엑셀 결과까지의 구현 상태. 동일한 내용이 아래 단계 목록에 있습니다.",
}: {
  diagram: string;
  label?: string;
}) {
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
        const { svg } = await mermaid.render(`flow${id}`, diagram);
        if (active && target.current) target.current.innerHTML = svg;
      } catch {
        if (active) setFailed(true);
      }
    }
    void render();
    return () => {
      active = false;
    };
  }, [id, diagram]);
  return (
    <>
      {failed && (
        <p role="status" className="alert">
          흐름도를 표시하지 못했습니다. 아래 단계별 설명에서 같은 상태를 확인할
          수 있습니다.
        </p>
      )}
      <div ref={target} className="flowchart" role="img" aria-label={label} />
    </>
  );
}
