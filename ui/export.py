"""Export: JSON / CSV / Excel, covering extracted fields, checkbox values,
validation status, confidence, page number, ROI name, and review status."""
from __future__ import annotations

import json
from io import BytesIO

import pandas as pd
import streamlit as st

from roi.config import DocumentTemplate
from validation.validator import ValidationSummary


def _build_export_rows(template: DocumentTemplate, values: dict[str, str], doc_label: str) -> list[dict]:
    rows = []
    for roi in template.rois:
        if roi.roi_name not in values:
            continue
        rows.append({
            "Document": doc_label, "Field": roi.roi_name, "Page": roi.page,
            "ROI": roi.roi_name, "Value": values[roi.roi_name], "Field Type": roi.field_type,
            "Priority": roi.priority, "Required": roi.required,
            "Review Status": "OK" if values[roi.roi_name] else "EMPTY",
        })
    return rows


def render_export(kyc_template: DocumentTemplate | None, kyc_values: dict[str, str],
                   citizenship_template: DocumentTemplate | None, citizenship_values: dict[str, str],
                   summary: ValidationSummary | None):
    st.subheader("Export")

    rows = []
    if kyc_template:
        rows += _build_export_rows(kyc_template, kyc_values, "KYC")
    if citizenship_template:
        rows += _build_export_rows(citizenship_template, citizenship_values, "Citizenship")

    validation_rows = []
    if summary:
        for o in summary.outcomes:
            validation_rows.append({
                "Field": o.field, "Citizenship Value": o.value_a, "KYC Value": o.value_b,
                "Result": o.result, "Confidence": o.confidence,
            })

    export_payload = {
        "extracted_fields": rows,
        "validation": {
            "overall_status": summary.overall_status if summary else None,
            "matched": summary.matched if summary else None,
            "needs_review": summary.needs_review if summary else None,
            "mismatched": summary.mismatched if summary else None,
            "missing": summary.missing if summary else None,
            "results": validation_rows,
        },
    }

    c1, c2, c3 = st.columns(3)
    c1.download_button("⬇ Export JSON", data=json.dumps(export_payload, indent=2, ensure_ascii=False),
                        file_name="kyc_validation_export.json", mime="application/json",
                        disabled=not rows)

    csv_buf = BytesIO()
    if rows:
        pd.DataFrame(rows).to_csv(csv_buf, index=False)
    c2.download_button("⬇ Export CSV", data=csv_buf.getvalue(), file_name="kyc_extracted_fields.csv",
                        mime="text/csv", disabled=not rows)

    xlsx_buf = BytesIO()
    if rows:
        with pd.ExcelWriter(xlsx_buf, engine="openpyxl") as writer:
            pd.DataFrame(rows).to_excel(writer, sheet_name="Extracted Fields", index=False)
            if validation_rows:
                pd.DataFrame(validation_rows).to_excel(writer, sheet_name="Validation", index=False)
    c3.download_button("⬇ Export Excel", data=xlsx_buf.getvalue(), file_name="kyc_validation_export.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        disabled=not rows)

    if not rows:
        st.caption("Run extraction on at least one document to enable export.")
