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
    class A,B,C,D partial
    class G,H,I todo
```

## 단계별 상태와 근거

"일부"는 해당 단계의 제한된 역할·사례만 처리할 수 있다는 뜻입니다. 구현이라고 표시해도 실제 공시 전반에서 정확하다는 뜻은 아닙니다. 현금 추출의 개발용 사례 범위는 D 단계와 연결 문서를 확인합니다.

<!-- system-status: stages -->
| ID | 단계 | 상태 | 근거 | 아직 없는 것 |
|---|---|---|---|---|
| A | 조회 조건 입력 | 일부 | [공통 계약 v1](specs/common-query-contract.md), src/dartness/query_contract.py, tests/test_query_contract.py, src/dartness/disclosure_candidate.py, tests/test_disclosure_candidate.py | 공통 입력·기간·후보 키 일치·날짜와 근거 보존만 지원. 유형별 조건·사건 기간·외부 입력·실행 연결 없음 |
| B | 법인·공시 찾기 | 일부 | src/dartness/disclosure_list.py, tests/test_disclosure_list.py, [목록 수집 계약](specs/disclosure-list.md), src/dartness/listed_universe.py, tests/test_listed_universe.py, [상장법인 연결](specs/listed-universe.md) | OpenDART 현재 등록/기업개황 모집단과 공시 연결 구현. [실제 사전 점검](guides/listed-live-check.md) 5회 호출 성공, 후보 4,021개 확인 후 전체 실행 진행 중. 거래소 명부 대조·원천 갱신 지연 검증·보고서 의미/정정 선택 미구현 |
| C | 원문 수집 | 일부 | src/dartness/dart_smoke.py, tests/test_dart_smoke.py, [수집 검사](guides/dart-live-check.md) | 수동 실행 1건만 수집. 여러 법인 수집, 캐시 |
| D | 현금 행·열 추출 | 일부 | src/dartness/cash_table.py, src/dartness/account_label.py, tests/test_cash_table.py, [지원 범위](specs/cash-table-extraction.md), [첫 평가](evaluations/cash-table-dart-2025.md), [두 번째 평가](evaluations/cash-table-dart-2025-second.md), [세 번째 평가](evaluations/cash-table-dart-2025-third.md) | 선정된 단순 재무상태표 구간만 지원(KIND HTML과 DART 원문 XML). 개발용 사례는 헬릭스미스와 DART 2025 6개 법인. 검증용 5개 법인 9건에서 틀린 금액 0, 8건 정답. 그 뒤 계정명 앞 목차 기호를 떼고 비교해 대한약품 1건은 개발용. 12월이 아닌 결산 3곳 5건은 정답대로 모두 확인 필요(현금및예치금·엔화). 원화 공시 12월이 아닌 결산 법인의 값 추출, 외화 공시 처리, 금융업 현금 기준, 절 자동 선정·주석 추출 |
| E | 단위 정규화 | 구현 | src/dartness/amounts.py, tests/test_amounts.py, [금액 단위 처리](specs/amounts.md) | 대시·괄호 음수 등 지원하지 않는 표기 |
| F | 계약 검증 | 구현 | src/dartness/cash_contract.py, tests/test_cash_contract.py, [현금 계약](specs/cash-query-contract.md) | 외부 JSON 입력, 근거의 사실 확인 |
| G | 합계·차이 판정 | 미구현 | [정확성과 근거](specs/requirements.md#accuracy) | 자동 차이 판정. 표시 기준만 합의됨 |
| H | 조건 비교 | 미구현 | [현금 계약](specs/cash-query-contract.md) | 금액 조건 비교 방식, 결과 포함 정책 |
| I | 엑셀 결과 | 미구현 | [결과물 예시](specs/output-example.md) | 열 배치, 파일 생성 |

## 지금 · 다음 · 나중

**지금**은 현재 도달한 구현 범위입니다. 열린 후속 작업은 [작업 상태](work-state.md)에서 확인합니다. **다음**과 **나중**은 에이전트의 제안이며 순서를 사용자와 아직 정하지 않았습니다.

<!-- system-status: next -->
| 구분 | 작업 | 상태 |
|---|---|---|
| 지금 | 공통 입력·날짜와 공시 후보 계약 v1 | [계약](specs/common-query-contract.md), 후보 범위 일치·출처 보존·복수 후보 보류. 실제 수집·추출 연결은 미구현 |
| 지금 | 원본·정정 전체 자료와 개발용 정답 | [PDF·원문 XBRL·현금 두 셀 대조](cases/hd-construction-correction.md). 자동 연결·정정 선택은 미구현 |
| 다음 | 유형별 미결 질문 하나를 정하고 실행 계약·실제 공시 사례 준비 | 제안 |
| 다음 | 모집단/공시 연결의 실제 API 운영 검증과 원문 후보·정정 계약 연결 | 제안 |
| 나중 | 합계·차이 판정, 조건 비교, 엑셀 결과 | 제안 |
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
