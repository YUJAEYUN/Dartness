---
pr: 115
issue: 114
date: 2026-11-26
stages: [F]
---

# 최신 공시의 잘못된 입력 거절 확인

## 한 줄 요약

최신 현금 공시 선택에서 잘못된 기간·본문 근거를 받아들이지 않는지 테스트를 보강합니다.

## 지도에서의 위치

```mermaid
flowchart LR
    F[잘못된 입력·보류 사유 검증] --> R[금액과 선택 결과 없음 확인]
    classDef changed fill:#dbeafe,stroke:#2563eb,stroke-width:3px
    class F changed
```

## 무엇이 달라졌나

합성 입력의 결함 10개와 잘못된 금액 조건 3개를 추가했습니다. 원문 누락·기간 충돌·목록 메타데이터 충돌·선택 날짜 없음·중복/잘못된 시각의 본문·정정 표시 충돌·표 날짜 초과를 정확한 사유로 보류하는지 확인합니다. 금액이나 선택 공시가 생기지 않는지도 검사합니다.

## 누가 무엇을 정했나

사용자가 중요한 미실행 분기부터 보강하는 방향에 동의했습니다. 기존 최신 공시 선택 계약을 기준으로 검사하며 제품 코드·판정 기준·기존 정답·의존성·CI·검사 제외는 바꾸지 않습니다.

## 확인해 주세요

추가 결정 요청은 없습니다. 이번 자료는 합성 실패 사례이며 새로운 실제 공시 독립 평가가 아닙니다.

## 확인한 것과 못 한 것

추가 13개 테스트를 통과했습니다. 전체 회귀·분기 측정·CI·병합 후 확인 근거는 이슈와 PR에 기록합니다. 높은 커버리지가 공시 내용의 정확성을 증명하지는 않습니다. 모든 정정 유형·모든 방어 분기를 검증한 것으로 표시하지 않습니다.

## 근거

- [PR #115](https://github.com/YUJAEYUN/Dartness/pull/115), [이슈 #114](https://github.com/YUJAEYUN/Dartness/issues/114)
- [최신 공시 선택 계약](../specs/latest-cash-source.md), [테스트 가이드](../guides/testing.md#latest-source-guards)
- tests/test_latest_cash_guards.py, src/dartness/latest_cash.py
