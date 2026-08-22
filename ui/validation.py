"""Validation results UI: the field-by-field table and overall PASS/REVIEW/MISMATCH banner."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from validation.validator import ValidationSummary, run_validation, DEFAULT_FIELD_MAP

_STATUS_ICON = {
    "MATCH": "✓", "EXACT_MATCH": "✓", "NORMALIZED_MATCH": "✓",
    "PROBABLE_MATCH": "≈", "REVIEW_REQUIRED": "⚠",
    "MISMATCH": "✗", "UNREADABLE": "!",
}
_OVERALL_COLOR = {
    "PASS": "success", "PASS WITH REVIEW": "warning", "MISMATCH": "error", "INCOMPLETE": "warning",
}


def render_validation(citizenship_values: dict[str, str], kyc_values: dict[str, str]) -> ValidationSummary:
    summary = run_validation(citizenship_values, kyc_values, DEFAULT_FIELD_MAP)

    banner = getattr(st, _OVERALL_COLOR.get(summary.overall_status, "info"))
    banner(f"**KYC VALIDATION: {summary.overall_status}**  —  "
           f"✓ {summary.matched} matched · ⚠ {summary.needs_review} need review · "
           f"✗ {summary.mismatched} mismatch · ! {summary.missing} missing")

    rows = []
    for o in summary.outcomes:
        rows.append({
            "Field": o.field,
            "Citizenship": o.value_a,
            "KYC": o.value_b,
            "Result": f"{_STATUS_ICON.get(o.result, '')} {o.result}",
            "Confidence": f"{o.confidence:.0f}%",
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No fields have been extracted yet for either document.")

    return summary
