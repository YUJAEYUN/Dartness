---
pr: 103
issue: 101
date: 2026-11-26
stages: [C]
---

# 지정한 원본·정정의 전체 원문 받기

## 한 줄 요약

접수번호를 명시해 원본·정정 제출서류 ZIP을 최대 두 건 받습니다.

## 지도에서의 위치

```mermaid
flowchart LR
    B[확인할 두 접수번호] --> C[전체 제출서류 수집]
    C --> N[전체 원문·실제 금액 연결]
    classDef changed fill:#dbeafe,stroke:#2563eb,stroke-width:3px
    class C changed
```

정정 관계·최신본 선택을 수행하는 단계는 아닙니다.

## 무엇이 달라졌나

기존 수동 수집에서 exact_receipts를 명시하면 document.xml만 최대 두 번 요청합니다. 연간 원본 평가 수집 기본 동작은 유지합니다. 본문이 없거나 한 건이라도 실패하면 완료된 묶음으로 저장하지 않습니다. ZIP 내부의 인증키도 검사합니다.

## 누가 무엇을 정했나

사용자가 기존 기준 안에서 계속 진행하도록 위임했습니다. 에이전트는 실제 정정 근거 연결에 필요한 수집 방식을 추가했습니다. 기존 시크릿·권한·의존성·원화 정답과 선택 정책은 유지합니다.

## 확인해 주세요

추가 결정은 없습니다. 실제 수집·검증 결과는 이슈 #101에 남기고, 전체 원문 바인딩·최신 유효성 조건이 남으면 이슈를 닫지 않습니다.

## 확인한 것과 못 한 것

고정 응답으로 요청 제한·지정 본문·부분 실패·모드 혼동·압축 내 키 노출을 검사했습니다. 일반 CI는 실제 DART를 호출하지 않습니다. complete는 지정 묶음 수집만 뜻하며 전체 이력 완전성·정정 관계·금액의 검증 결과가 아닙니다. 기존 annual 경로도 회귀 검사합니다.

## 근거

- [PR #103](https://github.com/YUJAEYUN/Dartness/pull/103), [이슈 #101](https://github.com/YUJAEYUN/Dartness/issues/101)
- [수집 범위와 실행](../guides/dart-live-check.md#exact-receipts)
- src/dartness/dart_receipts.py · src/dartness/dart_collect.py · tests/test_dart_receipts.py
