# 현금 조회 계약 초안

상태: 조회 범위·대체 금지·이유 구분은 사용자와 합의했습니다. 아래의 범위로 Python 입력·출력 계약과 생성 시 검증을 구현했습니다. 선정된 단순 HTML 구간의 [첫 추출 기능](cash-table-extraction.md)이 계약에 연결됐습니다. 전체 문서 추출기·외부 JSON 역직렬화·전체 조회 스키마는 아직 없습니다. 원본 기준은 [현금 조회 요구사항](requirements.md#cash-scope)입니다.

## 입력과 출력

| 구분 | 필요한 정보 |
|---|---|
| 입력 | 법인 식별자, 요청한 기준일, 법인 자체 또는 연결 범위, 금액 조건 |
| 확인된 값 | 원문 금액·통화·적용 단위, 정확히 변환한 금액, 재무 기준일, 실제 별도·개별·연결 구분 |
| 근거 | 공시 접수번호·원문 URL, 절·표·행·열 또는 위치, 사용한 원문 버전 |
| 확인 불가 | 이유, 확인한 경로·시각·원문 위치, 남은 확인 사항. 금액은 미확정이며 0원이 아님 |

기본 범위는 법인 자체입니다. 사용자 기준일·이전 자료·최신 정정·출력 정책은 [공통 계약](common-query-contract.md)에 합의했습니다. 조건 비교와 선택 엔진은 아직 없으며, 아래 CashQuery.as_of는 선정된 표의 실제 추출 대상 기준일입니다. Python 내부 필드와 상태 코드는 아래 v1에 정의합니다. 외부 API·JSON 형식은 아직 정하지 않았습니다.

## 실패와 확인 불가의 구분

| 상황 | 기대 처리 | 금지할 처리 |
|---|---|---|
| API에 값이 없음 | 원문 추가 확인이 필요하다고 기록 | 자료 자체가 없다고 확정 |
| 해당 공시에 재무제표가 없음 | 문서의 한계와 확인 위치 기록 | 법인 전체에 자료가 없다고 단정 |
| 요청 시점 자료를 못 찾음 | 확인한 시점과 요청 시점 구분 | 이전 기간 금액을 요청 시점 금액으로 표시 |
| 표·단위 해석 실패 | 추출 실패 이유와 원문 보존 | 단위 추정, 0원 처리 |
| 별도·개별 확인 불가, 연결은 존재 | 요청 범위를 유지하고 확인 불가 기록 | 연결 금액으로 자동 대체 |

조회 통신 장애는 자료 부재와 구분합니다. 확인 불가를 조건 미충족으로 단정하거나 누락시키는 정책도 아직 채택하지 않았습니다.

## 구현 전에 준비할 검증 사례

법인 자체 금액과 연결 금액이 다른 사례, 연결 없이 개별만 있는 사례, API 누락 후 원문에서 확인되는 사례, 요청 시점 부재, 단위 해석 실패를 준비합니다. 각 정답은 원문과 위치를 먼저 확인합니다. 별도·연결 두 개발용 금액은 확보했습니다. 연결 없이 개별만 있는 실제 법인과 API 누락 후 원문 확인 등의 실제 사례·추출 테스트는 아직 확보하지 않았습니다.

헬릭스미스 개발용 사례의 연결 금액은 연결 선택의 검증 자료로 유지합니다. 기본 범위가 바뀌었다고 기존 연결 정답을 별도 정답으로 바꾸지 않습니다. 이슈 #17에서 Python 계약 v1·실패 상태·고정 개발용 사례를 연결했습니다. 선정된 구간의 첫 추출은 이슈 #19에서 연결하며 범용 추출기는 후속 범위입니다.

## 계약 v1 — Python 경계

구현은 src/dartness/cash_contract.py입니다. Python dataclass 생성자가 값의 형태와 불변조건을 검사합니다. API 요청이나 후보 추출은 하지 않으며, 타입 검사만으로 런타임 입력을 믿지 않습니다.

| 타입 | 필드와 제약 |
|---|---|
| CashQuery | contract_version=cash-v1, corp_code=8자리 DART 법인 코드, as_of=명시한 날짜, scope=standalone 기본 또는 consolidated |
| CashEvidence | 공식 DART/KIND HTTPS URL, 전체 문서 SHA-256, 표·행·열 위치, 단위·시점·범위를 확인할 주변 문맥, 선택적 14자리 receipt_number |
| CashValue | query, basis=separate/individual/consolidated, as_of, raw_amount, 정확한 Decimal amount_krw, currency=KRW, evidence, status=value |
| CashNeedsReview | query, reason, 시간대 있는 checked_at, checked_path, detail, next_action, 선택적 evidence, status=needs_review. 금액 필드 없음 |

standalone은 separate·individual만, consolidated는 consolidated만 허용합니다. 결과 기준일은 해당 추출 요청(CashQuery.as_of)의 선정 기준일과 정확히 같아야 합니다. 원래 사용자 기준일과 이전 자료 선택 기록은 상위 계약에서 별도로 보존합니다. 잘못된 타입·시점·범위·금액을 전달하면 ValueError로 거절합니다. 지원 단위와 변환은 기존 금액 모듈을 사용합니다. 금액 조건과 환율·외화는 이번 계약에 포함하지 않습니다. 조건 비교 방식을 정하거나 금액 필터를 실행하지 않습니다.

확인 필요의 reason은 api_missing(API 누락, 원문 추가 확인), no_financial_statements(해당 문서에 재무제표 없음), period_unavailable(요청 시점 미확인), extraction_failed(해석·추출 실패), basis_unavailable(요청 범위 미확인), transport_error(통신 실패)입니다. 통신 실패와 자료 부재를 같은 이유로 기록하지 않습니다. 이런 결과는 금액이 없어 0원이나 조건 미충족으로 대신 표현할 수 없습니다.

status=value는 계약 형식의 통과를 뜻합니다. 원문에서 그 값이 실제 존재하는지, 해시·위치·문맥이 올바른지는 별도 원문 검증이 필요합니다. 생성자가 사실 검증을 수행하거나 허위 근거를 자동 탐지하지 않습니다. 명시적 원문 0원은 허용하지만 확인 불가 상태에는 금액 필드가 없습니다.

<a id="examples"></a>
## 규칙별 실행 예시

아래 예시는 tests/test_cash_contract.py가 읽어 계약 생성 결과와 비교합니다. 작성 규칙은 [문서 예시 테스트](testing.md#doc-examples)를 따릅니다. 규칙 원문은 [현금 조회 범위](requirements.md#cash-scope)입니다.

real-dev 금액은 헬릭스미스 개발용 사례에서 원문으로 먼저 확인한 값입니다(tests/fixtures/cash/helixmith-2025). evidence는 테스트가 넣을 개발용 근거를 고릅니다. modified는 실제 값을 다른 요청에 넣어 대체를 시도한 사례이고, synthetic은 실제 공시와 무관한 합성 사례입니다. 예시는 계약이 잘못된 대체를 거절하는지 확인할 뿐, 추출 정확도를 보여주지 않습니다.

<!-- dartness-example: cash-contract -->
```json
[
  {"id": "cash-consolidated-request-keeps-consolidated", "source": "real-dev",
   "input": {"kind": "value", "scope": "consolidated", "as_of": "2025-12-31",
             "basis": "consolidated", "result_as_of": "2025-12-31",
             "raw_value": "31,827,123,947", "unit": "원", "amount_krw": "31827123947",
             "evidence": "helixmith-consolidated"},
   "expect": {"status": "value", "basis": "consolidated", "amount_krw": "31827123947"}},
  {"id": "cash-standalone-keeps-separate", "source": "real-dev",
   "input": {"kind": "value", "scope": "standalone", "as_of": "2025-12-31",
             "basis": "separate", "result_as_of": "2025-12-31",
             "raw_value": "31,653,154,838", "unit": "원", "amount_krw": "31653154838",
             "evidence": "helixmith-separate"},
   "expect": {"status": "value", "basis": "separate", "amount_krw": "31653154838"}},
  {"id": "cash-standalone-rejects-consolidated", "rule": "CASH-001", "source": "modified",
   "input": {"kind": "value", "scope": "standalone", "as_of": "2025-12-31",
             "basis": "consolidated", "result_as_of": "2025-12-31",
             "raw_value": "31,827,123,947", "unit": "원", "amount_krw": "31827123947",
             "evidence": "helixmith-consolidated"},
   "expect": {"error": "ValueError", "message": "financial basis must match"}},
  {"id": "cash-unconfirmed-has-no-amount", "rule": "CASH-002", "source": "synthetic",
   "input": {"kind": "needs_review", "scope": "standalone", "as_of": "2025-12-31",
             "reason": "basis_unavailable"},
   "expect": {"status": "needs_review", "reason": "basis_unavailable", "amount_krw": null}},
  {"id": "cash-dash-is-not-zero", "rule": "CASH-002", "source": "synthetic",
   "input": {"kind": "value", "scope": "standalone", "as_of": "2025-12-31",
             "basis": "separate", "result_as_of": "2025-12-31",
             "raw_value": "-", "unit": "원", "amount_krw": "0",
             "evidence": "helixmith-separate"},
   "expect": {"error": "ValueError", "message": "exact normalization"}},
  {"id": "cash-other-period-rejected", "rule": "CASH-003", "source": "modified",
   "input": {"kind": "value", "scope": "consolidated", "as_of": "2025-12-31",
             "basis": "consolidated", "result_as_of": "2024-12-31",
             "raw_value": "31,827,123,947", "unit": "원", "amount_krw": "31827123947",
             "evidence": "helixmith-consolidated"},
   "expect": {"error": "ValueError", "message": "financial date must match"}}
]
```

## 계약 검증의 실제 범위

tests/test_cash_contract.py는 기존 연결 재무상태표와 새 별도 재무상태표 개발용 값을 사용합니다. 확인한 KIND 전체 원문 해시는 기존 기록과 같았습니다. 해당 값은 원문에서 먼저 읽었으며 계약 생성자의 출력으로 정답을 만들지 않았습니다. 개별재무제표 허용·API 누락·통신 장애·단위 제거 등은 명시적으로 합성한 경계 사례입니다. 실제 공시에서 그런 장애가 있었다는 뜻이 아닙니다.

이 검사는 원문에서 추출한 후보를 이후 코드가 잘못 바꾸거나 범위·시점이 다른 값을 결과로 확정하는 것을 막기 위한 첫 경계입니다. 원문 수집부터 추출까지의 정확도를 검증한 것은 아닙니다.

receipt_number는 확인한 DART 접수번호만 기록합니다. KIND 문서와 DART 문서의 버전 관계를 확인하지 못한 경우 번호를 추정해 넣지 않고 비워 둡니다. 관련 DART 접수번호가 있다는 것과 두 문서의 전체 내용이 같다는 것은 별개입니다.
