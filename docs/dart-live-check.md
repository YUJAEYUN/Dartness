# DART 실제 수집 검사

이슈 #9의 수동 연동 검사입니다. 사용자에게 등록받은 DART_API_KEY를 Actions 환경변수로만 사용합니다. 일반 PR CI에서는 키 없이 고정 응답 테스트만 실행합니다.

## 검사 범위

1. corpCode.xml에서 종목코드 084990인 헬릭스미스의 법인코드를 확인합니다.
2. list.json에서 2026.03.20에 접수된 사업보고서 (2025.12)를 찾습니다. 다른 날짜·보고서를 자동 대체하지 않습니다.
3. 후보가 정확히 하나인 경우 document.xml에서 원문 ZIP을 내려받고 비어 있지 않은 XML 파일 존재를 확인합니다.

정상 실행은 요청 3회입니다. 최대 다운로드 32MiB, ZIP 내부 총크기 128MiB, 파일 수 100개, HTTP 요청별 제한시간 30초, Actions 작업 제한시간 5분을 둡니다. 자동 재시도와 페이지 추가 조회는 없으며 예상 밖의 결과는 실패로 표시합니다. 이것은 첫 수집 경로 검사이지 전체 법인용 클라이언트나 캐시 구현이 아닙니다.

원문 ZIP과 각 XML의 SHA-256, 실제 DART 접수번호·법인코드·공시일·출처 링크를 기록합니다. 보고서 이름에서 읽은 2025.12와 원문에서 검증한 재무 기준일을 혼동하지 않습니다. 재무 기준일·연결/별도·금액·정정 관계는 아직 검증하지 않습니다.

## 실행

저장소 Settings → Secrets and variables → Actions에 DART_API_KEY를 등록합니다. Actions의 Check code → Run workflow에서 대상 브랜치와 dart_smoke=true를 선택합니다. 기본값은 false입니다. main에 이미 있는 workflow_dispatch를 작업 브랜치에서도 실행할 수 있도록 같은 워크플로에 수동 작업을 추가했습니다.

명령으로 실행할 때는 다음과 같습니다. 시크릿 값은 명령에 넣지 않습니다.

```bash
gh workflow run code.yml --ref feat/9-dart-smoke -f dart_smoke=true
```

병합 후에는 --ref main으로 실행합니다. 사용자 요청이 있을 때만 수동 실행하며 PR·예약 실행에서 실제 DART를 호출하지 않습니다. 기존 code-quality 필수 검사는 유지하고 dart-smoke는 외부 서비스 장애를 이유로 일반 PR을 막지 않도록 별도로 둡니다.

## 실패와 키 보호

키 누락·형식 오류, 인증 오류, IP 제한, 자료 없음, 요청 제한, 점검, 네트워크·HTTP 실패를 구분합니다. 원래 예외 메시지·인증키 포함 URL·서버 메시지는 출력하지 않습니다. HTTP 리다이렉트는 차단합니다. 응답·산출물에 키가 포함됐는지 검사하고 발견되면 저장하지 않습니다.

API 인증 실패는 추출 결과가 없다는 뜻이 아닙니다. 자료 없음과 원문 누락도 성공으로 기록하지 않습니다. 구체적인 실패 원인을 확인한 후 필요한 수정만 수행합니다.

## 결과와 보관

성공하면 dart-smoke-실행번호 아티팩트에 manifest.json과 document.zip을 3일 보관합니다. 공개 저장소의 아티팩트 접근 범위를 고려해 이 검사는 공개 공시만 대상으로 하며 내부 목록은 넣지 않습니다. 원문·키·생성 결과를 Git에 자동 커밋하지 않습니다. work/는 Git에서 제외합니다.

manifest의 collected는 수집 성공입니다. LLM 해석, 재무금액 정답 검증, KIND와 DART 원문의 동등성까지 확인했다는 뜻은 아닙니다. 실제 API 실행 결과는 PR·이슈 기록으로 남기며 성공 전에는 유효한 키라고 단정하지 않습니다.

## 오프라인 테스트

tests/test_dart_smoke.py에서 가짜 응답으로 회사·보고서 일치, 페이지 누락 방지, 오류 상태, XML/ZIP 실패, 비밀값을 노출하지 않는 오류 처리를 확인합니다. 이 테스트가 실제 DART 서비스의 정상 동작을 보증하지는 않습니다.

## 공식 가이드

- [공시 검색](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001)
- [공시 원문 ZIP](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019003)
- [고유번호 목록](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019018)

## 관련 초안

[PR #8](https://github.com/YUJAEYUN/Dartness/pull/8)의 테스트 절차와 KIND 정답 초안은 아직 사용자 검토 중입니다. 이번 작업이 해당 정답·오차 허용 기준을 확정하지 않습니다.

## 개발자 문서를 관리하는 범위

이번에 사용하는 공식 규격은 2026-11-20에 확인했습니다. 전체 개발자 문서를 복제하거나 임베딩하지 않고, 아래 호출에 필요한 규격과 공식 링크를 보관합니다.

| API | 이번 코드에서 확인한 계약 |
|---|---|
| corpCode.xml | crtfc_key, ZIP의 list/corp_code·corp_name·stock_code |
| list.json | corp_code·bgn_de·end_de·pblntf_detail_ty·last_reprt_at·page_count, status·total_page·list |
| document.xml | rcept_no, 성공 시 ZIP·실패 시 XML 상태 응답 |

API 키의 값은 문서·테스트에 적지 않습니다. 계약·응답이 달라지면 공식 문서를 다시 확인하고 문서·코드·테스트를 함께 고칩니다. 저장한 규격을 최신이라고 영구 가정하지 않습니다.

개발 에이전트가 규격을 확인하는 과정과 조회 에이전트가 도구를 실행하는 과정을 구분합니다. 실제 조회 때마다 웹검색으로 엔드포인트·필드를 만들어내지 않습니다. API가 늘면 필요한 규격을 추가하고 공식 문서 링크를 찾는 비용이 커질 때 문서 검색·임베딩의 필요성을 평가합니다. MCP는 API 호출 인터페이스의 후보이며 공식 규격 원본이나 재무 해석 검증을 대체하지 않습니다.

## 실제 실행 결과

2026-11-20의 [수동 실행](https://github.com/YUJAEYUN/Dartness/actions/runs/44653561475)이 성공했습니다. 실행한 수집 코드의 커밋은 225f7f7이며 이후 변경은 문서 기록입니다.

- 법인: 헬릭스미스, corp_code 00359395.
- 보고서: 사업보고서 (2025.12), 접수일 2026.03.20.
- 실제 접수번호: **20260320001142**.
- [DART 문서 링크](https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260320001142).
- API 요청 3회, XML 파일 3개가 들어 있는 ZIP 수집.
- [수집 기록](evidence/dart-20260320001142.json)에 ZIP·XML 해시와 크기를 보관.

Actions 아티팩트를 내려받아 ZIP의 SHA-256이 기록과 같은지 확인했습니다. 키·인증키 포함 요청 URL·원문 ZIP은 Git에 저장하지 않았습니다. 인증키가 이 실행에서 사용 가능했음을 확인했지만 향후 유효성까지 보장하지 않습니다. 재무 기준일·숫자·연결/별도·정정 관계와 KIND 원문의 동등성은 이 실행에서 검증하지 않았습니다.
