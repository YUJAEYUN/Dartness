---
pr: 71
issue: 69
date: 2026-11-24
stages: []
---

# GitHub 조회 장애와 사이트 배포 분리

## 한 줄 요약

GitHub 최신 상태 조회가 실패해도 유효한 저장본이 있으면 사이트를 배포합니다. 작업 현황의 최신 여부는 화면에서 따로 표시합니다.

## 지도에서의 위치

관리 화면 배포 수정입니다. DART 조회·판정 기준에는 변화가 없습니다.

## 무엇이 달라졌나

기존에는 빌드 중 GitHub 조회가 실패하면 배포를 중단했습니다. 이제 화면과 같은 검증을 통과한 저장본이 있으면 원래 내용과 확인 시각을 유지하고 경고 후 배포합니다. 저장본 누락·잘못된 형식·변조된 링크·파일 쓰기 오류는 계속 빌드를 실패시킵니다. 화면은 열기·다시 확인 시 최신 조회를 시도합니다.

## 누가 무엇을 정했나

**사용자가 정한 것**

- GitHub 조회 실패가 사이트 수정 배포를 막지 않도록 유효한 저장본 대체 배포를 승인했습니다.

**구현 중 에이전트가 정한 것**

- 화면의 기존 자료 검증을 공통 모듈로 옮겨 빌드에서도 재사용했습니다.
- 수동 저장 명령의 실패 처리와 일반 CI의 외부 조회 금지, 기존 검사·권한·의존성은 유지했습니다.

## 확인해 주세요

추가 결정은 없습니다. 운영 배포 결과 확인 전에는 이슈를 종료하지 않습니다.

## 확인한 것과 못 한 것

로컬에서 조회 실패·정상 갱신·잘못된 최신 응답·저장본 누락·변조·쓰기 실패·CI 외부 조회 금지를 검사했습니다. HTTP 403의 상세 원인은 제공된 로그만으로 확인할 수 없으며, 공개 API의 가용성을 보장하지 않습니다. 운영 결과는 이슈와 PR에서 확인합니다.

## 근거

- PR: [#71](https://github.com/YUJAEYUN/Dartness/pull/71) · 이슈: [#69](https://github.com/YUJAEYUN/Dartness/issues/69)
- 기준: [관리 화면](../design/management-screen.md)
- 구현: dashboard/scripts/build-snapshot.mjs, dashboard/scripts/snapshot-schema.mjs
- 검사: dashboard/scripts/build-snapshot.test.mjs, dashboard/src/features/github-status/data.test.ts
