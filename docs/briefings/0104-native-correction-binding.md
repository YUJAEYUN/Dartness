---
pr: 104
issue: 101
date: 2026-11-26
stages: [B, C, D, F]
---

# 전체 XML 정정표와 실제 현금 셀 대조

## 한 줄 요약

공식 API로 받은 두 전체 원문의 사업기간·정정표·현금 셀을 웹 근거와 연결해 비교합니다.

## 지도에서의 위치

```mermaid
flowchart LR
    C[전체 원문 ZIP] --> B[사업기간·정정표와 웹 대조]
    B --> D[실제 현금 셀 재추출]
    D --> F[기존 관계·금액 계약 검증]
    classDef changed fill:#dbeafe,stroke:#2563eb,stroke-width:3px
    class B,C,D,F changed
```

최신 유효 버전 선택과 전체 이력 확인은 다음 단계입니다.

## 무엇이 달라졌나

COVER의 속성·표시 날짜를 함께 읽고 CORRECTION 안의 최초 제출일·변경 문구를 웹과 대조합니다. 정정 근거에 전체 XML 해시를 연결하고 두 CashValue를 원문에서 직접 추출해 기존 관계/비교 계약에 전달합니다. 다른 파일·기간·회사·정정표 충돌은 확인 필요입니다. 금액이 다르더라도 기업 오류나 선택 결과로 단정하지 않습니다.

## 누가 무엇을 정했나

사용자가 기존 기준 안에서 계속 진행하도록 위임했습니다. 에이전트는 등록된 키로 원본·정정 두 건을 확보하고 기존 PDF/XBRL 정답과 대조했습니다. 기존 단위·범위·동률·ReportVersion v1 기간 제약과 테스트 정답은 유지합니다.

## 확인해 주세요

새 결정 요청은 없습니다. v1은 사업기간 밖 비교기간의 정정 검증을 보류합니다. 기존 조회의 과거 열 추출을 금지하거나 다른 날짜로 대체하지 않습니다. 이슈 #101은 전체 이력·최신 유효성 조건이 남아 열어 둡니다.

## 확인한 것과 못 한 것

실제 두 전체 ZIP·본문 해시·회사와 사업기간·정정표를 확인했습니다. HD건설기계 2025년 말 별도 69,787,650,000원, 연결 337,873,166,000원이 두 버전에서 같으며 기존 정답은 수정하지 않았습니다. 이미 본 개발용 사례입니다. 날짜/파일/기간/정정표/금액 변형과 잘못된 시간 입력을 구분해 검사하며, 다른 법인·전체 이력·철회·첨부·다중 차수 검증은 아닙니다.

## 근거

- [PR #104](https://github.com/YUJAEYUN/Dartness/pull/104), [이슈 #101](https://github.com/YUJAEYUN/Dartness/issues/101)
- [전체 원문 연결 기준](../specs/correction-evidence.md#native-binding), [기존 정답](../cases/hd-construction-correction.md)
- src/dartness/native_report.py · src/dartness/correction_binding.py · tests/test_native_correction.py
