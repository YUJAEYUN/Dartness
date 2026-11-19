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
- 현재는 사용자 승인 후 에이전트가 병합합니다. 자동 병합은 켜지 않습니다.

## 설정 방법과 확인 결과

처음에는 관리 API 권한 부족으로 보호 규칙 조회·변경과 자동 삭제 설정 변경이 HTTP 403으로 거부됐습니다. 이후 사용자가 2026-11-19에 설정 완료를 알려주었습니다. 자동 브랜치 삭제가 true인 것은 API로 확인했습니다. 보호 규칙의 세부 값은 관리 권한 제한으로 직접 확인하지 못했으며 사용자 확인을 근거로 기록합니다.

1. **Settings → General → Pull Requests**에서 **Automatically delete head branches**를 켭니다.
2. **Settings → Branches**에서 main 보호 규칙을 확인하거나 추가합니다. 기존 규칙이 있으면 중복 생성하지 말고 충돌 여부를 확인합니다.
3. **Require a pull request before merging**을 켜고 **Require approvals**는 끕니다.
4. **Require status checks to pass before merging**을 켜고 이 저장소 GitHub Actions의 **build** 검사를 선택합니다.
5. **Require branches to be up to date before merging**을 켭니다.
6. 관리자 우회도 막는 **Do not allow bypassing the above settings**를 켭니다. **Allow force pushes**, **Allow deletions**는 끕니다.
7. 저장 후 설정 화면을 다시 확인합니다. Rulesets를 이미 사용 중이면 같은 목적의 규칙을 그곳에서 관리하고 두 방식의 규칙이 충돌하지 않게 합니다.

설정 확인을 위해 main에 직접 push하거나 실패한 변경을 병합하는 실험은 하지 않습니다. 정상 PR에서 최신 검사와 병합 가능 상태를 확인합니다. PR #4의 설정 설명과 완료 기록이 병합되면 이슈 #3을 종료합니다.

PR #1의 원격 작업 브랜치 docs/development-workflow는 병합 사실을 확인한 뒤 삭제했습니다. 병합 코드와 PR 기록은 남아 있습니다.

## Check code 추가

이슈 #5에서 `.github/workflows/code.yml`을 추가합니다. Python 3.12에서 고정된 requirements-dev.txt를 설치하고, Ruff 린트·포맷, mypy strict, pytest를 실행합니다. PR과 main 변경, 수동 실행으로 동작하며 작업 이름은 **code-quality**입니다.

현재는 단위 변환 코드와 테스트를 검사합니다. 문서의 금액 예시도 테스트가 실행합니다. API·LLM 호출은 없으며 구조 의존성 검사기는 아직 필요하지 않아 추가하지 않았습니다. 일반적인 이름·길이 제한이나 커버리지 목표는 강제하지 않습니다.

2026-11-19 사용자가 기존 build와 함께 code-quality를 main 보호의 필수 검사로 추가했다고 확인했습니다. 관리 API 권한 제한으로 세부 설정을 직접 조회하지 못했으므로 사용자 확인을 근거로 기록합니다. 두 검사의 성공 여부는 PR에서 별도로 확인합니다.
