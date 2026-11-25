# 시스템 상태

상태: 2026-11-20 사용자와 정한 형식의 첫 버전입니다. 단계별 상태는 에이전트가 코드와 문서를 보고 판단했습니다. 사용자가 판단 근거를 확인하는 중입니다.

이 문서는 Dartness가 처리 흐름의 어디까지 만들어졌는지, 다음에 무엇을 하는지 멀리서 보기 위한 곳입니다. 세션을 이어갈 때 읽는 [작업 상태](work-state.md)와 목적이 다릅니다. 기준 원본은 각 단계에 연결한 docs이며, 이 문서는 그 상태를 모아 보여줍니다. 개념적인 역할 구분은 [구조와 판단 경계](design/architecture.md)를 봅니다.

## 처리 흐름 지도

아래 지도는 먼저 구현한 현금 조회 경로입니다. 올인원 전체 조회 유형과 각 유형의 미결 기준은 [조회 유형 명세](specs/query-types.md)를 봅니다. 현금 조회 한 건이 사용자의 조건에서 엑셀 결과까지 가는 단계입니다. 초록은 구현, 노랑은 일부 구현, 회색 점선은 미구현입니다.

```mermaid
flowchart LR
    A[조회 조건 입력] --> B[법인·공시 찾기]
    B --> C[원문 수집]
    C --> D[현금 행·열 추출]
    D --> E[단위 정규화]
    E --> F[계약 검증]
    F --> G[합계·차이 판정]
    G --> H[조건 비교]
    H --> I[엑셀 결과]

    classDef done fill:#d1fae5,stroke:#059669,color:#064e3b
    classDef partial fill:#fef3c7,stroke:#d97706,color:#78350f
    classDef todo fill:#f3f4f6,stroke:#9ca3af,color:#374151,stroke-dasharray:4
    class E,F done
    class A,B,C,D,H,I partial
    class G todo
```

## 단계별 상태와 근거

"일부"는 해당 단계의 제한된 역할·사례만 처리할 수 있다는 뜻입니다. 구현이라고 표시해도 실제 공시 전반에서 정확하다는 뜻은 아닙니다. 현금 추출의 개발용 사례 범위는 D 단계와 연결 문서를 확인합니다.

<!-- system-status: stages -->
| ID | 단계 | 상태 | 근거 | 아직 없는 것 |
|---|---|---|---|---|
| A | 조회 조건 입력 | 일부 | [공통 계약 v1](specs/common-query-contract.md), src/dartness/query_contract.py, tests/test_query_contract.py, src/dartness/disclosure_candidate.py, tests/test_disclosure_candidate.py | [저장 현금 원문 요청 연결](specs/cash-report-slice.md#report-candidates), src/dartness/cash_snapshot.py, tests/test_cash_snapshot.py. 실제 기간 후보와 요청 날짜 선택·현금 조건/출력 연결 지원. 사건 기간·사용자 외부 입력·전수 실행은 미완료 |
| B | 법인·공시 찾기 | 일부 | src/dartness/disclosure_list.py, tests/test_disclosure_list.py, [목록 수집 계약](specs/disclosure-list.md), src/dartness/listed_universe.py, tests/test_listed_universe.py, [상장법인 연결](specs/listed-universe.md), [정정 근거 계약](specs/correction-evidence.md), src/dartness/correction_evidence.py, tests/test_correction_evidence.py, [현금 셀 비교](specs/correction-cash-comparison.md), src/dartness/correction_cash.py, tests/test_correction_cash.py | OpenDART 현재 등록/기업개황 모집단과 공시 연결 구현. [실제 전체 연결](guides/listed-live-check.md) 4,029회 호출·2,770개 법인·365건 공시 확인. 거래소 명부 대조·원천 갱신 지연 검증·준비된 원본·정정 근거 메타데이터 대조 구현. 준비된 현금 두 셀의 범위/출처/원화 비교 구현. [저장 원문 기간 후보](specs/cash-report-slice.md#report-candidates), src/dartness/cash_report_candidates.py에서 지원 현금 셀·기간·단위 근거 연결. [실제 웹 근거 관측](specs/correction-evidence.md#viewer-observation), src/dartness/correction_observation.py에서 본문 관계/정정표 읽기 연결. 범용 보고서 의미/전체 원문 바인딩/유효 정정 선택 미구현 |
| C | 원문 수집 | 일부 | [지정 공시 실행](specs/cash-report-slice.md), src/dartness/report_section.py, src/dartness/cash_report.py, tests/test_cash_report.py, src/dartness/dart_smoke.py, tests/test_dart_smoke.py, [수집 검사](guides/dart-live-check.md) | 수동 1건/평가용 여러 법인 수집 경로가 있음. [지정 공시 실행](specs/cash-report-slice.md)에서 명시적 구역 선정 연결 중. 제품 전수 원문 수집·캐시는 미완료 |
| D | 현금 행·열 추출 | 일부 | src/dartness/cash_table.py, src/dartness/account_label.py, tests/test_cash_table.py, [지원 범위](specs/cash-table-extraction.md), [첫 평가](evaluations/cash-table-dart-2025.md), [두 번째 평가](evaluations/cash-table-dart-2025-second.md), [세 번째 평가](evaluations/cash-table-dart-2025-third.md) | 선정된 단순 재무상태표 구간만 지원(KIND HTML과 DART 원문 XML). 개발용 사례는 헬릭스미스와 DART 2025 6개 법인. 검증용 5개 법인 9건에서 틀린 금액 0, 8건 정답. 그 뒤 계정명 앞 목차 기호를 떼고 비교해 대한약품 1건은 개발용. 12월이 아닌 결산 3곳 5건은 정답대로 모두 확인 필요(현금및예치금·엔화). [저장 원문의 기간 후보](specs/cash-report-slice.md#report-candidates)와 요청 날짜 연결 구현. 원화 공시 12월이 아닌 결산 법인의 값 추출, 외화 공시 처리, 금융업 현금 기준, 범용 절 자동 선정·주석 추출 |
| E | 단위 정규화 | 구현 | src/dartness/amounts.py, tests/test_amounts.py, [금액 단위 처리](specs/amounts.md) | 대시·괄호 음수 등 지원하지 않는 표기 |
| F | 계약 검증 | 구현 | src/dartness/cash_contract.py, tests/test_cash_contract.py, [현금 계약](specs/cash-query-contract.md) | 외부 JSON 입력, 근거의 사실 확인 |
| G | 합계·차이 판정 | 미구현 | [정확성과 근거](specs/requirements.md#accuracy) | 자동 차이 판정. 표시 기준만 합의됨 |
| H | 조건 비교 | 일부 | [지정 공시 실행](specs/cash-report-slice.md), src/dartness/cash_report.py, tests/test_cash_report.py | 지정 공시의 정확한 원화 하한 비교만 지원. 전수·최신 정정 적용 자격·제품 결과 포함은 미완료 |
| I | 엑셀 결과 | 일부 | [결과물 예시](specs/output-example.md), [지정 공시 실행](specs/cash-report-slice.md), src/dartness/cash_workbook.py, tests/test_cash_workbook.py | 지정 공시/제공 원문 내 선택의 세 열 엑셀·표 구간 링크·원문 메모·요청/실제 날짜·이전 자료 표시 지원. 전수/최신 유효 정정 선정 완료 결과는 미구현 |

## 지금 · 다음 · 나중

**지금**은 현재 도달한 구현 범위입니다. 열린 후속 작업은 [작업 상태](work-state.md)에서 확인합니다. M1 현금 조회 우선과 단일 법인 연결은 사용자와 정했습니다. 세부 구현 순서는 기존 위임 범위의 계획이며 미결 요구사항은 자동 확정하지 않습니다.

<!-- system-status: next -->
| 구분 | 작업 | 상태 |
|---|---|---|
| 지금 | M1 상장법인 현금 조건 조회와 근거 포함 엑셀 | 사용자 입력 금액·세 시장 전수·기존 정책 유지. [첫 실행 계약](specs/cash-report-slice.md)에 상위 Milestone 연결 |
| 지금 | 지정 공시 한 건의 원문에서 조건 비교·결과 파일 연결 | 이슈 #92, PR #93. 명시적 지원 구역 선정·기존 추출/검증·세 열 엑셀과 근거 JSON 연결. 전수·최신본 선정 완료가 아닌 중간 체크포인트 |
| 지금 | 실제 원문 후보 생성·기준일 자료 선택 연결(이슈 #94 / PR #100) | 지원 저장 사업보고서의 실제 기간/현금 근거를 공통 계약에 연결. 미확인 범위/정정·읽기 실패는 보류하며 전수 자격은 아님 |
| 지금 | 실제 본문 관계·정정표 관측(이슈 #101 / PR #102) | 양쪽 본문 목록과 정정표를 직접 읽고 응답 해시/관측 시각 보존. 이슈 #101은 전체 조건이 남아 열어 둠 |
| 다음 | 관측 근거의 전체 원문·항목 영향 바인딩과 유효 정정 선택 연결 | 기존 준비 근거·두 셀 비교를 재사용. 근거 부족은 보류하고 새 선정 기준이 필요한 경우만 논의 |
| 다음 | 근거 포함 엑셀과 독립 E2E 평가 | 출력 상세·수용 기준·의존성의 실제 미결만 논의. 한 법인 성공만으로 M1 완료 아님 |
| 나중 | 나머지 네 조회 유형의 Milestone·미결 기준·실행 범위 구체화 | 제안 |
| 나중 | 금융업 현금 기준 (이슈 #57) | 지금은 확인 필요 유지로 사용자 결정, 필요해지면 현금흐름표 기말 현금 검토 |
| 나중 | 외화 공시 현금 조회 방식, 원화 공시 12월이 아닌 결산 법인의 값 추출 확인 (이슈 #67) | 보류. 문제가 생기면 다루기로 사용자 결정 |
| 나중 | PR마다 LLM이 문서와 코드를 대조하는 참고 리뷰 | 보류. API 키·비용 결정 필요 |

## 답을 기다리는 결정

아래는 요구사항에서 아직 정하지 않은 항목입니다. 원본은 [아직 정하지 않은 것](specs/requirements.md)과 [현금 계약](specs/cash-query-contract.md)입니다.

<!-- system-status: decisions -->
| 결정 | 영향받는 단계 |
|---|---|
| 정정본 연결·여러 후보의 동률 처리 | B, C |
| 사건 기간 경계와 유형별 조회 대상 | A, D |
| 반올림 허용 범위 | G |
| 엑셀 열과 메모 배치 | I |
| 원문·내부 기록의 저장 방식과 보관 기간 | C |

## 규칙별 검사 현황

[정합성 검토](consistency.md)에 정의한 규칙과 그 규칙을 확인하는 검사입니다. 검사는 계약·변환 단계에서 잘못된 대체를 막는지 확인합니다. 선정된 단순 구간의 추출(D)도 검사하지만 전체 보고서·다른 법인 서식의 정확성을 증명하지는 않습니다.

<!-- system-status: rules -->
| 규칙 | 내용 | 검사 위치 |
|---|---|---|
| AMOUNT-001 | 단위를 확인할 수 없는 금액은 확인 필요 | [금액 예시](specs/amounts.md), tests/test_amounts.py |
| CASH-001 | 별도·개별 미확인 시 연결 금액으로 대체 금지 | [현금 예시](specs/cash-query-contract.md#examples), tests/test_cash_contract.py |
| CASH-002 | 확인 불가 금액을 0원으로 대체 금지 | [현금 예시](specs/cash-query-contract.md#examples), tests/test_cash_contract.py |
| CASH-003 | 실제 자료 날짜 혼동 금지·허용된 이전 자료는 요청/실제 날짜 표시 | [현금 예시](specs/cash-query-contract.md#examples), tests/test_cash_contract.py, [날짜 예시](specs/common-query-contract.md), tests/test_query_contract.py |

## 개발 기반

| 항목 | 상태 | 근거 |
|---|---|---|
| 코드 검사(린트·타입·테스트) | 필수 CI | .github/workflows/code.yml |
| 문서 빌드 | 필수 CI | .github/workflows/docs.yml |
| 문서 경로·규칙·예시 연결 검사 | pytest 안에서 실행 | tests/test_docs_consistency.py |
| 관리 화면 | 배포됨, docs의 배포 기준 상태와 최신 GitHub 조회/대체 자료 표시 | [관리 화면](design/management-screen.md) |

## 이 문서를 갱신할 때

단계의 상태가 바뀌는 PR에서 지도와 표를 함께 고칩니다. tests/test_docs_consistency.py가 지도의 색과 표의 상태가 같은지, 정의된 규칙이 모두 규칙 현황에 있는지, 근거 파일이 실제로 있는지 확인합니다. 상태 판단 자체가 맞는지는 확인하지 못하므로 PR에서 근거를 적습니다.

이 문서는 관리 화면의 시스템 상태 데이터 원본이기도 합니다. 원본을 고친 뒤 dashboard에서 `npm run docs:generate`를 실행해 생성 파일을 함께 커밋합니다. 필수 CI의 `npm run docs:check`가 생성물 불일치를 실패로 처리합니다. [화면 동기화 범위와 한계](design/management-screen.md)를 확인합니다.
