"""
Extraction review UI. Runs the ROI -> preprocessing -> OCR / checkbox /
presence pipeline across every page of a document and renders each field as
an editable value next to its confidence and (in Debug Mode) its source crop
and preprocessing trace -- the "show source ROI" + manual correction spec.
"""
from __future__ import annotations

import streamlit as st
import numpy as np

from extraction.checkbox import detect_group, detect_mark
from extraction.signatures import detect_signature_or_thumbprint, detect_photo
from extraction.text import extract_text_field
from preprocessing.image_processing import pil_to_cv, crop, to_grayscale
from roi.config import DocumentTemplate
from ui.upload import UploadedPage
from utils.helpers import scale_box


def _confidence_badge(conf: float | None, threshold: float) -> str:
    if conf is None:
        return "confidence unavailable"
    flag = " ⚠" if conf < threshold else ""
    return f"{conf:.0f}%{flag}"


def run_and_render_extraction(pages: list[UploadedPage], template: DocumentTemplate,
                               settings: dict, session_key: str) -> dict[str, str]:
    """
    Runs extraction for every calibrated ROI across all supplied pages, lets
    the operator correct values inline, and returns {roi_name: final_value}
    for use by the validation step. Values are cached in st.session_state so
    re-running validation doesn't require re-running OCR.
    """
    store_key = f"{session_key}_extracted"
    if store_key not in st.session_state:
        st.session_state[store_key] = {}
    values_store = st.session_state[store_key]

    if st.button("Run Extraction", key=f"{session_key}_run_extraction"):
        with st.spinner("Running OCR and detection..."):
            for page in pages:
                page_rois = template.rois_for_page(page.page_number)
                arr = pil_to_cv(page.image)
                for roi in page_rois:
                    if not roi.calibrated and roi.field_type not in ("CHECKBOX_GROUP",):
                        continue
                    try:
                        if roi.field_type == "CHECKBOX_GROUP" and roi.options:
                            crops = {}
                            for opt in roi.options:
                                if not opt.get("box"):
                                    continue
                                sb = scale_box(opt["box"], page.native_size, page.image.size)
                                c = crop(arr, sb)
                                crops[opt["value"]] = to_grayscale(c)
                            if crops:
                                results = detect_group(crops)
                                checked = [k for k, r in results.items() if r.checked is True]
                                ambiguous = any(r.status == "REVIEW_REQUIRED" for r in results.values())
                                value = checked[0] if checked else ("REVIEW_REQUIRED" if ambiguous else "")
                                values_store[roi.roi_name] = value
                        elif roi.field_type in ("SIGNATURE", "THUMBPRINT") and roi.box:
                            sb = scale_box(roi.box, page.native_size, page.image.size)
                            c = to_grayscale(crop(arr, sb))
                            r = detect_signature_or_thumbprint(c)
                            values_store[roi.roi_name] = r.status
                        elif roi.field_type == "PHOTO" and roi.box:
                            sb = scale_box(roi.box, page.native_size, page.image.size)
                            c = crop(arr, sb)
                            r = detect_photo(c)
                            values_store[roi.roi_name] = r.status
                        elif roi.field_type in ("TEXT", "NAME", "NUMBER", "DATE", "ADDRESS") and roi.box:
                            result = extract_text_field(page.image, roi, page.native_size,
                                                         debug=settings.get("debug_mode", False))
                            values_store[roi.roi_name] = result.raw_value
                    except Exception as e:
                        values_store[roi.roi_name] = ""
                        st.warning(f"Could not extract '{roi.roi_name}': {e}")
        st.success("Extraction complete. Review and correct values below, then run validation.")

    if not values_store:
        st.caption("No extraction has been run yet for this document.")
        return {}

    threshold = settings.get("confidence_threshold", 60)
    grouped: dict[int, list] = {}
    for roi in template.rois:
        if roi.roi_name in values_store:
            grouped.setdefault(roi.page, []).append(roi)

    for page_num in sorted(grouped.keys()):
        with st.expander(f"Page {page_num} fields", expanded=(page_num == 1)):
            for roi in grouped[page_num]:
                current = values_store.get(roi.roi_name, "")
                cols = st.columns([2, 3, 1])
                cols[0].caption(f"{roi.roi_name}  ({roi.priority})")
                new_val = cols[1].text_input("value", value=current, key=f"{session_key}_{roi.roi_name}",
                                              label_visibility="collapsed")
                if new_val != current:
                    values_store[roi.roi_name] = new_val
                if settings.get("show_confidence", True):
                    cols[2].caption(roi.field_type)

    return dict(values_store)
