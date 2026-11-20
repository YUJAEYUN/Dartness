# LLM 위키 진입점

이 페이지는 기준 문서를 찾아주는 지도입니다. 독립적인 규칙 원본이 아닙니다.

| 작업 | 먼저 읽을 문서 |
|---|---|
| DART 실제 수집 | [수동 검사와 범위](../dart-live-check.md) |
| CI·브랜치 설정 | [검사와 설정 방법](../ci.md) |
| 테스트·정답 사례 준비 | [테스트 절차](../testing.md), [실제 공시 초안](../cases/helixmith-cash.md) |
| 문서 예시 테스트 작성 | [작성 규칙](../testing.md#doc-examples). 로더는 tests/doc_examples.py, 연결 검사는 tests/test_docs_consistency.py |
| 위임·병합 판단 | [합의한 위임 정책](../delegation.md) |
| docs→화면 생성·검사 | [동기화 범위](../management-screen.md). dashboard/scripts/system-status.mjs, dashboard/src/ProjectStatus.tsx, dashboard/scripts/system-status.test.mjs |
| 관리 화면 구현·갱신 | [첫 화면·실행·데이터 원본·검사 한계](../management-screen.md). dashboard/src/App.tsx, dashboard/src/data.ts, dashboard/src/data.test.ts, dashboard/scripts/snapshot.mjs, dashboard/scripts/github-snapshot.mjs (Vercel 빌드 시 갱신) |
| 개발 작업 진행 | [작업 흐름](../development-workflow.md), [정합성 검토](../consistency.md) |
| 세션 이어가기 | [다음 작업](../work-state.md) |
| 전체 진행 상황·방향 | [시스템 상태](../system-status.md). 단계별 상태를 바꾸면 지도와 표를 함께 고칩니다 |
| 개발 원칙·실행 평가 | [다섯 개발 원칙](../engineering-principles.md), [평가 기록](../record-forms/evaluation.md) |
| 현금 표 추출 | [선정 구간의 지원 범위](../cash-table-extraction.md). src/dartness/cash_table.py, tests/test_cash_table.py |
| 현금 조회 범위·계약 | [확정한 범위와 CASH-001~003](../requirements.md#cash-scope), [규칙별 예시](../cash-query-contract.md#examples), [Python 계약 v1과 한계](../cash-query-contract.md). src/dartness/cash_contract.py, tests/test_cash_contract.py |
| 기능·데이터 계약 설계 | [요구사항](../requirements.md), [판단 경계](../architecture.md) |
| 엑셀 양식 조정 | [출력 예시](../output-example.md) |
| 문서·메모리 운영 | [운영 기준](../documentation.md). 문서 경로·규칙 ID·작업 상태 형식 검사는 tests/test_docs_consistency.py |
| 기술 후보 검토 | [초기 추천안](../development-environment-proposal.md) |

갱신 기준: 이 설정에서 생성한 docs 문서. 참조 문서가 바뀌면 관련 안내를 재검토합니다. 실제 구현이 추가되면 검증한 코드·테스트 위치를 연결합니다. 없는 파일을 예상 경로로 연결하지 않습니다.

<a id="amount"></a>
## 금액 처리 안내

AMOUNT-001의 기준은 [요구사항의 정확성과 근거](../requirements.md#accuracy)입니다. 단위를 확인할 수 없는 금액은 추정하지 않고 확인 필요로 처리합니다. [현재 검토 상태](../consistency.md#amount-001)에서 구현 여부를 확인합니다. [금액 단위 처리](../amounts.md)에 입력·출력과 지원 범위를 정의했습니다. 구현은 src/dartness/amounts.py, 검증은 tests/test_amounts.py입니다. 정상 변환은 공시 사실의 검증 완료를 뜻하지 않습니다.

## 실제 DART 수집 결과

[수동 검사 기록](../dart-live-check.md)에서 헬릭스미스의 실제 접수번호 20260320001142와 ZIP·XML 해시를 확인할 수 있습니다. 원문 수집 성공이며 재무정보 추출 정답 검증은 아닙니다.

## DART 연동 방식

[외부 도구 사용 결정](../dart-live-check.md)을 따릅니다. 외부 DART MCP·스킬·전용 래퍼는 도입하지 않고 공식 API를 직접 호출합니다. 범용 개발 도구는 계속 사용합니다.
## 실제 공시 자료

헬릭스미스 2025년 말 연결 자료를 [개발용 초안](../cases/helixmith-cash.md)으로 확인했습니다. 재무상태표는 원, 주석은 천원이며 두 값은 53원 차이가 있습니다. 사용자와 이번 53원 차이는 기본 표에서 경고하지 않고 내부 기록에 보존하기로 합의했습니다. 보편적인 자동 오차 판정은 아직 구현하지 않았습니다. 추출기가 이 자료를 통과했다고 해석하지 않습니다.
