---
pr: 109
issue: 108
date: 2026-11-26
stages: [B, F, I]
---

# 저장 파일과 조건만으로 조회 결과 재현

## 한 줄 요약

임시 Python 조립 스크립트 없이 기존 수집 파일에서 최신 현금 조회와 JSON·엑셀까지 연결합니다.

## 지도에서의 위치

```mermaid
flowchart LR
    B[저장 이력·공시 파일 읽기] --> F[요청·원시 응답·해시·경로 검증]
    F --> I[기존 최신 선택과 JSON·엑셀 연결]
    classDef changed fill:#dbeafe,stroke:#2563eb,stroke-width:3px
    class B,F,I changed
```

## 무엇이 달라졌나

기존 annual/exact_receipts/filing_history 산출물을 검증해 기존 조회 객체로 연결합니다. 명시한 날짜·금액 조건으로 기존 최신 선택을 실행하고 JSON·세 열 엑셀을 만듭니다. 표 HTML도 있으면 기존 링크 대조를 재사용합니다. API/웹을 새로 호출하지 않으며 저장 정책을 새로 정하지 않습니다.

## 누가 무엇을 정했나

사용자는 기존 기준 안의 구현·검증을 위임했습니다. 선정·판정 기준, 기존 정답, 의존성·권한·CI 완화는 없습니다. 개발자용 재현 명령이며 최종 비전공자용 템플릿/UI 형식을 확정한 것은 아닙니다.

## 확인해 주세요

추가 결정 요청은 없습니다. 단일 법인의 지정 이력 자료를 재현하는 경로입니다. 전수 수집·캐시 보관 정책·모든 정정 유형·제품 전체 E2E는 미완료입니다. 결과 파일이 이미 있으면 보호하고 새 출력 경로를 요구합니다.

## 확인한 것과 못 한 것

수집 요약과 원시 응답 충돌, 경로 이탈, ZIP/멤버/본문 선언 불일치, 중복·미완료 수집과 로딩 실패의 확인 필요 처리를 검사했습니다. 기존 동진쎄미켐 자료로 최신·2025말 지정 조회의 날짜·금액·표 링크·엑셀을 재현했습니다. 이미 읽은 자료의 재현이며 새 독립 평가로 세지 않습니다. 실제 Excel 데스크톱 렌더링은 확인하지 않았습니다.

## 근거

- [PR #109](https://github.com/YUJAEYUN/Dartness/pull/109), [이슈 #108](https://github.com/YUJAEYUN/Dartness/issues/108)
- [명령·입출력·실패·한계](../specs/cash-bundle-runner.md), [추가 법인 평가](../evaluations/latest-cash-dongjin-2026.md)
- src/dartness/collection_bundle.py, src/dartness/cash_bundle_runner.py, tests/test_collection_bundle.py
