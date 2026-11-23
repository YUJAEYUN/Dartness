# 재무상태표 구간에서 현금 읽기 — 첫 버전

## 지원 범위

입력은 법인·보고서·연결/별도/개별 범위를 상위 단계가 확인해 선정한 HTML 구간입니다. 제목과 기간·단위 표, 그 다음 금액 표 두 개를 포함합니다. 이번 구현은 선정된 표 안에서 현금 행·요청 날짜 열·단위를 읽습니다. 전체 보고서에서 해당 절을 자동 선정하거나 법인·범위를 자동 판정하지 않습니다.

처음 지원하는 구조는 기간 표의 `제 N 기 YYYY.MM.DD 현재`, 단위 표의 `(단위 : 원)` 등 기존 지원 원화 단위, 금액 표 첫 행의 `제 N 기` 열과 `현금및현금성자산` 행입니다. 표 칸은 HTML의 `<TD>`·`<TH>`와 DART 원문 XML의 `<TE>`를 같은 방식으로 읽습니다. 계정명 뒤에 붙은 주석 번호(`(주4,29)`처럼 "주"와 숫자·쉼표만 든 괄호 하나)는 허용합니다. "현금및현금성자산 등"처럼 다른 말이 붙은 계정명은 현금 행으로 보지 않습니다. HTMLParser로 셀·행을 나누고 명시한 기간 형식만 인식합니다. 복잡한 표를 평탄화해 첫 숫자를 선택하지 않습니다.

## 입력과 출력

`extract_cash_table(query, html_section, basis, evidence, checked_at)`는 기존 CashValue 또는 CashNeedsReview를 반환합니다. evidence는 전체 원문 URL·해시·선정한 절 위치를, basis는 상위 단계가 확인한 실제 재무 범위를 전달합니다. checked_at은 시간대가 있는 확인 시각입니다. 이 입력 메타데이터의 진실성을 자동 검증한 것으로 해석하지 않습니다.

- 기간 표의 제목이 입력 범위와 맞는지 확인합니다. 연결은 연결 재무상태표, 별도·개별은 재무상태표 제목을 요구합니다. 이 확인만으로 별도와 개별을 자동 구분하지는 않습니다.
- 요청 날짜와 일치하는 기간을 찾고 해당 기간 이름과 같은 머리글 열을 선택합니다. 전기·전전기라고 제외하지 않고 요청 날짜에 따라 고릅니다.
- 요청 범위와 입력 basis가 다르면 basis_unavailable, 명시된 기간 중 요청 날짜가 없으면 period_unavailable로 남깁니다.
- 기간·단위·행/열 누락·중복·모순, 병합/중첩/미완성 셀, 지원하지 않는 형식은 extraction_failed입니다. 자료 부재나 0원으로 확정하지 않습니다.
- 두 표 이외의 표와 256KiB를 넘는 구간은 지원하지 않습니다. rowspan·colspan은 1만 허용합니다. 모호한 후보 중 하나를 임의로 고르지 않습니다.
- 값은 기존 단위 변환·현금 계약을 거칩니다. 근거에는 선정 구간 내 표·행·열(1부터 시작), 기간·단위 원문과 입력 basis를 보존합니다. 인덱스는 전체 보고서 기준이 아닙니다.

주석 세부내역·합계 대조·정정 공시 선택·XBRL·PDF·LLM·다른 법인 서식 자동 일반화는 이번 범위가 아닙니다. 메타데이터를 잘못 전달하거나 원문 자체가 틀린 경우까지 이 파서가 탐지하지는 않습니다.

## 검증 자료

헬릭스미스 원문 해시가 기존 기록과 일치하는 저장 자료에서 별도·연결 재무상태표의 전체 두 표 구간을 발췌했습니다. balance-sections.json은 발췌 해시·전체 문서 해시·선정 위치를 기록합니다. 두 원문 구간은 개발용이며 같은 법인의 같은 서식입니다. 날짜·단위 제거, 중복 현금 행, 병합 셀 등은 테스트에서 생성하는 변형 입력이며 실제 공시 결함이 아닙니다.

정답은 기존 원문 대조 값에서 가져오며 추출 함수 출력으로 만들지 않습니다. 원문 표에서 값을 읽는 첫 테스트이지만 수집·절 선정·모든 법인에 대한 종단 정확도를 검증하지 않습니다.

## 다른 법인 평가 결과

2026-11-23 DART 2025 사업보고서 6곳(11건)으로 처음 평가했습니다. 첫 실행에서는 틀린 금액은 없었지만 DART 원문 XML을 하나도 읽지 못했습니다. 원문이 표 셀을 `<TE>`로 쓰고, 일부 법인은 계정명 뒤에 "(주4,29)" 같은 주석 번호를 붙였기 때문입니다. 같은 날 두 형식을 지원하도록 고쳤고, 11건 모두 원문에서 정답을 읽습니다. 이 11건은 이제 개발용이므로, 정확도는 새 법인으로 다시 평가해야 합니다. 자세한 내용은 [평가 기록](evaluations/cash-table-dart-2025.md)에 있습니다.

## 실행하는 문서 예시

real-dev는 기존 원문 대조 값과 별도·연결 HTML 구간을 사용합니다. modified는 구간의 단위를 제거하거나 요청 범위를 바꾸는 테스트 입력입니다. 파서 출력으로 기대값을 만들지 않았습니다.

<!-- dartness-example: cash-table -->
```json
[
  {"id": "table-separate-current", "source": "real-dev",
   "input": {"section": "separate", "scope": "standalone", "as_of": "2025-12-31"},
   "expect": {"status": "value", "basis": "separate", "as_of": "2025-12-31", "amount_krw": "31653154838"}},
  {"id": "table-consolidated-current", "source": "real-dev",
   "input": {"section": "consolidated", "scope": "consolidated", "as_of": "2025-12-31"},
   "expect": {"status": "value", "basis": "consolidated", "as_of": "2025-12-31", "amount_krw": "31827123947"}},
  {"id": "table-missing-unit", "rule": "AMOUNT-001", "source": "modified",
   "input": {"section": "separate", "scope": "standalone", "as_of": "2025-12-31", "remove_unit": true},
   "expect": {"status": "needs_review", "reason": "extraction_failed", "amount_krw": null}},
  {"id": "table-request-basis-mismatch", "rule": "CASH-001", "source": "modified",
   "input": {"section": "consolidated", "scope": "standalone", "as_of": "2025-12-31"},
   "expect": {"status": "needs_review", "reason": "basis_unavailable", "amount_krw": null}},
  {"id": "table-request-period-missing", "rule": "CASH-003", "source": "modified",
   "input": {"section": "separate", "scope": "standalone", "as_of": "2026-12-31"},
   "expect": {"status": "needs_review", "reason": "period_unavailable", "amount_krw": null}}
]
```

## 이전 자료 정책과 추출의 경계

[공통 계약](common-query-contract.md)에서 허용한 이전 자료는 상위 단계가 사용자 한도와 범위를 검증해 선정합니다. 이 함수의 query.as_of는 선정된 표의 실제 기준일이며 여전히 일치하는 열만 읽습니다. 이 함수가 임의로 다른 날짜를 고르거나 이전 자료 사용 표시를 생성하는 것은 아닙니다.
