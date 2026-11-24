import { useState } from "react";
import { ClipboardList } from "lucide-react";
import data from "./generated/work-results.json";
import { sourceBase } from "./data";

export function WorkResults() {
  const [selected, setSelected] = useState(
    (data.groups.find((item) => item.records.length > 0) ?? data.groups[0]).pr,
  );
  const group =
    data.groups.find((item) => item.pr === selected) ?? data.groups[0];
  const recorded = data.groups.filter((item) => item.records.length > 0).length;
  return (
    <section id="work-results" className="panel">
      <div className="section-title">
        <h2>
          <ClipboardList size={21} />
          작업 결과
        </h2>
        <a href={`${sourceBase}/${data.source}`}>기록 원본과 작성 방법</a>
      </div>
      <p>
        브리핑 {data.groups.length}개 PR 중 {recorded}개 기록 ·{" "}
        {data.groups.length - recorded}개 미기록
      </p>
      <p className="muted">
        기록이 없다는 것은 성공이나 문제 없음을 뜻하지 않습니다. 아래 결과는
        배포 시 포함된 기록이며 실시간 CI 상태가 아닙니다. 같은 이슈의 여러 PR을
        포함하고 성공률·개입 횟수·시간은 계산하지 않습니다.
      </p>
      <label htmlFor="result-pr">결과를 볼 PR </label>
      <select
        id="result-pr"
        value={selected}
        onChange={(event) => setSelected(Number(event.target.value))}
      >
        {data.groups.map((item) => (
          <option key={item.pr} value={item.pr}>
            #{item.pr} {item.title} ·{" "}
            {item.records.length ? "기록 있음" : "미기록"}
          </option>
        ))}
      </select>
      <div aria-live="polite">
        <h3>
          #{group.pr} {group.title}
        </h3>
        <p>
          <a href={`https://github.com/YUJAEYUN/Dartness/pull/${group.pr}`}>
            PR 원본
          </a>
          {group.issue !== null && (
            <>
              {" "}
              ·{" "}
              <a
                href={`https://github.com/YUJAEYUN/Dartness/issues/${group.issue}`}
              >
                이슈 #{group.issue}
              </a>
            </>
          )}
        </p>
        {group.records.length ? (
          <div className="table-scroll">
            <table>
              <caption>조건별 결과와 근거 · 확인일은 한국 날짜</caption>
              <thead>
                <tr>
                  <th>구분</th>
                  <th>확인할 내용</th>
                  <th>결과</th>
                  <th>확인일</th>
                  <th>근거</th>
                </tr>
              </thead>
              <tbody>
                {group.records.map((row) => (
                  <tr key={`${row.kind}-${row.content}`}>
                    <th scope="row">{row.kind}</th>
                    <td>{row.content}</td>
                    <td>
                      <strong>{row.result}</strong>
                    </td>
                    <td>{row.date}</td>
                    <td>
                      <a href={row.evidence.url}>{row.evidence.label}</a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p role="status">
            미기록: 이 PR의 완료 조건·사람의 개입·병합 후 문제는 아직 이 표에
            정리하지 않았습니다. PR 원본을 확인해 주세요.
          </p>
        )}
      </div>
      <p className="muted">
        ‘없음’은 기록한 시점에 관측한 범위입니다. 자동 감시나 독립적인 품질
        보증이 아니며, 완료 근거와 설명은 원본에서 대조해야 합니다.
      </p>
      <small>
        원본: {data.source} · 원본 해시 {data.sha256.slice(0, 12)}
      </small>
    </section>
  );
}
