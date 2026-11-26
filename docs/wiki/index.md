# LLM 위키 진입점

이 페이지는 기준 문서를 찾아주는 지도입니다. 독립적인 규칙 원본이 아닙니다.

| 작업 | 먼저 읽을 문서 |
|---|---|
| 최신 공시 선택의 추가 법인 평가 | [동진쎄미켐 고정 구현 평가](../evaluations/latest-cash-dongjin-2026.md). 이력 26건/정기보고서 4개, 관련 요청 5개 일치. 코드 튜닝 없이 확인했고 전수·모든 정정 유형의 E2E는 아님 |
| 최신 유효 현금 공시 선택 | [이력 재검사·날짜/제출일 선택·관계·미지원 범위](../specs/latest-cash-source.md). src/dartness/latest_cash.py, src/dartness/filing_history.py, tests/test_latest_cash.py. 지정 이력의 지원 정기보고서 안의 선택이며 전수/모든 정정 유형 완료가 아님 |
| 저장 공시의 요청 기준일 선택 | [후보 생성·지원·보류와 실행](../specs/cash-report-slice.md#report-candidates). src/dartness/cash_report_candidates.py와 src/dartness/cash_snapshot.py가 실제 기간 열을 기존 날짜/후보 계약과 현금 실행에 연결합니다. tests/test_cash_snapshot.py. 제공 원문 묶음 안의 선택이며 전수·최신 정정·별도/개별 자동 판정은 미완료 |
| M1 지정 공시 현금 실행 | [입력·지원 태그·범위·실패·검증](../specs/cash-report-slice.md). src/dartness/report_section.py, src/dartness/cash_report.py, tests/test_cash_report.py. 전체 지정 원문에서 구역 선정 후 조건 비교. 전수·최신 정정·최종 엑셀은 미완료 |
| 정정 전후 현금 셀 비교 | [출처·범위·두 값 비교와 한계](../specs/correction-cash-comparison.md). src/dartness/correction_cash.py, tests/test_correction_cash.py. 원화 현금 입력 비교이며 의미 추출·최신본 적용은 미구현 |
| 전체 XML 정정·현금 바인딩 | [범위·기간·해시·미확인 경계](../specs/correction-evidence.md#native-binding). src/dartness/native_report.py, src/dartness/correction_binding.py, tests/test_native_correction.py. 원문을 다시 읽어 기존 관계/셀 비교에 연결하며 최신 유효 버전 선택은 하지 않음 |
| 실제 정정 웹 근거 관측 | [지원·해시·미확인 경계](../specs/correction-evidence.md#viewer-observation). src/dartness/correction_observation.py, src/dartness/correction_html.py, src/dartness/dart_viewer.py, tests/test_correction_observation.py. 양쪽 본문 목록과 정정표를 읽으며 전체 원문 바인딩·금액 영향·최신 유효성은 확정하지 않음 |
| 원본·정정 연결 근거 입력 | [수집 후보·전체 원문/뷰어 해시·마감 대조](../specs/correction-evidence.md). src/dartness/correction_evidence.py, tests/test_correction_evidence.py. 준비된 메타데이터 검사이며 의미 검증·자동 최신본 선택은 아님 |
| 상장법인 실제 연결 검증 | [실행 한도·결과·미확인 범위](../guides/listed-live-check.md). src/dartness/listed_live_check.py, tests/test_listed_live_check.py. 실제 4,029회 호출·상장법인 2,770개·공시 365건 연결 및 결과 파일 대조 완료 |
| 실행일 상장법인·공시 연결 | [공식 원천·통합·예산·관측 한계](../specs/listed-universe.md). src/dartness/listed_universe.py, tests/test_listed_universe.py. 전날 하루 실제 연결은 위 검증 기록 참조. 거래소 대조·정정/금액 판정은 미검증 |
| 공통 공시 목록 수집 | [공식 제한·입출력·실패 기준](../specs/disclosure-list.md). src/dartness/disclosure_list.py, tests/test_disclosure_list.py. 모집단 연결은 상장법인 계약 참조. 정정/금액 선택은 미구현 |
| 지정 법인 전체 유형 공시 이력 | [입력·상한·응답 보존](../guides/dart-live-check.md#filing-history). src/dartness/dart_history.py, tests/test_dart_history.py. 기존 목록 완전성을 재사용하며 관계/유효성/금액은 확정하지 않음 |
| 지정 접수번호 전체 원문 수집 | [명시적 모드·최대 2회·원문/키 보호](../guides/dart-live-check.md#exact-receipts). src/dartness/dart_receipts.py, src/dartness/dart_collect.py, tests/test_dart_receipts.py. 원본/정정 선택 없이 지정 제출서류만 수집하며 관계·금액·전체 이력의 완전성은 판정하지 않음 |
| DART 실제 수집 | [수동 검사와 범위](../guides/dart-live-check.md), [평가용 여러 법인 수집](../guides/dart-live-check.md#evaluation-collection). 코드는 src/dartness/dart_collect.py, 워크플로는 .github/workflows/collect-filings.yml |
| 예외 처리·검사 우회 변경 | [적용 규칙·PR 비교·보고와 한계](../guides/quality-guards.md). scripts/check_quality_changes.py, dashboard/scripts/quality-markers.mjs |
| CI·브랜치 설정 | [검사와 설정 방법](../guides/ci.md) |
| 다른 법인 평가 결과 | [현금 표 추출 첫 평가와 수정 결과](../evaluations/cash-table-dart-2025.md). 자료는 tests/fixtures/cash/dart-2025-eval(현재 개발용), 테스트는 tests/test_cash_eval_2025.py. [두 번째 평가(검증용 5개 법인)](../evaluations/cash-table-dart-2025-second.md)의 자료는 tests/fixtures/cash/dart-2025-eval-2, 테스트는 tests/test_cash_eval_2025_second.py. [세 번째 평가(12월이 아닌 결산)](../evaluations/cash-table-dart-2025-third.md)는 tests/fixtures/cash/dart-2025-eval-3, tests/test_cash_eval_2025_third.py |
| 테스트·정답 사례 준비 | [테스트 절차](../guides/testing.md), [실제 공시 초안](../cases/helixmith-cash.md) |
| 테스트가 버그를 잡는지 확인 | [변이 테스트](../guides/testing.md#mutation). 설정은 pyproject.toml의 [tool.mutmut], 대상은 src/dartness/cash_table.py |
| 문서 예시 테스트 작성 | [작성 규칙](../guides/testing.md#doc-examples). 로더는 tests/doc_examples.py, 연결 검사는 tests/test_docs_consistency.py |
| 위임·병합 판단 | [합의한 위임 정책](../guides/delegation.md) |
| docs→화면 생성·검사 | [동기화 범위](../design/management-screen.md). dashboard/scripts/system-status.mjs, dashboard/src/features/project-status/ProjectStatus.tsx, dashboard/scripts/system-status.test.mjs |
| 대시보드 코드 배치·참조 방향 | [기능별 폴더와 검사 범위](../design/dashboard-structure.md). dashboard/scripts/architecture.mjs, dashboard/scripts/architecture.test.mjs |
| 관리 화면 구현·갱신 | [첫 화면·실행·데이터 원본·검사 한계](../design/management-screen.md). dashboard/src/app/App.tsx, dashboard/src/features/github-status/data.ts, dashboard/src/features/github-status/data.test.ts, dashboard/scripts/snapshot.mjs, dashboard/scripts/build-snapshot.mjs (빌드 실패 시 저장본 검증), dashboard/scripts/snapshot-schema.mjs (화면·빌드 공통 검증), dashboard/scripts/github-snapshot.mjs (빌드·브라우저 공통 공개 조회), dashboard/src/features/github-status/snapshot-loader.ts, dashboard/src/features/github-status/snapshot-loader.test.ts (실패·취소·대체 자료) |
| 여러 에이전트로 동시 작업 | [작업 흐름의 공동 작업 규칙](../guides/development-workflow.md). 최신화·생성 파일·의미 충돌을 무엇이 강제하는지 표로 정리 |
| 에이전트 지침 변경·경로 검토 | [지침 보존 대조와 대표 작업](../design/agent-entrypoint.md). AGENTS.md는 진입점이며 정책 원본은 연결한 docs |
| 개발 작업 진행 | [작업 흐름](../guides/development-workflow.md), [정합성 검토](../consistency.md) |
| 세션 이어가기 | [다음 작업](../work-state.md) |
| 작업 완료 근거·개입·문제 확인 | [기록 기준과 실행 표](../work-results.md). dashboard/scripts/work-results.mjs가 docs 원본에서 화면 데이터를 생성합니다. dashboard/src/features/work-results/WorkResults.tsx와 dashboard/scripts/work-results.test.mjs를 함께 확인하고 미기록은 성공으로 세지 않습니다 |
| 작업 하나를 따라가기 | [작업 브리핑 양식과 목록](../briefings/index.md), [기존 합의와의 내용 검토](../consistency.md). 형식 검사는 tests/test_docs_consistency.py |
| 전체 진행 상황·방향 | [시스템 상태](../system-status.md). 단계별 상태를 바꾸면 지도와 표를 함께 고칩니다 |
| 개발 원칙·실행 평가 | [다섯 개발 원칙](../design/engineering-principles.md), [평가 기록](../record-forms/evaluation.md) |
| 정정 전체 자료·고정 정답 | [HD건설기계 개발용 사례](../cases/hd-construction-correction.md). tests/fixtures/corrections/hd-construction-2025, tests/test_correction_case.py. 전체 원문은 별도 데이터 커밋에 보존하며 기본 후보 v1은 두 후보를 보류하며 검증된 상위 최신 실행은 위 계약 참조 |
| 원본·정정공시 연결 조사 | [공식 근거·실제 원본/정정 한 쌍·검증 계획](../design/correction-linking.md). 조사 기록이며 연결·정정 선택 코드는 미구현 |
| 공시 후보 범위·근거 보존 | [공시 후보 계약](../specs/common-query-contract.md). src/dartness/disclosure_candidate.py, tests/test_disclosure_candidate.py. 같은 날짜의 여러 후보는 보류하고 수집·현금 추출 파일과 분리합니다 |
| 공통 날짜 입력·선택 코드 | [Python 계약 v1](../specs/common-query-contract.md). src/dartness/query_contract.py, tests/test_query_contract.py. 날짜 선택은 원문 선정·조건 판정이 아닙니다 |
| 공통 조회·시점·출력 합의 | [계약 초안](../specs/common-query-contract.md). 전수 범위·최신/지정일·개월 선택지·달력 계산·분할 조회 요구·정정·엑셀 옵션과 미구현 경계를 확인합니다 |
| 올인원 조회 유형·분기 설계 | [유형별 입력·결과·근거·미결](../specs/query-types.md), [공통/개별 책임](../design/architecture.md). 현금 외 모듈·라우터는 미구현 |
| 현금 표 추출 | [선정 구간의 지원 범위](../specs/cash-table-extraction.md). src/dartness/cash_table.py, tests/test_cash_table.py. 계정명 정리는 src/dartness/account_label.py, tests/test_account_label.py |
| 현금 조회 범위·계약 | [확정한 범위와 CASH-001~003](../specs/requirements.md#cash-scope), [규칙별 예시](../specs/cash-query-contract.md#examples), [Python 계약 v1과 한계](../specs/cash-query-contract.md). src/dartness/cash_contract.py, tests/test_cash_contract.py |
| 기능·데이터 계약 설계 | [요구사항](../specs/requirements.md), [판단 경계](../design/architecture.md) |
| 엑셀 양식·근거 표 바로가기 | [출력 예시](../specs/output-example.md), [구간 대조 기준](../specs/cash-report-slice.md#table-link). src/dartness/cash_viewer.py는 문서별 목차·뷰어 표를 대조하고 src/dartness/cash_workbook.py가 확인된 구간 링크를 사용합니다. tests/test_cash_viewer.py. 직접 연결 실패는 메모/JSON에 표시하며 현금 조건을 바꾸지 않습니다 |
| 문서·메모리 운영 | [운영 기준](../design/documentation.md). 문서 경로·규칙 ID·작업 상태 형식 검사는 tests/test_docs_consistency.py |
| 기술 후보 검토 | [초기 추천안](../design/development-environment-proposal.md) |

갱신 기준: 이 설정에서 생성한 docs 문서. 참조 문서가 바뀌면 관련 안내를 재검토합니다. 실제 구현이 추가되면 검증한 코드·테스트 위치를 연결합니다. 없는 파일을 예상 경로로 연결하지 않습니다.

<a id="amount"></a>
## 금액 처리 안내

AMOUNT-001의 기준은 [요구사항의 정확성과 근거](../specs/requirements.md#accuracy)입니다. 단위를 확인할 수 없는 금액은 추정하지 않고 확인 필요로 처리합니다. [현재 검토 상태](../consistency.md#amount-001)에서 구현 여부를 확인합니다. [금액 단위 처리](../specs/amounts.md)에 입력·출력과 지원 범위를 정의했습니다. 구현은 src/dartness/amounts.py, 검증은 tests/test_amounts.py입니다. 정상 변환은 공시 사실의 검증 완료를 뜻하지 않습니다.

## 실제 DART 수집 결과

[수동 검사 기록](../guides/dart-live-check.md)에서 헬릭스미스의 실제 접수번호 20260320001142와 ZIP·XML 해시를 확인할 수 있습니다. 원문 수집 성공이며 재무정보 추출 정답 검증은 아닙니다.

## DART 연동 방식

[외부 도구 사용 결정](../guides/dart-live-check.md)을 따릅니다. 외부 DART MCP·스킬·전용 래퍼는 도입하지 않고 공식 API를 직접 호출합니다. 범용 개발 도구는 계속 사용합니다.
## 실제 공시 자료

헬릭스미스 2025년 말 연결 자료를 [개발용 초안](../cases/helixmith-cash.md)으로 확인했습니다. 재무상태표는 원, 주석은 천원이며 두 값은 53원 차이가 있습니다. 사용자와 이번 53원 차이는 기본 표에서 경고하지 않고 내부 기록에 보존하기로 합의했습니다. 보편적인 자동 오차 판정은 아직 구현하지 않았습니다. 추출기가 이 자료를 통과했다고 해석하지 않습니다.
