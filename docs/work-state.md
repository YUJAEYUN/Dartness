# 다음 작업

이 문서는 다음 세션이 시작할 위치입니다. 기준은 관련 docs이며 검사·완료 근거는 이슈·PR에 연결합니다. 과거 완료 작업을 진행 중으로 나열하지 않습니다.

## 현재 상태

- 최종 비전은 [다섯 조회 유형](specs/query-types.md)을 지원하는 올인원 법인 조회입니다. 현금은 첫 기능이며 나머지 유형을 폐기하거나 현금으로 대신하지 않습니다.
- 현재 제품 목표는 [M1: 상장법인 현금 조건 조회와 근거 포함 엑셀](https://github.com/YUJAEYUN/Dartness/milestone/1)입니다. 금액은 사용자 입력이며 500억원은 시범값입니다. 정책 원본은 [요구사항](specs/requirements.md), [공통 계약](specs/common-query-contract.md)입니다.
- 모집단·공시 목록 연결은 구현했고 [실제 실행 결과](guides/listed-live-check.md)도 대조했습니다. 이는 현금 전수 조회나 독립 거래소 명부 검증 완료가 아닙니다.
- [공통 입력·날짜·후보 선택](specs/common-query-contract.md), [금액 변환](specs/amounts.md), [현금 값 계약](specs/cash-query-contract.md), [선정 구간 추출](specs/cash-table-extraction.md)을 재사용합니다.
- [원본·정정 근거](specs/correction-evidence.md)와 [현금 두 셀 비교](specs/correction-cash-comparison.md)는 준비된 입력의 검사입니다. 자동 근거 추출·유효 차수·최종 금액 적용은 아직 없습니다. 이슈 #86·#88·#90은 완료 종료했고 해당 근거는 이슈·브리핑에 있습니다.
- 실제 현금 추출 평가의 범위·개발용 전환은 [첫 평가](evaluations/cash-table-dart-2025.md), [두 번째 평가](evaluations/cash-table-dart-2025-second.md), [세 번째 평가](evaluations/cash-table-dart-2025-third.md)를 봅니다.

- [지정 공시 실행](specs/cash-report-slice.md)의 원문 구역 선정·현금 검증·조건 비교·세 열 엑셀/근거 JSON 구현과 검사를 마쳤습니다(이슈 #92 / PR #93). 최종 병합·배포 근거는 이슈에서 확인하며 전수·최신 유효 정정 완료와 구분합니다.
- 코드 경로는 src/dartness/report_section.py, src/dartness/cash_report.py, src/dartness/cash_report_result.py, src/dartness/cash_workbook.py이고 검사는 tests/test_cash_report.py, tests/test_cash_workbook.py입니다. 사용자 승인으로 openpyxl·타입 스텁을 추가했고 기존 정답·엄격한 타입/CI 검사는 유지합니다.

## 진행 중인 작업

- M1은 진행 중입니다. 다음 연결 작업은 이슈 #94의 실제 원문 후보 생성과 기준일 자료 선택입니다. PR #93 병합 후 이어갑니다. 지정 공시 결과를 최종 전수 결과로 간주하지 않습니다.

## 다음에 정할 것

- 이슈 #94에서 실제 원문 날짜/후보를 공통 요청·선택 계약과 연결한 뒤 최신 유효 정정·상장법인 전수 실행으로 확대합니다. 이 과정에서 실제로 막히는 요구사항만 사용자에게 제시합니다.
- 템플릿으로 조건을 입력하고 엑셀로 결과를 받는 방향은 이미 정했습니다. 별도 웹 입력 화면을 필수 전제로 다시 결정받지 않습니다.
- 금액 조건의 전수 선정·최신 정정 적용·합계 판정·전수 결과 엑셀/독립 E2E 평가는 M1의 남은 범위입니다. 한 법인의 성공으로 Milestone을 닫지 않습니다.
- 금융업 현금 기준(이슈 #57)은 보류입니다. 현금및현금성자산 행이 없으면 확인 필요를 유지하며 지금 다시 결정을 요구하지 않습니다.
- 외화 공시 및 원화 공시의 12월이 아닌 결산 법인 값 추출 확인(이슈 #67)은 기존 보류를 유지합니다. 문제가 생기면 근거와 함께 다룹니다.

## 알려진 한계

- 새 구역 선정은 명시적 DART 태그가 있는 지원 서식만 처리합니다. 범용 의미 추출·보고서 유형 전체·독립 명부 완전성·유효 정정 선택·전수 원문 수집·캐시·환율·합계·제품 최종 엑셀은 아직 완료하지 않았습니다.
- 원문에서 추출 가능한 입력과 최종 법인 선정 자격을 구분합니다. 지정 문서 비교는 최신 자료·정정 검증 완료가 아닙니다.
- 기존 [품질 검사](guides/quality-guards.md)·[위임 정책](guides/delegation.md)·[작업 흐름](guides/development-workflow.md)을 유지합니다. 실행 중인 상시 봇이나 별도 오케스트레이터는 없습니다.
- 자동 문서 검사는 경로·형식·생성물 일치를 확인하며 의미 일치는 [정합성 검토](consistency.md)가 필요합니다. 관리 화면의 상세 모바일/디자인 검사는 기존 합의대로 보류입니다.
