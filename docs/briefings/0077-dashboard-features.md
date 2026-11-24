---
pr: 77
issue: 76
date: 2026-11-24
stages: []
---

# 대시보드 파일을 기능별로 모으기

## 한 줄 요약

화면 조립·개별 기능·공통 UI·공통 자료를 나누고 기존 테스트에서 참조 방향을 검사합니다.

## 지도에서의 위치

관리 화면 코드 정리입니다. DART 처리 단계·도메인 기준·화면 디자인은 바뀌지 않았습니다.

## 무엇이 달라졌나

app은 화면을 조립하고 features는 GitHub 현황·시스템 상태·브리핑·작업 결과를 맡습니다. components의 흐름도와 shared의 저장소 주소·자료 계약을 함께 사용해 기능끼리 직접 참조하지 않습니다. 테스트는 해당 기능 옆에 둡니다. scripts·generated·Vercel 루트와 출력 경로는 유지합니다.

## 누가 무엇을 정했나

**사용자가 정한 것**

- docs 다음으로 대시보드 코드를 기능별로 정리합니다.
- 기존 구조를 활용하고 동작을 유지합니다.

**구현 중 에이전트가 정한 것**

- 브리핑과 시스템 상태가 쓰는 Flowchart를 공통 UI로 분리하고 기본 흐름도는 호출하는 화면에서 전달했습니다.
- 기능 간 참조·공통 모듈의 역참조·허용하지 않은 src 밖 상대 참조를 기존 Vitest에서 검사합니다.
- TypeScript 7에 예전 JavaScript 파서 API가 없어 기존 Vite가 제공하는 Oxc 파서를 사용했습니다. 새 의존성은 추가하지 않았습니다.
- 빌드와 브라우저가 공유하던 공개 조회·자료 검증 두 연결은 명시적으로 유지했습니다.

## 확인해 주세요

추가 결정은 없습니다. 이번 정리는 Python 기능 세분화나 새 기능 구현이 아닙니다. AGENTS.md 운영 방향 검토는 이번 작업을 마친 뒤 별도로 진행합니다.

## 확인한 것과 못 한 것

| 확인한 것 | 못 한 것 |
|---|---|
| 기존 조회·대체 자료·표시 테스트 유지, 실제 src의 참조 경로 검사 | 모든 순환 참조와 좋은 추상화의 자동 판정 |
| 타입 import·재내보내기·동적 import도 경계 검사, 계산형 경로 거절 | 코드 배치만으로 도메인 정확성 보증 |
| 문서·위키·브리핑·타입 선언의 경로 갱신 | 모든 모바일 화면·디자인 검토 |

운영 화면과 실제 조회 확인은 이슈·PR에 남깁니다.

## 근거

- PR: [#77](https://github.com/YUJAEYUN/Dartness/pull/77) · 이슈: [#76](https://github.com/YUJAEYUN/Dartness/issues/76)
- 기준: [대시보드 코드 배치](../design/dashboard-structure.md)
- 검사: dashboard/scripts/architecture.mjs, dashboard/scripts/architecture.test.mjs
- 조립: dashboard/src/app/App.tsx · 공통 흐름도: dashboard/src/components/Flowchart.tsx
