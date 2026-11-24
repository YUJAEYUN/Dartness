# 문서 CI와 main 보호 설정

## Check docs가 하는 일

설정 파일은 `.github/workflows/docs.yml`입니다. 워크플로 이름은 **Check docs**, 실제 필수 검사로 선택할 작업 이름은 **build**입니다. GitHub 화면에서는 Check docs / build처럼 보일 수 있습니다.

1. Ubuntu 실행 환경에서 저장소를 받습니다.
2. Python 3.12를 설치하고 pip 다운로드 캐시를 준비합니다.
3. requirements-docs.txt에 고정한 문서 패키지를 설치합니다.
4. `python -m mkdocs build --strict`로 docs와 mkdocs.yml을 사이트로 변환합니다.
5. site/ 결과물을 documentation-preview 아티팩트로 저장합니다. 웹 게시 작업은 아닙니다.

PR에서는 기본적으로 GitHub가 만든 임시 병합 결과를 검사합니다. main에 push되면 다시 검사합니다. 수동 실행과 매주 월요일 오전 9시(한국 시간) 예약 실행도 있습니다.

## 검사 범위

| 확인하는 것 | 확인하지 않는 것 |
|---|---|
| 문서 빌드·설정 오류, 설정된 탐색·링크 검사에서 발생한 경고 | 문서·위키·코드의 의미 일치 |
| 의존성 설치와 사이트 생성 | DART 추출 정확성, 타입·회귀 테스트 |
| 경고 발생 시 strict 빌드 실패 | Mermaid의 브라우저 렌더링, 실제 화면 가독성, 외부 링크 상태 |

모든 마크다운 오류를 잡는 린터는 아닙니다. 로그의 INFO 항목까지 모두 실패로 처리하지 않습니다. PR에서 build가 성공했어도 기준 변경과 검사 우회 여부는 리뷰합니다.

## 확인한 실행

2026-11-19, 병합 커밋 `8e8a36ccf983a3bbc29a66a611075ab00c3cdae2`의 [main 실행](https://github.com/YUJAEYUN/Dartness/actions/runs/44465690212)이 성공했습니다. build의 의존성 설치·엄격한 빌드·아티팩트 저장 단계가 모두 성공했습니다.

## 적용할 보호 규칙

사용자와 합의한 설정입니다. 아래 설정을 문서에 적는 것만으로 활성화되지는 않습니다.

- main 변경은 PR로 진행합니다.
- build 검사 통과와 최신 main 반영을 요구합니다.
- 협업자가 본인 한 명이므로 타인의 승인은 필수로 요구하지 않습니다.
- main의 강제 push와 삭제를 막습니다. 관리자에게도 규칙을 적용합니다.
- 병합한 작업 브랜치는 자동 삭제합니다. 로컬 브랜치·worktree는 미커밋 작업과 사용 여부를 확인한 뒤 정리합니다.
- [위임 범위](delegation.md)에 따라 일반 작업은 필수 검사 통과 후 에이전트가 병합합니다. 기준 변경과 예외는 사용자 확인을 받습니다. 상시 자동 병합 봇은 켜지 않았습니다.

## 설정 방법과 확인 결과

처음에는 관리 API 권한 부족으로 보호 규칙 조회·변경과 자동 삭제 설정 변경이 HTTP 403으로 거부됐습니다. 이후 사용자가 2026-11-19에 설정 완료를 알려주었습니다. 자동 브랜치 삭제가 true인 것은 API로 확인했습니다. 보호 규칙의 세부 값은 관리 권한 제한으로 직접 확인하지 못했으며 사용자 확인을 근거로 기록합니다. 2026-11-23 사용자가 "병합 전 브랜치 최신화 요구"가 켜져 있음을 다시 확인했습니다. 여러 에이전트 작업에서 이 설정이 최신 main 반영을 강제합니다([작업 흐름](development-workflow.md)).

1. **Settings → General → Pull Requests**에서 **Automatically delete head branches**를 켭니다.
2. **Settings → Branches**에서 main 보호 규칙을 확인하거나 추가합니다. 기존 규칙이 있으면 중복 생성하지 말고 충돌 여부를 확인합니다.
3. **Require a pull request before merging**을 켜고 **Require approvals**는 끕니다.
4. **Require status checks to pass before merging**을 켜고 이 저장소 GitHub Actions의 **build** 검사를 선택합니다.
5. **Require branches to be up to date before merging**을 켭니다.
6. 관리자 우회도 막는 **Do not allow bypassing the above settings**를 켭니다. **Allow force pushes**, **Allow deletions**는 끕니다.
7. 저장 후 설정 화면을 다시 확인합니다. Rulesets를 이미 사용 중이면 같은 목적의 규칙을 그곳에서 관리하고 두 방식의 규칙이 충돌하지 않게 합니다.

설정 확인을 위해 main에 직접 push하거나 실패한 변경을 병합하는 실험은 하지 않습니다. 정상 PR에서 최신 검사와 병합 가능 상태를 확인합니다. PR #4의 설정 설명과 완료 기록이 병합되면 이슈 #3을 종료합니다.

PR #1의 원격 작업 브랜치는 병합 사실을 확인한 뒤 삭제했습니다. 병합 코드와 PR 기록은 남아 있습니다.

## Check code 추가

이슈 #5에서 `.github/workflows/code.yml`을 추가합니다. Python 3.12에서 고정된 requirements-dev.txt를 설치하고, Ruff 린트·포맷, mypy strict, pytest를 실행합니다. PR과 main 변경, 수동 실행으로 동작하며 작업 이름은 **code-quality**입니다.

현재는 단위 변환 코드와 테스트를 검사합니다. 문서의 금액 예시도 테스트가 실행합니다. API·LLM 호출은 없으며 구조 의존성 검사기는 아직 필요하지 않아 추가하지 않았습니다. 일반적인 이름·길이 제한이나 커버리지 목표는 강제하지 않습니다.

2026-11-19 사용자가 기존 build와 함께 code-quality를 main 보호의 필수 검사로 추가했다고 확인했습니다. 관리 API 권한 제한으로 세부 설정을 직접 조회하지 못했으므로 사용자 확인을 근거로 기록합니다. 두 검사의 성공 여부는 PR에서 별도로 확인합니다.

## 수동 DART 연동 작업

Check code의 dart_smoke 입력을 true로 지정한 수동 실행에만 별도 dart-smoke 작업을 추가합니다. 실제 요청과 산출물·오류 처리의 범위는 [DART 실제 수집 검사](dart-live-check.md)를 따릅니다. 일반 PR에서는 실행하지 않으며 code-quality는 그대로 실행합니다. 새로운 필수 검사 등록은 필요하지 않습니다.

## 관리 화면 검사

이슈 #13에서 기존 code-quality에 Node.js 24·npm ci·UI 린트·Vitest·TypeScript strict·Vite 빌드를 추가했습니다. package-lock.json을 사용하고 dashboard/dist/를 management-dashboard 아티팩트로 7일 보관합니다. 별도 필수 검사 설정이나 권한 확대는 없습니다. 일반 CI는 GitHub를 재조회하지 않고 저장된 스냅샷으로 빌드합니다. Vercel 빌드는 공개 API에서 새 스냅샷을 생성하고 조회 실패 시 빌드도 실패합니다. 브라우저는 같은 공개 조회 모듈을 재사용해 화면 열기/다시 확인 시 조회하며, 네트워크·호출 제한 실패 시 저장본/직전 자료를 유지합니다. 조회/대체 자료 시각과 검증 한계는 [관리 화면](../design/management-screen.md)에 명시합니다.

## docs와 대시보드 생성물 검사

code-quality가 UI 빌드 전에 `npm run docs:check`를 실행합니다. 시스템 상태 원본과 커밋된 생성 JSON이 다르면 실패하며 빌드의 자동 재생성으로 그 실패를 숨기지 않습니다. 생성기와 경계 사례는 UI Vitest에서 실행합니다. 로컬 훅 설치와 검사 한계는 [관리 화면](../design/management-screen.md)에 있습니다. 필수 검사 이름·권한·기존 검사·정답은 바꾸지 않았습니다.

## 이슈 조기 종료 방지

PR 본문의 자동 종료 문구는 scripts/check_pr_policy.py가 거절합니다. PR 편집 이벤트에도 code-quality를 다시 실행해 본문만 바꿔도 검사합니다. 이 검사는 PR 본문의 자동 종료 경로를 차단하며, 실제 완료 조건의 충족 여부까지 판단하거나 GitHub에서 사람이 직접 닫는 동작을 막지는 않습니다. 본문과 체크리스트를 먼저 확인한 뒤 별도로 종료합니다.

기능·명세 PR의 작업 브리핑은 scripts/check_briefing_required.py가 확인합니다. code-quality는 이 검사를 위해 전체 이력을 받아(fetch-depth: 0) PR 기준 커밋과의 변경 파일을 비교합니다. 대상 경로와 작성 방법은 [작업 브리핑](../briefings/index.md)에 있습니다. 브리핑 파일이 있는지만 확인하며, 요약이 PR과 같은 뜻인지는 확인하지 않습니다.

## 이슈 하나에 열린 PR 하나

scripts/check_issue_claim.py가 PR 본문의 `Refs #번호`를 그 PR이 맡은 이슈로 읽습니다(이슈 #55). 다음 경우 code-quality가 실패합니다.

- 먼저 열린(번호가 더 작은) 다른 열린 PR이 같은 이슈를 맡고 있을 때. 초안 PR도 셉니다. 먼저 연 PR은 실패하지 않습니다.
- `Refs #번호`가 서로 다른 이슈로 두 개 이상일 때. 관련 이슈는 '관련: #번호'처럼 적습니다.
- 기능·명세 PR([작업 브리핑](../briefings/index.md)의 대상)인데 `Refs #번호`가 없을 때.

열린 PR 목록을 읽기 위해 code-quality 작업에 `pull-requests: read` 권한을 주고 Actions 기본 토큰을 씁니다. 쓰기 권한은 없습니다. 먼저 연 PR이 닫혀도 뒤의 PR 검사는 자동으로 다시 돌지 않으므로, 본문을 편집하거나 push해서 다시 실행합니다. PR을 열기 전에 겹친 작업은 감지하지 못합니다. 이슈 본문에 적은 담당 에이전트와 실제 작업자가 같은지도 확인하지 않습니다.
