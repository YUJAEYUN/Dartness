---
pr: 102
issue: 101
date: 2026-11-26
stages: [B, C]
---

# 실제 본문 관계와 정정표를 코드로 대조

## 한 줄 요약

DART의 양쪽 본문 목록과 정정표를 직접 읽어 원본·정정의 식별 정보와 변경 문구를 보존합니다.

## 지도에서의 위치

```mermaid
flowchart LR
    B[원본·정정 본문 목록] --> C[정정표 위치·날짜·문구 대조]
    C --> N[전체 원문·금액 영향 연결은 다음 단계]
    classDef changed fill:#dbeafe,stroke:#2563eb,stroke-width:3px
    class B,C changed
```

이슈 #101의 첫 연결입니다. 최신 유효 정정 적용 완료가 아닙니다.

## 무엇이 달라졌나

첨부와 통합 목록을 제외하고 양쪽 본문 목록의 법인·접수번호·날짜·표시를 대조합니다. 정정 목차가 지정한 구간에서 대상 서류·최초 제출일·정정일·변경 항목/사유/전후를 읽습니다. 목록 불일치·중복·다른 위치·불완전 표·통신 실패를 성공으로 숨기지 않습니다. 추가 본문도 모두 보존합니다.

## 누가 무엇을 정했나

사용자가 다음 정정 연결 단계 진행을 승인했습니다. 에이전트는 준비된 입력 검증 전에 필요한 실제 웹 근거 읽기를 구현했습니다. 기존 선정/보류·원화 정답·CI·의존성·권한은 유지합니다. 공통 목차 읽기는 재무상태표 바로가기와 함께 재사용합니다.

## 확인해 주세요

새 결정 요청은 없습니다. 이슈 #101은 전체 원문·항목 영향·최신 유효성 조건이 남아 계속 열어 둡니다.

## 확인한 것과 못 한 것

HD건설기계의 2026-11-23 공식 저장 응답을 기존 해시·수동 대조 정답과 비교했습니다. 개발용이며 새 관측/미사용 평가가 아닙니다. 최대 3회 수집은 고정 응답으로 검사하며 일반 CI의 실제 DART 호출은 없습니다. 웹 구간 해시는 전체 PDF/XML 해시가 아니며 최신본·현금 불변이나 오류를 확정하지 않습니다.

## 근거

- [PR #102](https://github.com/YUJAEYUN/Dartness/pull/102), [이슈 #101](https://github.com/YUJAEYUN/Dartness/issues/101)
- [관측 기준](../specs/correction-evidence.md#viewer-observation), [기존 실제 사례](../cases/hd-construction-correction.md)
- src/dartness/correction_observation.py · src/dartness/correction_html.py · tests/test_correction_observation.py
