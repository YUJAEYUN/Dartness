---
pr: 97
issue: 95
date: 2026-11-25
stages: [I]
---

# 참고 파일처럼 간결한 엑셀 표 배치

## 한 줄 요약

사용자 참고 파일의 흰 바탕·상단 정보 한 줄·2행 머리글·3행 데이터 배치로 맞춥니다. 왼쪽 정렬·10포인트와 근거 보존은 유지합니다.

## 지도에서의 위치

```mermaid
flowchart LR
    H[조건 비교] --> I[엑셀 결과]
    classDef changed fill:#dbeafe,stroke:#2563eb,stroke-width:3px
    class I changed
```

I의 서식 변경이며 전수·최신 정정 적용 지원 범위를 바꾸지 않습니다.

## 무엇이 달라졌나

색상 머리글·큰 여백을 기본 표로 바꾸고 틀 고정/필터를 적용합니다. 날짜와 범위를 한 줄로 표시하고 세 열의 금액·원문 링크·메모는 유지합니다. 조회일은 한국 시간이며 자료 기준일과 구분합니다.

## 누가 무엇을 정했나

사용자가 기존 파일과 비슷한 형식을 요청했습니다. 에이전트는 서식만 참고하고 첨부의 회사·팀별 목록·분류 내용을 제품이나 저장소에 복사하지 않았습니다.

## 확인해 주세요

추가 결정은 없습니다. 기존 세 열과 원문 대조 기능을 유지합니다.

## 확인한 것과 못 한 것

기존 테스트의 셀 주소·표시 줄바꿈을 새 배치에 맞추고 금액·날짜·근거·수식 방지·조건 미충족 제외 검사를 유지합니다. 재생성 파일의 배치·서식을 확인하며 모든 Excel 데스크톱 환경을 검증한 것은 아닙니다.

## 근거

- [PR #97](https://github.com/YUJAEYUN/Dartness/pull/97), [이슈 #95](https://github.com/YUJAEYUN/Dartness/issues/95)
- [출력 양식](../specs/output-example.md), [지정 공시 실행](../specs/cash-report-slice.md)
- 구현: src/dartness/cash_workbook.py · 기존 검사: tests/test_cash_workbook.py
