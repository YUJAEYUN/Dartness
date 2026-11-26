---
pr: 105
issue: 101
date: 2026-11-26
stages: [B, C]
---

# 추가 정정·철회를 확인할 공시 이력 받기

## 한 줄 요약

지정 법인의 제출일 구간에서 모든 공시 유형을 최대 10회 요청으로 수집합니다.

## 지도에서의 위치

```mermaid
flowchart LR
    B[법인·공시 제출일 구간] --> C[모든 유형·월·페이지 수집]
    C --> N[정정 근거와 이력 연결은 다음 단계]
    classDef changed fill:#dbeafe,stroke:#2563eb,stroke-width:3px
    class B,C changed
```

목록 수집 완전성과 최신 유효 정정 선택은 구분합니다.

## 무엇이 달라졌나

기존 collect_list의 정정 포함·월 분할·전체 페이지·중복/누락 검사를 재사용합니다. 법인 하나를 명시하며 유형/시장 필터로 이력을 잘라내지 않습니다. 각 응답의 파라미터·원문 바이트·해시와 수집 시각을 저장하고 실패 구간을 정상 빈 이력으로 바꾸지 않습니다.

## 누가 무엇을 정했나

사용자가 기존 기준 안의 작업을 위임했습니다. 에이전트는 최신 정정 판단에 필요한 원천을 준비하는 수집 모드만 추가했습니다. 기본 annual/exact_receipts·기존 권한/시크릿/의존성·조회/정답 기준은 유지합니다.

## 확인해 주세요

새 결정 요청은 없습니다. 실제 이력의 내용·미지원 버전·철회/첨부 영향과 최신 유효성은 수집 뒤 별도로 검증합니다. 이슈 #101은 미완료 조건이 남으면 닫지 않습니다.

## 확인한 것과 못 한 것

고정 응답으로 월 분할·정정 포함 N·유형/시장 필터 배제·예산·부분 실패·CLI 모드를 검사합니다. 일반 CI는 실제 API를 호출하지 않습니다. API 응답 완전성만으로 회사의 정정 관계나 금액을 확정하지 않습니다.

## 근거

- [PR #105](https://github.com/YUJAEYUN/Dartness/pull/105), [이슈 #101](https://github.com/YUJAEYUN/Dartness/issues/101)
- [수집 계약](../guides/dart-live-check.md#filing-history), [기존 목록 완전성](../specs/disclosure-list.md)
- src/dartness/dart_history.py · tests/test_dart_history.py
