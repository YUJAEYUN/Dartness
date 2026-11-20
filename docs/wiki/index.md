# LLM 위키 진입점

이 페이지는 기준 문서를 찾아주는 지도입니다. 독립적인 규칙 원본이 아닙니다.

| 작업 | 먼저 읽을 문서 |
|---|---|
| DART 실제 수집 | [수동 검사와 범위](../dart-live-check.md) |
| CI·브랜치 설정 | [검사와 설정 방법](../ci.md) |
| 개발 작업 진행 | [작업 흐름](../development-workflow.md), [정합성 검토](../consistency.md) |
| 세션 이어가기 | [다음 작업](../work-state.md) |
| 기능·데이터 계약 설계 | [요구사항](../requirements.md), [판단 경계](../architecture.md) |
| 엑셀 양식 조정 | [출력 예시](../output-example.md) |
| 문서·메모리 운영 | [운영 기준](../documentation.md) |
| 기술 후보 검토 | [초기 추천안](../development-environment-proposal.md) |

갱신 기준: 이 설정에서 생성한 docs 문서. 참조 문서가 바뀌면 관련 안내를 재검토합니다. 실제 구현이 추가되면 검증한 코드·테스트 위치를 연결합니다. 없는 파일을 예상 경로로 연결하지 않습니다.

<a id="amount"></a>
## 금액 처리 안내

AMOUNT-001의 기준은 [요구사항의 정확성과 근거](../requirements.md#accuracy)입니다. 단위를 확인할 수 없는 금액은 추정하지 않고 확인 필요로 처리합니다. [현재 검토 상태](../consistency.md#amount-001)에서 구현 여부를 확인합니다. [금액 단위 처리](../amounts.md)에 입력·출력과 지원 범위를 정의했습니다. 구현은 src/dartness/amounts.py, 검증은 tests/test_amounts.py입니다. 정상 변환은 공시 사실의 검증 완료를 뜻하지 않습니다.

## 실제 DART 수집 결과

[수동 검사 기록](../dart-live-check.md)에서 헬릭스미스의 실제 접수번호 20260320001142와 ZIP·XML 해시를 확인할 수 있습니다. 원문 수집 성공이며 재무정보 추출 정답 검증은 아닙니다.
