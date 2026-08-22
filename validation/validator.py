"""
Orchestrates the full KYC <-> Citizenship cross-validation: takes the
extracted field values from both documents, runs each configured pair
through the matcher, and rolls the results up into the overall status the
spec asks for (counts + PASS / PASS WITH REVIEW / MISMATCH / INCOMPLETE).
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field

from validation.matcher import MatchOutcome, match_field

# Which cross-document field pairs to compare, and at what priority. This is
# the "cross-validation map" -- kept as data, not hardcoded branching, so a
# new bank template can supply its own mapping (see ROI.validation_target).
DEFAULT_FIELD_MAP: list[dict] = [
    {"citizenship_field": "full_name", "kyc_field": "applicant_1_name", "field_type": "NAME", "priority": "CRITICAL"},
    {"citizenship_field": "citizenship_number", "kyc_field": "citizenship_no_applicant_1", "field_type": "TEXT", "priority": "CRITICAL"},
    {"citizenship_field": "dob_bs", "kyc_field": "dob_applicant_1", "field_type": "DATE", "priority": "CRITICAL"},
    {"citizenship_field": "gender", "kyc_field": "gender_applicant_1", "field_type": "TEXT", "priority": "IMPORTANT"},
    {"citizenship_field": "father_name", "kyc_field": "family_father_name", "field_type": "NAME", "priority": "IMPORTANT"},
    {"citizenship_field": "permanent_address_district", "kyc_field": "permanent_district", "field_type": "ADDRESS", "priority": "IMPORTANT"},
    {"citizenship_field": "issuing_office_and_district", "kyc_field": "citizenship_issue_district_applicant_1", "field_type": "TEXT", "priority": "CRITICAL"},
]

# Verdicts that count as "matched" / "needs review" / "mismatch" / "missing"
# for the summary counters, across both the free-text and ID vocabularies.
_MATCHED = {"MATCH", "EXACT_MATCH", "NORMALIZED_MATCH"}
_REVIEW = {"PROBABLE_MATCH", "REVIEW_REQUIRED"}
_MISMATCH = {"MISMATCH"}
_MISSING = {"UNREADABLE"}


@dataclass
class ValidationSummary:
    outcomes: list[MatchOutcome] = dc_field(default_factory=list)
    matched: int = 0
    needs_review: int = 0
    mismatched: int = 0
    missing: int = 0
    overall_status: str = "INCOMPLETE"

    @property
    def total(self) -> int:
        return len(self.outcomes)


def run_validation(citizenship_values: dict[str, str], kyc_values: dict[str, str],
                    field_map: list[dict] | None = None) -> ValidationSummary:
    """
    citizenship_values / kyc_values: {field_name: extracted_string_value}
    (already human-corrected where applicable -- this module doesn't know
    about OCR confidence, only final values).
    """
    field_map = field_map or DEFAULT_FIELD_MAP
    outcomes: list[MatchOutcome] = []
    for mapping in field_map:
        c_val = citizenship_values.get(mapping["citizenship_field"], "")
        k_val = kyc_values.get(mapping["kyc_field"], "")
        outcome = match_field(mapping["kyc_field"], mapping["field_type"], c_val, k_val)
        outcomes.append(outcome)

    matched = sum(1 for o in outcomes if o.result in _MATCHED)
    review = sum(1 for o in outcomes if o.result in _REVIEW)
    mismatch = sum(1 for o in outcomes if o.result in _MISMATCH)
    missing = sum(1 for o in outcomes if o.result in _MISSING)

    critical_fields = {m["kyc_field"] for m in field_map if m.get("priority") == "CRITICAL"}
    critical_outcomes = [o for o in outcomes if o.field in critical_fields]
    critical_mismatch = any(o.result in _MISMATCH for o in critical_outcomes)
    critical_missing = any(o.result in _MISSING for o in critical_outcomes)

    if critical_mismatch:
        status = "MISMATCH"
    elif critical_missing or missing > 0:
        status = "INCOMPLETE"
    elif review > 0:
        status = "PASS WITH REVIEW"
    elif mismatch > 0:
        status = "PASS WITH REVIEW"  # a non-critical mismatch still needs a human look, just isn't fatal
    else:
        status = "PASS"

    return ValidationSummary(
        outcomes=outcomes, matched=matched, needs_review=review,
        mismatched=mismatch, missing=missing, overall_status=status,
    )
