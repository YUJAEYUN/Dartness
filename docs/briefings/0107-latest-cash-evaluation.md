---
pr: 107
issue: 101
date: 2026-11-26
stages: [B, D, F, H, I]
---

# 최신 공시 선택을 다른 법인에서도 확인

## 한 줄 요약

구현을 고정한 뒤 다른 법인의 원문과 요청 5개를 대조했고 모두 기대 결과와 같았습니다.

## 지도에서의 위치

```mermaid
flowchart LR
    B[전체 이력·유효 문서 선택] --> D[당기·비교열 읽기]
    D --> F[기대 날짜·범위·단위·값 대조]
    F --> H[금액 조건 충족·미충족 확인]
    H --> I[근거 링크와 세 열 엑셀 확인]
    classDef changed fill:#dbeafe,stroke:#2563eb,stroke-width:3px
    class B,D,F,H,I changed
```

## 무엇이 달라졌나

제품 코드를 고정한 상태에서 동진쎄미켐의 실제 이력 26건과 정기보고서 4개로 실행했습니다. 원문에서 정답을 먼저 기록했고 기준일 지정·최신, 별도·연결, 금액 조건 미충족을 대조했습니다. 공식 재무상태표 링크와 엑셀 숫자/서식/미충족 행 제외도 확인했습니다.

## 누가 무엇을 정했나

사용자는 기존 최신 유효 공시 기준의 구현을 위임했습니다. 새 제품 기준·의존성·권한·기존 정답·CI 완화는 없습니다. 평가를 통과시키려고 제품 코드를 바꾸지 않았습니다.

## 확인해 주세요

추가 결정 요청은 없습니다. 새 법인 한 곳에서 나온 관련 요청 5개이며 회사 5곳이나 M1 전수 E2E 성공으로 해석하지 않습니다. 이슈 #101은 모든 완료 조건과 병합·배포 근거를 대조한 뒤 처리하며 M1 전체는 진행 중입니다.

## 확인한 것과 못 한 것

기대값과 선정 접수번호·날짜·단위·금액·조건 판정은 5개 모두 일치했습니다. 최신 별도 값은 2026-09-30 기준 166,741,090,356원이며 500억원 조건은 충족하고 2,000억원 조건은 미충족입니다. 데스크톱 Excel 렌더링·모바일 UI·전체 상장법인 전수·합계·금융업/외화·모든 정정 유형은 검증하지 않았습니다.

## 근거

- [PR #107](https://github.com/YUJAEYUN/Dartness/pull/107), [이슈 #101](https://github.com/YUJAEYUN/Dartness/issues/101)
- [평가 방법·원문 값·한계](../evaluations/latest-cash-dongjin-2026.md), [기대값 고정과 실제 결과 기록](https://github.com/YUJAEYUN/Dartness/blob/main/docs/evidence/dongjin-latest-cash-2026.json)
- [최신 선택 계약](../specs/latest-cash-source.md), [M1](https://github.com/YUJAEYUN/Dartness/milestone/1)
