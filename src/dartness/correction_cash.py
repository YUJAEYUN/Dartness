"""Compare two prepared cash cells; do not select or apply corrected reports."""

from dataclasses import dataclass, field, replace
from typing import Literal

from dartness.cash_contract import CashValue
from dartness.correction_evidence import CorrectionAssessment, assess_correction


@dataclass(frozen=True)
class CorrectionCashComparison:
    relation: CorrectionAssessment
    original: CashValue | None
    correction: CashValue | None
    status: Literal["amounts_equal", "amounts_differ", "needs_review"] = field(init=False)
    reason: Literal["relation_needs_review", "missing_value"] | None = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.relation, CorrectionAssessment):
            raise ValueError("correction relation required")
        supplied = self.relation
        relation = assess_correction(
            supplied.request,
            replace(supplied.original),
            replace(supplied.correction),
            replace(supplied.evidence) if supplied.evidence is not None else None,
        )
        key = relation.request.key
        if (key.query_type, key.item_key, key.currency) != (
            "cash",
            "cash-and-cash-equivalents",
            "KRW",
        ):
            raise ValueError("only the KRW cash item is supported")
        for version, value in (
            (relation.original, self.original),
            (relation.correction, self.correction),
        ):
            if value is None:
                continue
            if not isinstance(value, CashValue):
                raise ValueError("CashValue or explicit missing value required")
            # Re-run the existing contract, including exact raw-unit normalization.
            value = replace(value)
            candidate = version.candidate
            if (value.query.corp_code, value.as_of, value.basis, value.currency) != (
                candidate.key.corp_code,
                candidate.actual_date,
                candidate.key.basis,
                candidate.key.currency,
            ):
                raise ValueError("cash value must match the candidate scope")
            source, evidence = candidate.source, value.evidence
            if (
                evidence.receipt_number,
                evidence.source_url,
                evidence.document_sha256,
                evidence.locator,
                evidence.context,
            ) != (
                source.document_id,
                source.source_url,
                source.document_sha256,
                source.locator,
                source.context,
            ):
                raise ValueError("cash evidence must match the candidate cell")
        reason: Literal["relation_needs_review", "missing_value"] | None = None
        status: Literal["amounts_equal", "amounts_differ", "needs_review"]
        if relation.status != "metadata_consistent":
            status, reason = "needs_review", "relation_needs_review"
        elif self.original is None or self.correction is None:
            status, reason = "needs_review", "missing_value"
        else:
            status = (
                "amounts_equal"
                if self.original.amount_krw == self.correction.amount_krw
                else "amounts_differ"
            )
        object.__setattr__(self, "relation", relation)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
