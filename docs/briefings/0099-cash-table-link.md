---
pr: 99
issue: 98
date: 2026-11-25
stages: [I]
---

# 법인명을 누르면 근거 재무상태표 열기

## 한 줄 요약

공시 전체를 열던 법인명 링크를, 값 대조를 마친 재무상태표 구간으로 연결합니다.

## 지도에서의 위치

```mermaid
flowchart LR
    H[현금 금액 확인] --> V[목차와 실제 표 대조]
    V --> I[엑셀 법인명 링크]
    classDef changed fill:#dbeafe,stroke:#2563eb,stroke-width:3px
    class I changed
```

I의 근거 접근 개선이며 전수·최신 정정 선택은 기존 미완료 범위를 유지합니다.

## 무엇이 달라졌나

문서별 목차에서 법인·접수번호·재무 범위와 구간 인자를 읽습니다. 실제 구간의 기준일·원문 금액·단위를 기존 전체 원문 추출값과 대조한 경우에만 바로 연결합니다. 원래 공시 주소와 목차/구간 응답 해시는 별도 JSON에 보존합니다. 직접 확인 실패는 공시 전체 링크·메모의 미확인 표시와 실패 기록을 유지합니다.

## 누가 무엇을 정했나

사용자가 금액의 근거 표로 바로 이동하도록 요청했습니다. 에이전트는 기존 현금 추출 검사를 재사용하고 DART 웹 목차의 관찰된 형식만 지원했습니다. 새 의존성·정정 정책·금액 정답·검사 완화는 없습니다.

## 확인해 주세요

추가 결정은 없습니다. 표가 있는 구간을 여는 기능이며 특정 행 스크롤·강조를 보장하지 않습니다.

## 확인한 것과 못 한 것

대한약품 공식 목차와 재무상태표 응답을 확보해 2025-12-31 개별 현금 43,972,786,132원과 대조했습니다. 개발용 사례이며 미사용 검증용이 아닙니다. 다른 법인·접수번호·범위·금액·기간·단위·목차 중복·불완전 응답을 변형 테스트로 검사합니다. 실제 CLI의 네트워크 경로는 통제 응답으로 검사하고 PR CI에서 DART를 호출하지 않습니다. 모든 보고서 형식이나 Excel 데스크톱 환경의 호환성을 확인한 것은 아닙니다.

## 근거

- [PR #99](https://github.com/YUJAEYUN/Dartness/pull/99), [이슈 #98](https://github.com/YUJAEYUN/Dartness/issues/98)
- [구간 연결 기준](../specs/cash-report-slice.md#table-link), [출력](../specs/output-example.md)
- src/dartness/cash_viewer.py · tests/test_cash_viewer.py · tests/fixtures/cash/report-viewer/origin.json
