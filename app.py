"""
KYC Validator -- main Streamlit app.

Upload -> Preview -> (optionally) edit ROIs -> Extract -> Validate -> Export,
with a human reviewer in control at every step. See README.md for setup.
"""
from __future__ import annotations

import streamlit as st

from roi.config import load_template
from roi.manager import ROIManager
from ui import sidebar, upload, preview, roi_editor, extraction, validation, export
from utils.logging import get_logger

log = get_logger("app")

st.set_page_config(page_title="KYC Validator", layout="wide")


def _load_template_cached(path, session_key):
    """Load a template into session_state once, so ROI edits persist across reruns."""
    if session_key not in st.session_state:
        st.session_state[session_key] = load_template(path)
    return st.session_state[session_key]


def main():
    st.title("KYC / Citizenship Document Validator")
    st.caption(
        "This application assists with document processing and validation. "
        "Final verification and KYC decisions must be performed by authorized bank personnel."
    )

    settings = sidebar.render()

    kyc_template = None
    if settings.get("template_path"):
        kyc_template = _load_template_cached(settings["template_path"], "kyc_template")
    citizenship_template = _load_template_cached("configs/citizenship/nepal_citizenship.json", "citizenship_template")

    tab_upload, tab_review, tab_validate, tab_export = st.tabs(
        ["📤 Upload & Preview", "🔍 Extraction / ROI Editor", "✅ Validation", "📦 Export"]
    )

    with tab_upload:
        col_kyc, col_cit = st.columns(2)
        with col_kyc:
            kyc_pages = upload.render_kyc_uploader(dpi=settings["dpi"])
            if kyc_pages:
                preview.render_preview(kyc_pages, "KYC FORM", kyc_template,
                                        settings["show_roi"], key_prefix="kyc")
        with col_cit:
            citizenship_pages = upload.render_citizenship_uploader(dpi=settings["dpi"])
            if citizenship_pages:
                preview.render_preview(citizenship_pages, "CITIZENSHIP", citizenship_template,
                                        settings["show_roi"], key_prefix="citizenship")
        st.session_state["kyc_pages"] = kyc_pages if kyc_pages else st.session_state.get("kyc_pages", [])
        st.session_state["citizenship_pages"] = (citizenship_pages if citizenship_pages
                                                  else st.session_state.get("citizenship_pages", []))

    kyc_pages = st.session_state.get("kyc_pages", [])
    citizenship_pages = st.session_state.get("citizenship_pages", [])

    with tab_review:
        if settings["roi_mode"] == "Edit ROIs":
            doc_choice = st.radio("Document", ["KYC", "Citizenship"], horizontal=True)
            if doc_choice == "KYC" and kyc_pages and kyc_template:
                page_num = st.selectbox("Page", list(range(1, len(kyc_pages) + 1)))
                manager = ROIManager(kyc_template)
                roi_editor.render_roi_editor(manager, kyc_pages[page_num - 1], page_num)
            elif doc_choice == "Citizenship" and citizenship_pages and citizenship_template:
                page_num = st.selectbox("Page", list(range(1, len(citizenship_pages) + 1)))
                manager = ROIManager(citizenship_template)
                roi_editor.render_roi_editor(manager, citizenship_pages[page_num - 1], page_num)
            else:
                st.info("Upload a document on the Upload & Preview tab first.")
        else:
            st.markdown("### KYC Form")
            kyc_values = {}
            if kyc_pages and kyc_template:
                kyc_values = extraction.run_and_render_extraction(kyc_pages, kyc_template, settings, "kyc")
            else:
                st.caption("Upload a KYC form to extract fields.")
            st.session_state["kyc_values"] = kyc_values or st.session_state.get("kyc_values", {})

            st.markdown("### Citizenship")
            citizenship_values = {}
            if citizenship_pages and citizenship_template:
                citizenship_values = extraction.run_and_render_extraction(
                    citizenship_pages, citizenship_template, settings, "citizenship")
            else:
                st.caption("Upload a citizenship certificate to extract fields.")
            st.session_state["citizenship_values"] = (citizenship_values
                                                        or st.session_state.get("citizenship_values", {}))

    with tab_validate:
        kyc_values = st.session_state.get("kyc_values", {})
        citizenship_values = st.session_state.get("citizenship_values", {})
        if not kyc_values or not citizenship_values:
            st.info("Run extraction on both the KYC form and the Citizenship certificate first "
                     "(Extraction / ROI Editor tab).")
        else:
            st.button("Re-run Validation", help="Re-check after correcting any extracted values.")
            st.session_state["validation_summary"] = validation.render_validation(
                citizenship_values, kyc_values)

    with tab_export:
        export.render_export(
            kyc_template, st.session_state.get("kyc_values", {}),
            citizenship_template, st.session_state.get("citizenship_values", {}),
            st.session_state.get("validation_summary"),
        )


if __name__ == "__main__":
    main()
