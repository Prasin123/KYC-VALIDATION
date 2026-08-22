"""
Sidebar UI. Kept modular (one function per section) as requested, so new
settings sections can be added later without restructuring this file --
app.py just calls render() once and gets a plain dict of settings back.
"""
from __future__ import annotations

import streamlit as st

from roi.config import list_bank_templates

LANG_LABELS = {"english": "English", "nepali": "नेपाली", "mixed": "English + नेपाली"}


def _section_document() -> dict:
    st.sidebar.subheader("Document")
    banks = list_bank_templates()
    bank_names = list(banks.keys()) or ["siddhartha"]
    bank = st.sidebar.selectbox("Bank", bank_names, format_func=lambda b: b.replace("_", " ").title())
    templates = banks.get(bank, [])
    template_path = None
    if templates:
        template_path = st.sidebar.selectbox(
            "Document Template", templates, format_func=lambda p: p.stem.replace("_", " ").title(),
        )
    else:
        st.sidebar.caption("No templates found under configs/banks/. Add one to get started.")
    return {"bank": bank, "template_path": template_path}


def _section_language() -> dict:
    st.sidebar.subheader("Language")
    lang = st.sidebar.radio("UI / OCR language", list(LANG_LABELS.keys()),
                             format_func=lambda k: LANG_LABELS[k], index=2, horizontal=False)
    return {"language": lang}


def _section_ocr() -> dict:
    st.sidebar.subheader("OCR")
    engine = st.sidebar.selectbox("OCR Engine", ["tesseract"], help="More engines can be added under ocr/.")
    ocr_language = st.sidebar.selectbox("OCR Language", ["english", "nepali", "mixed"], index=2)
    dpi = st.sidebar.slider("Render DPI", min_value=100, max_value=400, value=200, step=50,
                             help="Higher DPI improves OCR accuracy on small text but is slower.")
    return {"ocr_engine": engine, "ocr_language": ocr_language, "dpi": dpi}


def _section_roi() -> dict:
    st.sidebar.subheader("ROI")
    mode = st.sidebar.radio("Mode", ["Review extraction", "Edit ROIs"], index=0)
    return {"roi_mode": mode}


def _section_validation() -> dict:
    st.sidebar.subheader("Validation")
    match_threshold = st.sidebar.slider("Name match threshold", 0.5, 1.0, 0.90, 0.01)
    review_threshold = st.sidebar.slider("Review threshold", 0.3, 0.9, 0.55, 0.01)
    conf_threshold = st.sidebar.slider("OCR confidence threshold", 0, 100, 60, 5)
    return {"match_threshold": match_threshold, "review_threshold": review_threshold,
            "confidence_threshold": conf_threshold}


def _section_display() -> dict:
    st.sidebar.subheader("Display")
    show_roi = st.sidebar.checkbox("Show ROI boxes", value=True)
    show_confidence = st.sidebar.checkbox("Show OCR confidence", value=True)
    debug_mode = st.sidebar.checkbox("Debug Mode", value=False,
                                      help="Show preprocessing steps, OCR boxes, and detection internals.")
    return {"show_roi": show_roi, "show_confidence": show_confidence, "debug_mode": debug_mode}


def render() -> dict:
    st.sidebar.title("KYC Validator")
    settings = {}
    settings.update(_section_document())
    st.sidebar.divider()
    settings.update(_section_language())
    st.sidebar.divider()
    settings.update(_section_ocr())
    st.sidebar.divider()
    settings.update(_section_roi())
    st.sidebar.divider()
    settings.update(_section_validation())
    st.sidebar.divider()
    settings.update(_section_display())
    st.sidebar.divider()
    st.sidebar.caption(
        "This application assists with document processing and validation. "
        "Final verification and KYC decisions must be performed by authorized bank personnel."
    )
    return settings
