# 대시보드 코드 배치

상태: 2026-11-24 사용자와 합의한 기능별 정리 방향을 적용합니다. 화면 동작·조회·대체 자료·문서 기준·디자인은 유지하고 위치와 참조 방향을 정리합니다. [Bulletproof React](https://github.com/alan2207/bulletproof-react/blob/master/docs/project-structure.md)의 기능별 배치와 단방향 참조를 필요한 범위에서 참고합니다.

## 파일을 둘 위치

| 위치 | 책임 |
|---|---|
| dashboard/src/app | App과 화면 전체 스타일. 기능을 조립하고 화면 수준 상태를 관리 |
| dashboard/src/features/github-status | 공개 GitHub 상태 로딩·실패·시점·검사 결과 처리와 테스트 |
| dashboard/src/features/project-status | docs에서 생성한 시스템 상태 화면 |
| dashboard/src/features/briefings | 브리핑 화면·자료 처리·테스트 |
| dashboard/src/features/work-results | 작업 결과 화면 |
| dashboard/src/components | 여러 화면이 쓰는 Button·Flowchart |
| dashboard/src/shared | 저장소 주소·원본 기준 커밋·공통 GitHub 자료 타입/검증 연결 |
| dashboard/src/generated | docs에서 생성한 JSON. 직접 수정하지 않음 |
| dashboard/src/main.tsx·dashboard/src/index.css | Vite 진입점과 전역 스타일 |

위 표의 경로는 저장소 루트 기준입니다. scripts는 빌드·문서 생성·공개 조회 스크립트로 유지합니다. Root Directory dashboard, 출력 dist와 기존 명령은 바꾸지 않습니다. 기능 하나에 파일 하나뿐이어도 그 기능에 속하면 해당 폴더에 두고, 아직 필요 없는 api·hooks·types 하위 폴더는 만들지 않습니다.

## 참조 방향

App은 기능과 공통 모듈을 참조합니다. 기능은 자기 기능과 components·shared·generated를 참조할 수 있지만 다른 기능·app을 참조하지 않습니다. components와 shared는 기능·app을 참조하지 않습니다. 공통 자료를 쓰려고 다른 기능에서 타입만 가져오는 참조도 금지합니다. 공통 타입은 shared에 둡니다. components와 shared 사이 참조는 허용하되 순환 구조는 설계·리뷰에서 피합니다. 기능을 연결하는 조립은 app에서 합니다.

예외는 이미 빌드와 브라우저가 공유하던 스크립트 두 개뿐입니다. shared/snapshot.ts는 scripts/snapshot-schema.mjs의 검증을 재사용하고, features/github-status/snapshot-loader.ts는 scripts/github-snapshot.mjs를 재사용합니다. 이외의 src 밖 상대 import는 허용하지 않습니다. Node 빌드가 브라우저 화면을 실행하지 않도록 scripts의 타입 선언은 공통 자료 타입만 가리킵니다.

## 자동 검사와 한계

기존 Vite가 제공하는 Oxc 파서로 src의 정적 import·재내보내기·문자열 동적 import·import type 경로를 읽고 Vitest에서 참조 방향을 검사합니다. 대상이 없는 상대 경로와 분석할 수 없는 계산형 동적 import도 실패합니다. 테스트 파일도 같은 경계로 검사합니다. 기존 npm test와 CI에서 실행하며 새 패키지나 CI 권한을 추가하지 않습니다.

이 검사는 구조 경계를 확인할 뿐 좋은 추상화·이름·도메인 정확성·모든 순환 참조를 보증하지 않습니다. 기능 분리는 파일 수가 아니라 함께 바뀌는 책임을 기준으로 하고, 동작은 기존 테스트와 운영 확인으로 대조합니다. 이 정리는 Python 모듈 세분화가 아닙니다.
