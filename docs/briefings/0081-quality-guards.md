---
pr: 81
issue: 80
date: 2026-11-24
stages: []
---

# 예외 처리와 새 검사 우회를 CI에서 확인

## 한 줄 요약

예외 처리 린트를 보강하고 PR에서 새 검사 무시·테스트 비활성·명시적 Any를 실제 구문으로 비교합니다.

## 지도에서의 위치

개발 코드 품질 검사 보강입니다. DART 처리 기준·정답·위임 권한을 바꾸지 않았습니다.

## 무엇이 달라졌나

Ruff가 포괄 예외 잡기·예외 후 pass/continue·포괄 또는 불필요한 검사 무시를 검사합니다. PR의 기준/작업 커밋에서 Python·JS/TS의 알려진 우회 구문을 비교하고 추가되면 code-quality가 실패합니다. 기존 테스트의 명시적 무시는 유지하며 새 패키지·권한은 추가하지 않았습니다. 설정·검사기 변경은 실행 요약에 표시합니다.

## 누가 무엇을 정했나

**사용자가 정한 것**

- AGENTS.md에 당부를 늘리기보다 예외 처리·검사 우회를 린트·테스트·CI로 막습니다.

**구현 중 에이전트가 정한 것**

- BLE001·S110·S112·PGH003·PGH004·RUF100을 추가하고 구체 예외 후 pass/continue도 검사하는 옵션을 켰습니다.
- 기존 정당한 type-ignore·noqa·형식 유지 주석은 기준 커밋과 비교해 보존합니다. 새 Any·skip/xfail/only/todo 등 알려진 구문은 파서로 찾습니다.
- Git rename을 연결하고 문자열 예시는 제외합니다. 코드나 Git을 읽지 못하면 정상으로 처리하지 않습니다.
- 설정 변경 보고는 승인 인증이 아닙니다. 실제 필요가 있는 새 예외는 별도 검토가 필요하며 몰래 기준을 낮추지 않습니다.

## 확인해 주세요

추가 결정은 없습니다. 보안 규칙 전체 활성화·복잡도 임계값·독립 승인 시스템·정답 변경 전체 보호는 이번 범위가 아닙니다.

## 확인한 것과 못 한 것

| 확인한 것 | 못 한 것 |
|---|---|
| 실제 Ruff 반례 거부와 정상 구체 예외 처리 허용 | 모든 의미상 잘못된 예외 처리를 정적으로 판정 |
| Python/JS 별칭·문자열·재배치·새 우회·구문 오류·Git 비교·실행 상태 검사 | 동적 호출·기존 예외 재활용·기존 assert/정답 약화의 완전 탐지 |
| 기준 커밋과 비교한 설정 변경 보고·원본 정답 유지 | 에이전트와 사람의 권한 분리 또는 독립 승인 인증 |

실제 CI·운영 브리핑 확인은 이슈·PR에 남깁니다. 통과 자체가 코드 품질 보증은 아닙니다.

## 근거

- PR: [#81](https://github.com/YUJAEYUN/Dartness/pull/81) · 이슈: [#80](https://github.com/YUJAEYUN/Dartness/issues/80)
- 기준: [예외 처리와 검사 우회](../guides/quality-guards.md), [위임](../guides/delegation.md)
- 구현: scripts/check_quality_changes.py, dashboard/scripts/quality-markers.mjs
- 검사: tests/test_quality_changes.py, tests/test_exception_lint.py, dashboard/scripts/quality-markers.test.mjs
