---
pr: 96
issue: 95
date: 2026-11-25
stages: [I]
---

# 엑셀 왼쪽 정렬·10포인트와 눈금 표시

## 한 줄 요약

사용자 요청대로 엑셀의 제목·머리글·본문·링크를 왼쪽 정렬·10포인트로 통일하고 눈금선을 표시합니다.

## 지도에서의 위치

```mermaid
flowchart LR
    H[조건 비교] --> I[엑셀 결과]
    classDef changed fill:#dbeafe,stroke:#2563eb,stroke-width:3px
    class I changed
```

I의 서식만 변경합니다. 지정 공시 단계의 한계는 유지합니다.

## 무엇이 달라졌나

숨겼던 눈금선을 다시 표시합니다. 셀을 삭제한 것은 아니며 금액·날짜·범위·원문 링크·메모는 유지합니다.

## 누가 무엇을 정했나

사용자가 왼쪽 정렬·10포인트를 요청했습니다. 에이전트는 빈 공간이 하얗게 보인 원인이 눈금선 숨김임을 확인하고 표시를 복원했습니다.

## 확인해 주세요

추가 결정은 없습니다. 기존 세 열과 근거 보존을 유지합니다.

## 확인한 것과 못 한 것

재생성 XLSX의 값·링크·메모·서식과 기존 검사를 확인합니다. 실제 Excel 데스크톱의 모든 표시 환경을 검사한 것은 아닙니다.

## 근거

- [PR #96](https://github.com/YUJAEYUN/Dartness/pull/96), [이슈 #95](https://github.com/YUJAEYUN/Dartness/issues/95)
- [출력 예시](../specs/output-example.md), [지정 공시 실행](../specs/cash-report-slice.md)
- 구현: src/dartness/cash_workbook.py
