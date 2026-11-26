# 작업 브리핑

상태: 2026-11-23 사용자와 정한 양식입니다. 같은 날 기능·명세 PR에는 브리핑을 필수로 하기로 했습니다.

작업 하나를 사람이 몇 분 안에 따라갈 수 있도록 한 장으로 요약합니다. PR 본문은 리뷰와 기록을 위해 자세히 쓰고, 브리핑은 사람이 판단해야 할 것만 앞에 둡니다. 브리핑은 해당 PR 시점의 작업을 요약한 2차 자료입니다. 구현 사실은 해당 PR·코드·테스트와 대조하고, 현재 진행 상태는 시스템 상태와 이슈에서 확인합니다. 요구사항·판정 기준의 원본은 관련 docs이며 브리핑이 덮어쓰지 않습니다. 구현과 기준 문서가 다르면 불일치로 남기고 어느 쪽을 수정할지 검토합니다.

## 목록

| 브리핑 | 종류 |
|---|---|
| [#107 최신 공시 선택 추가 검증](0107-latest-cash-evaluation.md) | 추가 법인 평가 |
| [#106 최신 유효 공시에서 현금 선택](0106-latest-valid-cash.md) | 최신 원문 선택 |
| [#105 전체 유형 공시 이력 수집](0105-filing-history-collection.md) | 공시 이력 수집 |
| [#104 전체 XML 정정표·현금 셀 바인딩](0104-native-correction-binding.md) | 실제 원문 연결 |
| [#103 지정 접수번호 원문 수집](0103-exact-receipt-collection.md) | 원문 수집 |
| [#102 실제 본문 관계·정정표 대조](0102-correction-web-observation.md) | 정정 근거 관측 |
| [#100 실제 공시 기간 후보·기준일 선택](0100-cash-report-candidates.md) | 현금 요청 실행 연결 |
| [#99 근거 재무상태표 바로 열기](0099-cash-table-link.md) | 근거 접근 |
| [#97 참고 파일과 같은 엑셀 배치](0097-workbook-reference-layout.md) | 출력 서식 |
| [#96 엑셀 왼쪽 정렬·10포인트](0096-workbook-style.md) | 출력 서식 |
| [#93 M1 지정 공시 현금 실행](0093-cash-report-slice.md) | 원문 실행 연결 |
| [#91 정정 전후 현금 비교](0091-correction-cash-comparison.md) | 정정 셀 비교 |
| [#89 원본·정정 근거 대조](0089-correction-evidence.md) | 공통 수집 계약 |
| [#87 상장법인 실제 연결 검증](0087-listed-live-check.md) | 실제 API 검사 |
| [#85 실행일 상장법인 연결](0085-listed-universe.md) | 공통 수집 |
| [#83 공통 공시 목록 수집](0083-disclosure-list.md) | 공통 수집 |
| [#81 예외 처리·새 우회 검사](0081-quality-guards.md) | 품질 검사 |
| [#79 에이전트 작업 진입점](0079-agent-entrypoint.md) | 개발 지침 |
| [#77 대시보드 기능별 폴더](0077-dashboard-features.md) | 코드 구조 |
| [#75 문서 폴더 정리](0075-docs-layout.md) | 문서 구조 |
| [#73 완료 근거와 개입·문제 확인](0073-work-results.md) | 관리 화면 |
| [#71 GitHub 조회 실패 시 저장본으로 배포](0071-build-snapshot-fallback.md) | 관리 화면 |
| [#68 외화 공시 등을 미결로 두기](0068-deferred-foreign-currency.md) | 명세 |
| [#70 최신 GitHub 상태 확인](0070-dashboard-live-state.md) | 관리 화면 |
| [#66 12월이 아닌 결산 법인 평가](0066-non-december-evaluation.md) | 평가 |
| [#63 12월이 아닌 결산 법인 수집](0063-fiscal-month-collection.md) | 평가 도구 |
| [#65 정정 전체 자료와 정답](0065-correction-case.md) | 개발용 사례 |
| [#62 원본·정정공시 조사](0062-correction-linking.md) | 조사·명세 |
| [#60 계정명 앞의 목차 기호 읽기](0060-leading-item-numbers.md) | 조회 기능 |
| [#53 현금 표 추출 두 번째 평가](0053-cash-table-second-evaluation.md) | 평가 |
| [#48 조회 시점과 허용 개월](0048-query-time-options.md) | 명세 |
| [#46 공통 조회 정책](0046-common-query-policy.md) | 명세 |
| [#54 공시 후보의 범위와 근거](0054-disclosure-candidates.md) | 조회 기반 |
| [#51 조회 입력과 날짜 선택](0051-query-contract.md) | 조회 기반 |
| [#49 DART 원문 표 칸과 주석 번호 읽기](0049-dart-cells-and-note-labels.md) | 조회 기능 |
| [#45 현금 표 추출 첫 평가](0045-cash-table-evaluation.md) | 평가 |
| [#43 평가용 여러 법인 공시 수집](0043-evaluation-collection.md) | 평가 도구 |
| [#28 재무상태표에서 현금 금액 읽기](0028-cash-table.md) | 조회 기능 |
| [#30 docs에서 대시보드 상태 만들기](0030-dashboard-sync.md) | 대시보드 |
| [#33 올인원 조회 유형 명세](0033-query-types.md) | 명세 |
| [#34 이슈가 먼저 닫히지 않게 막기](0034-issue-autoclose.md) | 작업 절차 |

## 언제 써야 하나요?

**기능·명세 PR에는 필수입니다.** CI(scripts/check_briefing_required.py)가 PR에서 바뀐 파일을 보고 판단합니다.

- 기능 PR: `src/` 아래 파일을 바꾼 PR
- 명세 PR: 아래 문서 중 하나를 바꾼 PR
    - docs/specs/requirements.md
    - docs/specs/query-types.md
    - docs/specs/common-query-contract.md
    - docs/specs/disclosure-list.md
    - docs/specs/listed-universe.md
    - docs/specs/correction-evidence.md
    - docs/specs/correction-cash-comparison.md
    - docs/specs/cash-report-slice.md
    - docs/specs/cash-query-contract.md
    - docs/specs/cash-table-extraction.md
    - docs/specs/amounts.md
    - docs/specs/output-example.md

그 밖의 PR(테스트만, 대시보드, CI, 작업 절차 문서)은 필요하면 씁니다. 이동 전 명세 경로의 삭제도 검사 대상으로 유지합니다. 대상 PR이 이 폴더에 `PR번호 네 자리-주제.md` 브리핑을 추가하지 않으면 필수 검사 code-quality가 실패합니다. PR 번호는 PR을 연 뒤에 정해지므로, PR을 열고 브리핑을 같은 PR에 커밋으로 추가합니다.

## 양식

date는 브리핑 작성일입니다. 과거 PR을 나중에 요약했다면 그 PR의 병합일과 다를 수 있습니다.

파일 이름은 `PR번호 네 자리-주제.md`입니다. 맨 위에 메타데이터를 두고, 아래 일곱 칸을 이 순서로 씁니다. 해당 내용이 없으면 칸을 지우지 말고 "없음"과 이유를 적습니다.

```yaml
---
pr: 28          # PR 번호
issue: 19       # 관련 이슈 번호. 없으면 null
date: 2026-11-23  # 작성일. 대상 PR의 병합일과 구분합니다
stages: [D]     # 상태가 바뀐 처리 흐름 단계 ID. 없으면 []
---
```

| 칸 | 쓰는 내용 |
|---|---|
| 한 줄 요약 | 이 작업으로 무엇이 달라졌는지 한두 문장. 한계가 크면 함께 씁니다 |
| 지도에서의 위치 | [처리 흐름 지도](../system-status.md)에서 상태가 바뀐 단계. 바뀐 단계가 있으면 Mermaid로 강조합니다 |
| 무엇이 달라졌나 | 사용자가 보는 변화. 기능이면 입력과 결과 예시, 명세·절차면 전과 후 |
| 누가 무엇을 정했나 | 사용자나 이슈에서 정한 것과, 구현 중 에이전트가 새로 정한 것을 나눕니다 |
| 확인해 주세요 | 사용자가 판단할 것만 1~3개. 왜 판단이 필요한지 함께 씁니다 |
| 확인한 것과 못 한 것 | 검사·근거로 확인한 것과 확인하지 못한 것을 나란히 둡니다 |
| 근거 | PR, 이슈, 코드, 테스트, 기준 문서 링크 |

## 쓸 때 지킬 것

- **에이전트가 정한 것을 숨기지 않습니다.** 이슈에 없던 제한값, 거절 조건, 새 절차는 작아도 적습니다. 사람이 놓치기 가장 쉬운 부분입니다.
- **"확인해 주세요"에는 아직 미결인 사용자 판단만 둡니다.** 없으면 없음과 이유를 씁니다. 위임한 생성·검사·작업 관리나 이미 정해진 내용을 다시 묻지 않습니다. 구현 제한을 적을 때도 에이전트가 정한 현재 지원 범위와 사용자가 정한 도메인 정책을 구분합니다.
- **숫자는 원본에서 옮깁니다.** 금액과 테스트 수는 PR과 테스트 결과에 있는 값을 씁니다.
- **지도 강조는 메타데이터와 같아야 합니다.** `stages`에 적은 단계만 `changed`로 칠합니다.

## 대시보드에서 보기

관리 화면의 "작업 브리핑" 칸이 이 폴더의 브리핑을 최신 PR부터 보여줍니다. dashboard/scripts/briefings.mjs가 브리핑을 읽어 dashboard/src/generated/briefings.json을 만듭니다. 화면은 이 순서를 따르되, 사람이 먼저 봐야 할 "확인해 주세요"를 요약 바로 아래에 강조합니다. 지도는 브리핑의 Mermaid 대신 [시스템 상태](../system-status.md)의 지도를 쓰고, `stages`의 단계만 파란 테두리로 표시합니다.

브리핑을 추가하거나 고치면 dashboard에서 `npm run docs:generate`를 실행하고 생성 파일을 함께 커밋합니다. 화면에 표시할 수 있는 형식은 문단, 목록, 표, 굵은 글씨 한 줄 제목, 인라인 코드, 링크입니다. 링크는 docs 문서와 이 저장소의 GitHub 주소만 허용합니다. HTML, 이미지, 다른 주소의 링크가 있으면 생성이 실패합니다.

## CI가 확인하는 것

tests/test_docs_consistency.py가 메타데이터 형식, 일곱 칸의 순서, `stages`가 처리 흐름 지도에 있는 단계인지, 지도 강조와 `stages`가 같은지를 확인합니다. 문서 사이트 빌드는 목차에 없는 브리핑을 실패로 처리합니다. 필수 검사 code-quality의 `npm run docs:check`는 브리핑과 화면 데이터가 다르거나 화면에 표시할 수 없는 형식이 있으면 실패합니다. 요약 내용이 PR과 같은 뜻인지는 확인하지 못합니다.
