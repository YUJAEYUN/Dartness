# 금액 단위 처리

상태: 이슈 #5의 첫 구현 범위. PR 병합 전에는 작업 브랜치에서 확인합니다.

추출 단계가 전달한 숫자와 원화 단위를 원 단위 금액으로 변환합니다. **AMOUNT-001**에 따라 단위를 알 수 없으면 추정하지 않습니다. 이 함수는 공시에서 단위·기간을 올바르게 읽었는지 판단하지 않습니다.

## 입력과 결과

입력은 원문 숫자 문자열과 적용 단위 문자열입니다. 원문은 공백을 포함해 그대로 보존하고, 해석할 때만 앞뒤 공백을 제거합니다. 단위는 원·천원·백만원·억원만 지원합니다. 통화가 포함된 다른 단위를 원화로 자동 해석하지 않습니다.

| 입력 | 결과 |
|---|---|
| 숫자와 지원 단위 | normalized, 원 단위 Decimal 금액 |
| 단위 없음·빈 문자열 | needs_review, missing_unit |
| 그 밖의 단위 | needs_review, unsupported_unit |
| 숫자 형식 오류 | needs_review, invalid_number |

normalized는 단위 변환 성공이지 공시 사실의 검증 완료가 아닙니다. 확인 필요 결과에는 금액 필드가 없습니다. 단위가 잘못됐고 숫자도 잘못됐다면 단위 문제부터 반환합니다.

숫자는 부호·소수점과 정상적인 세 자리 쉼표 구분을 허용합니다. 대시·괄호 음수·지수 표기·통화기호·셀 안의 단위·NaN·Infinity는 현재 지원하지 않습니다. 대시를 0으로 바꾸지 않습니다. 과거 공시의 이런 표기를 지원하려면 명시적인 규칙과 테스트를 추가합니다.

계산은 Decimal로 정확히 처리하며 표시용 반올림과 환율 계산을 수행하지 않습니다. float를 입력 계약에 사용하지 않습니다.

## 실행 예시와 테스트 데이터

아래 예시는 테스트가 문서에서 읽어 실제 결과와 비교합니다. 작성 규칙은 [문서 예시 테스트](../guides/testing.md#doc-examples)를 따릅니다. amount_krw는 사람이 지정한 정답이며 코드 출력으로 갱신하지 않습니다.

<!-- dartness-example: amounts -->
```json
[
  {"id": "amount-thousand-won", "source": "synthetic",
   "input": {"raw_value": "56,000,000", "unit": "천원"},
   "expect": {"status": "normalized", "amount_krw": "56000000000"}},
  {"id": "amount-hundred-million-won", "source": "synthetic",
   "input": {"raw_value": "560", "unit": "억원"},
   "expect": {"status": "normalized", "amount_krw": "56000000000"}},
  {"id": "amount-decimal-million-won", "source": "synthetic",
   "input": {"raw_value": "0.125", "unit": "백만원"},
   "expect": {"status": "normalized", "amount_krw": "125000"}},
  {"id": "amount-missing-unit", "rule": "AMOUNT-001", "source": "synthetic",
   "input": {"raw_value": "560", "unit": null},
   "expect": {"status": "needs_review", "reason": "missing_unit", "amount_krw": null}},
  {"id": "amount-unsupported-unit", "source": "synthetic",
   "input": {"raw_value": "560", "unit": "USD"},
   "expect": {"status": "needs_review", "reason": "unsupported_unit", "amount_krw": null}},
  {"id": "amount-dash-is-not-zero", "source": "synthetic",
   "input": {"raw_value": "-", "unit": "천원"},
   "expect": {"status": "needs_review", "reason": "invalid_number", "amount_krw": null}}
]
```

가상 데이터로 변환 동작을 확인하는 예시이며 실제 공시 추출 평가가 아닙니다. 56,000,000천원은 560억원입니다.

## 구현과 검사

구현: src/dartness/amounts.py. 테스트: tests/test_amounts.py.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/pytest -q
```

타입 검사로 정상 금액과 확인 필요 결과를 구분하고, 테스트로 실제 반환 동작을 확인합니다. 런타임 외부 입력 스키마 검증은 아직 없으므로 추후 API·LLM 입력 경계에 추가해야 합니다.

## 다음 단계

공시의 기간·단위·통화·연결/별도와 근거 위치를 추출하는 계약은 별도 논의합니다. 합계 대조·조건 판정·엑셀 출력은 아직 구현하지 않았습니다.
