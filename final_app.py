"""
Nepal KYC IDP Portal
=====================
An Intelligent Document Processing (IDP) and KYC verification tool for
Nepali citizenship certificates, built with Streamlit, OpenCV, and
Tesseract OCR (Devanagari / Nepali language pack).

Pipeline
--------
1. Preprocess  - grayscale -> non-local means denoising -> adaptive
                 Gaussian thresholding, to handle glare, shadows and
                 uneven lighting from mobile camera captures.
2. Localize    - crop configurable Regions of Interest (ROI) for the
                 fields that matter for KYC: citizenship number, name,
                 father's name, date of birth, and address.
3. Recognize   - run Tesseract with the Nepali (`nep`) language pack,
                 using single-line segmentation (--psm 7) for most
                 fields and block mode (--psm 6) for the multi-line
                 address field.
4. Validate    - clean and normalise the Devanagari output (including
                 Devanagari -> Arabic digit conversion), then apply
                 field-specific regular expressions.
5. Cross-check - compare the citizenship certificate against the
                 physical KYC form field-by-field and flag mismatches.

Run:
    streamlit run app.py

System requirements (NOT installable via pip - see SETUP.md):
    - Tesseract OCR binary (tesseract-ocr)
    - Nepali trained data (tesseract-ocr-nep / nep.traineddata)

NOTE ON ACCURACY: real citizenship certificates and KYC forms vary a lot
in layout, era, print vs. handwriting, and scan quality. The default ROI
boxes below are illustrative starting points, not a guarantee of correct
localisation for every document. Use the "Calibrate ROI regions" panel
in the sidebar to tune them for your own scanner/camera setup, and treat
this app as a reviewable-assistant, not an unattended decision-maker.
"""

from __future__ import annotations

import difflib
import json
import re
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, UnidentifiedImageError

# --- Optional heavy dependencies are imported defensively so a missing ---
# --- package produces a friendly in-app message instead of a hard crash --
try:
    import cv2
    CV2_IMPORT_ERROR: Optional[str] = None
except ImportError as exc:  # pragma: no cover - exercised only if opencv missing
    cv2 = None  # type: ignore
    CV2_IMPORT_ERROR = str(exc)

try:
    import pytesseract
    from pytesseract import TesseractNotFoundError, TesseractError
    PYTESSERACT_IMPORT_ERROR: Optional[str] = None
except ImportError as exc:  # pragma: no cover - exercised only if pytesseract missing
    pytesseract = None  # type: ignore
    PYTESSERACT_IMPORT_ERROR = str(exc)

    class TesseractNotFoundError(Exception):
        pass

    class TesseractError(Exception):
        pass


# =====================================================================
# Page config + visual identity
# =====================================================================
st.set_page_config(
    page_title="Nepal KYC IDP Portal",
    page_icon="🪪",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+Devanagari:wght@500;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
    --paper: #FAF6EE;
    --paper-line: #E4D9BC;
    --ink: #211B1F;
    --ink-soft: #6B6470;
    --crimson: #A91E32;
    --crimson-soft: #F4DEE1;
    --blue: #0B2F73;
    --blue-soft: #DDE6F5;
    --success: #1B7F4C;
    --success-bg: #DEF3E7;
    --warning: #9C6B08;
    --warning-bg: #FBF0D2;
    --danger: #A91E32;
    --danger-bg: #F7DEE1;
}

.stApp { background: var(--paper); }

html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; color: var(--ink); }

h1, h2, h3 {
    font-family: 'Noto Serif Devanagari', serif !important;
    color: var(--ink) !important;
    letter-spacing: 0.2px;
}

code, .kyc-mono { font-family: 'IBM Plex Mono', monospace !important; }

.kyc-header {
    display: flex;
    align-items: center;
    gap: 1.2rem;
    padding: 1.3rem 1.8rem;
    background: linear-gradient(135deg, var(--blue) 0%, #123a86 100%);
    border-radius: 14px;
    margin-bottom: 0.6rem;
}
.kyc-header .kyc-flagbar {
    width: 52px;
    height: 52px;
    border-radius: 50%;
    background: var(--crimson);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    flex-shrink: 0;
    border: 3px solid #FFFFFF;
}
.kyc-header h1 { color: #FFFFFF !important; font-size: 1.6rem; margin: 0; }
.kyc-header p { color: #DCE6F7; margin: 0.2rem 0 0 0; font-size: 0.92rem; }

.kyc-rule {
    height: 6px;
    margin: 0 0 1.5rem 0;
    border-radius: 3px;
    background: repeating-linear-gradient(90deg,
        var(--crimson), var(--crimson) 10px,
        var(--blue) 10px, var(--blue) 20px);
    opacity: 0.55;
}

.kyc-card {
    background: #FFFFFF;
    border: 1px solid var(--paper-line);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
}

.kyc-field-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--ink-soft);
}

.kyc-stamp {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 128px;
    height: 128px;
    border-radius: 50%;
    border: 3px double currentColor;
    box-shadow: inset 0 0 0 5px var(--paper);
    outline: 1px solid currentColor;
    outline-offset: -9px;
    transform: rotate(-6deg);
    text-align: center;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 600;
    font-size: 0.78rem;
    line-height: 1.25;
    padding: 0.4rem;
    margin: 0.2rem 0.4rem 0.6rem 0;
}
.kyc-stamp--verified { color: var(--success); }
.kyc-stamp--review { color: var(--warning); }
.kyc-stamp--failed { color: var(--danger); }
.kyc-stamp .kyc-stamp-sub {
    display: block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.58rem;
    letter-spacing: 0.1em;
    opacity: 0.8;
    margin-top: 0.15rem;
}

.stButton>button[kind="primary"] { background: var(--crimson); border: none; }
.stButton>button[kind="primary"]:hover { background: #8A1828; }

[data-testid="stMetricValue"] { font-family: 'IBM Plex Mono', monospace; }

section[data-testid="stSidebar"] { background: #F3ECDD; border-right: 1px solid var(--paper-line); }

@media (prefers-reduced-motion: no-preference) {
    .kyc-card { transition: box-shadow 0.15s ease; }
    .kyc-card:hover { box-shadow: 0 2px 10px rgba(33, 27, 31, 0.08); }
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# =====================================================================
# Domain constants
# =====================================================================
DEV_DIGIT_MAP = str.maketrans("०१२३४५६७८९", "0123456789")
NUMERIC_WHITELIST = "0123456789०१२३४५६७८९-/. "

FIELD_DEFINITIONS = [
    {"key": "citizenship_no", "label": "Citizenship Number", "kind": "number", "psm": 7},
    {"key": "full_name", "label": "Full Name (Devanagari)", "kind": "text", "psm": 7},
    {"key": "father_name", "label": "Father's Name", "kind": "text", "psm": 7},
    {"key": "dob", "label": "Date of Birth (B.S.)", "kind": "date", "psm": 7},
    {"key": "address", "label": "Permanent Address", "kind": "text", "psm": 6},
]
FIELD_KEYS = [f["key"] for f in FIELD_DEFINITIONS]
FIELD_LABELS = {f["key"]: f["label"] for f in FIELD_DEFINITIONS}
CRITICAL_FIELDS = {"citizenship_no", "full_name"}

# Normalised (0-1) ROI boxes: (x1, y1, x2, y2).
DEFAULT_ROI = {
    # Calibrated against a District Administration Office citizenship
    # certificate layout: photo lower-left; label/value rows to its
    # right running name -> birthplace -> permanent address -> DOB ->
    # father's name -> mother's name -> spouse. Still a starting point -
    # older/newer certificate formats shift things, so recalibrate from
    # the sidebar if your rows land differently.
    "citizenship": {
        "citizenship_no": (0.02, 0.250, 0.35, 0.300),
        "full_name": (0.21, 0.350, 0.62, 0.388),
        "address": (0.21, 0.500, 0.62, 0.567),
        "dob": (0.21, 0.572, 0.62, 0.603),
        "father_name": (0.21, 0.607, 0.62, 0.639),
    },
    # Calibrated against a Siddhartha Bank "Personal Account Opening
    # Form" (page 1). Only the applicant-name row is present on this
    # page - citizenship_no / father_name / dob / address aren't part
    # of this particular page (they typically live on the accompanying
    # "Individual Customer Information Form" annex) and keep
    # illustrative placeholders below until calibrated against that page.
    "kyc": {
        "citizenship_no": (0.08, 0.10, 0.55, 0.18),
        "full_name": (0.03, 0.635, 0.97, 0.685),
        "father_name": (0.08, 0.32, 0.92, 0.40),
        "dob": (0.08, 0.42, 0.55, 0.50),
        "address": (0.08, 0.52, 0.92, 0.68),
    },
}

ROI_COLORS = {
    "citizenship_no": (169, 30, 50),
    "full_name": (11, 47, 115),
    "father_name": (27, 127, 76),
    "dob": (156, 107, 8),
    "address": (110, 60, 150),
}

FIELD_LABEL_STRIP = {
    "citizenship_no": [r"नागरिकता(को)?\s*(प्रमाणपत्र)?\s*नं\.?", r"Citizenship\s*No\.?"],
    "full_name": [r"^\s*नाम\s*(थर)?", r"\bName\b"],
    "father_name": [r"बाबुको\s*नाम", r"Father'?s?\s*Name"],
    "dob": [r"जन्म\s*मिति", r"Date\s*of\s*Birth", r"D\.?O\.?B\.?"],
    "address": [r"स्थायी\s*ठेगाना", r"\bठेगाना\b", r"\bAddress\b"],
}

CITIZENSHIP_NO_PATTERN = re.compile(r"(\d{1,3}[-/]\d{1,3}[-/]\d{1,3}(?:[-/]\d{1,6})?|\d{6,15})")
DATE_PATTERN = re.compile(r"(\d{4})[\-/.](\d{1,2})[\-/.](\d{1,2})")

STATUS_MATCH, STATUS_REVIEW, STATUS_MISMATCH = "✅ Match", "⚠️ Review", "❌ Mismatch"
STATUS_SEVERITY = {STATUS_MATCH: 0, STATUS_REVIEW: 1, STATUS_MISMATCH: 2}


# =====================================================================
# Preprocessing (OpenCV)
# =====================================================================
def preprocess_document(image: np.ndarray, denoise_strength: int = 10) -> np.ndarray:
    """Grayscale -> non-local means denoise -> adaptive Gaussian threshold.

    This is the core step that makes mobile-camera captures (uneven
    lighting, glare, shadows) usable by Tesseract.
    """
    if image is None or image.size == 0:
        raise ValueError("Empty image passed to preprocess_document().")
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if image.ndim == 3 else image.copy()
    denoised = cv2.fastNlMeansDenoising(gray, None, h=denoise_strength, templateWindowSize=7, searchWindowSize=21)
    thresh = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    return thresh


def crop_roi(image: np.ndarray, roi_norm: tuple[float, float, float, float]) -> Optional[np.ndarray]:
    """Crop a normalised (0-1) ROI box from an image, clamped to bounds."""
    h, w = image.shape[:2]
    x1, y1, x2, y2 = roi_norm
    x1, x2 = sorted((max(0.0, min(1.0, x1)), max(0.0, min(1.0, x2))))
    y1, y2 = sorted((max(0.0, min(1.0, y1)), max(0.0, min(1.0, y2))))
    px1, px2 = int(x1 * w), min(w, max(int(x2 * w), int(x1 * w) + 1))
    py1, py2 = int(y1 * h), min(h, max(int(y2 * h), int(y1 * h) + 1))
    crop = image[py1:py2, px1:px2]
    return crop if crop.size > 0 else None


def draw_roi_overlay(image: np.ndarray, roi_dict: dict) -> np.ndarray:
    """Draw labelled ROI rectangles on a copy of the document for visual QA."""
    overlay = image.copy()
    h, w = overlay.shape[:2]
    for key, box in roi_dict.items():
        x1, y1, x2, y2 = box
        p1 = (int(x1 * w), int(y1 * h))
        p2 = (int(x2 * w), int(y2 * h))
        color = ROI_COLORS.get(key, (100, 100, 100))
        cv2.rectangle(overlay, p1, p2, color, max(2, w // 400))
        label_y = max(18, p1[1] - 8)
        cv2.putText(
            overlay, FIELD_LABELS.get(key, key), (p1[0], label_y),
            cv2.FONT_HERSHEY_SIMPLEX, max(0.4, w / 2200), color, 2, cv2.LINE_AA,
        )
    return overlay


# =====================================================================
# OCR engine (Tesseract)
# =====================================================================
def check_tesseract_ready() -> tuple[bool, str]:
    """Verify the Tesseract binary and the Nepali language pack are available.

    Returns (ok, message) - never raises, so callers can always show a
    friendly banner instead of letting the app crash.
    """
    if CV2_IMPORT_ERROR:
        return False, f"OpenCV failed to import ({CV2_IMPORT_ERROR}). Run: pip install opencv-python-headless"
    if PYTESSERACT_IMPORT_ERROR:
        return False, f"pytesseract failed to import ({PYTESSERACT_IMPORT_ERROR}). Run: pip install pytesseract"
    try:
        pytesseract.get_tesseract_version()
    except TesseractNotFoundError:
        return False, (
            "Tesseract OCR binary was not found on this system. Install it first, e.g. "
            "`sudo apt-get install tesseract-ocr` (Ubuntu/Debian), `brew install tesseract` (macOS), "
            "or the UB-Mannheim installer on Windows. See SETUP.md for details."
        )
    except Exception as exc:
        return False, f"Could not verify the Tesseract installation ({exc})."

    try:
        langs = pytesseract.get_languages(config="")
    except Exception:
        langs = []
    if "nep" not in langs:
        return False, (
            "Tesseract is installed, but the Nepali language pack (`nep.traineddata`) is missing. "
            "Install it with `sudo apt-get install tesseract-ocr-nep`, or download `nep.traineddata` "
            "from the tesseract-ocr/tessdata GitHub repository into your tessdata folder. See SETUP.md."
        )
    return True, "Tesseract and the Nepali language pack are ready."


def ocr_devanagari(image: np.ndarray, psm: int = 7, numeric_only: bool = False) -> dict:
    """Run Tesseract configured for Nepali/Devanagari text on a single crop.

    Returns a dict with text, mean word confidence, and an error field
    that is None on success - callers check `error` rather than relying
    on exceptions propagating into the UI.
    """
    config_parts = [f"--psm {psm}", "--oem 3"]
    if numeric_only:
        config_parts.append(f'-c tessedit_char_whitelist={NUMERIC_WHITELIST}')
    config = " ".join(config_parts)
    try:
        text = pytesseract.image_to_string(image, lang="nep", config=config).strip()
        data = pytesseract.image_to_data(image, lang="nep", config=config, output_type=pytesseract.Output.DICT)
        confs = [int(c) for c in data.get("conf", []) if str(c) not in ("-1",)]
        mean_conf = round(sum(confs) / len(confs), 1) if confs else 0.0
        return {"text": text, "confidence": mean_conf, "error": None}
    except TesseractNotFoundError:
        return {"text": "", "confidence": 0.0, "error": "Tesseract binary not found."}
    except TesseractError as exc:
        return {"text": "", "confidence": 0.0, "error": f"Tesseract error: {exc}"}
    except Exception as exc:  # defensive catch-all so one bad crop never crashes the run
        return {"text": "", "confidence": 0.0, "error": str(exc)}


# =====================================================================
# Post-processing & validation
# =====================================================================
def devanagari_digits_to_arabic(text: str) -> str:
    return text.translate(DEV_DIGIT_MAP)


def clean_devanagari_text(text: str) -> str:
    """Keep Devanagari, Latin letters/digits, spaces and light punctuation."""
    if not text:
        return ""
    allowed = re.compile(r"[^\u0900-\u097F0-9A-Za-z\s,./-]")
    cleaned = allowed.sub("", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def strip_field_label(field_key: str, text: str) -> str:
    result = text
    for pattern in FIELD_LABEL_STRIP.get(field_key, []):
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)
    return result.strip(" :।.,-")


def extract_citizenship_number(text: str) -> Optional[str]:
    normalized = devanagari_digits_to_arabic(text).replace(" ", "")
    match = CITIZENSHIP_NO_PATTERN.search(normalized)
    return match.group(0) if match else None


def validate_citizenship_number(number: Optional[str]) -> bool:
    if not number:
        return False
    digits_only = re.sub(r"[^\d]", "", number)
    return 6 <= len(digits_only) <= 15


def extract_dob(text: str) -> Optional[str]:
    normalized = devanagari_digits_to_arabic(text)
    match = DATE_PATTERN.search(normalized)
    return match.group(0) if match else None


def postprocess_field(field_def: dict, raw_text: str) -> str:
    """Apply the right cleaning/extraction strategy for a field's `kind`."""
    cleaned = clean_devanagari_text(raw_text)
    cleaned = strip_field_label(field_def["key"], cleaned)
    kind = field_def["kind"]
    if kind == "number":
        extracted = extract_citizenship_number(cleaned)
        return extracted if extracted else cleaned
    if kind == "date":
        extracted = extract_dob(cleaned)
        return extracted if extracted else cleaned
    return cleaned


# =====================================================================
# Document-level extraction
# =====================================================================
def load_image(uploaded_file) -> Optional[np.ndarray]:
    try:
        uploaded_file.seek(0)
        image = Image.open(uploaded_file).convert("RGB")
        return np.array(image)
    except (UnidentifiedImageError, OSError):
        return None


def extract_fields_from_document(image: np.ndarray, roi_dict: dict, denoise_strength: int) -> dict:
    """Run the full per-field pipeline for one document.

    Returns a dict with: fields (key -> cleaned value), confidences
    (key -> mean OCR confidence), warnings (list[str]), and overlay
    (ROI-annotated preview image for QA).
    """
    fields, confidences, warnings = {}, {}, []
    for field_def in FIELD_DEFINITIONS:
        key = field_def["key"]
        box = roi_dict.get(key)
        crop = crop_roi(image, box) if box else None
        if crop is None:
            warnings.append(f"Could not crop a region for '{FIELD_LABELS[key]}' - check ROI calibration.")
            fields[key], confidences[key] = "", 0.0
            continue
        try:
            processed_crop = preprocess_document(crop, denoise_strength=denoise_strength)
        except ValueError:
            warnings.append(f"Empty crop for '{FIELD_LABELS[key]}'.")
            fields[key], confidences[key] = "", 0.0
            continue
        result = ocr_devanagari(processed_crop, psm=field_def["psm"], numeric_only=(field_def["kind"] in ("number", "date")))
        if result["error"]:
            warnings.append(f"OCR issue on '{FIELD_LABELS[key]}': {result['error']}")
        value = postprocess_field(field_def, result["text"])
        if key == "citizenship_no" and value and not validate_citizenship_number(value):
            warnings.append(
                f"'{value}' doesn't look like a valid citizenship number (expected 6-15 digits) - please verify manually."
            )
        fields[key] = value
        confidences[key] = result["confidence"]

    overlay = draw_roi_overlay(image, roi_dict)
    return {"fields": fields, "confidences": confidences, "warnings": warnings, "overlay": overlay}


# =====================================================================
# Cross-referencing
# =====================================================================
def similarity(a: str, b: str) -> float:
    a, b = (a or "").strip(), (b or "").strip()
    if not a and not b:
        return 100.0
    if not a or not b:
        return 0.0
    return round(difflib.SequenceMatcher(None, a, b).ratio() * 100, 1)


def status_for_score(score: float, match_threshold: float) -> str:
    if score >= match_threshold:
        return STATUS_MATCH
    if score >= match_threshold - 30:
        return STATUS_REVIEW
    return STATUS_MISMATCH


def compare_fields(citizenship_fields: dict, kyc_fields: dict, match_threshold: float) -> list[dict]:
    rows = []
    for field_def in FIELD_DEFINITIONS:
        key = field_def["key"]
        val_a, val_b = citizenship_fields.get(key, ""), kyc_fields.get(key, "")
        score = similarity(val_a, val_b)
        rows.append({
            "key": key,
            "Field": field_def["label"],
            "Citizenship Certificate": val_a or "—",
            "KYC Form": val_b or "—",
            "Similarity (%)": score,
            "Status": status_for_score(score, match_threshold),
        })
    return rows


def compute_overall_status(rows: list[dict]) -> tuple[str, str]:
    """Returns (status_class, status_text) where status_class is one of
    'verified' / 'review' / 'failed', used to style the stamp."""
    worst_overall = max((STATUS_SEVERITY.get(r["Status"], 1) for r in rows), default=1)
    worst_critical = max(
        (STATUS_SEVERITY.get(r["Status"], 1) for r in rows if r["key"] in CRITICAL_FIELDS), default=1
    )
    if worst_critical == 2 or worst_overall == 2:
        return "failed", "Verification failed"
    if worst_overall == 1:
        return "review", "Needs manual review"
    return "verified", "Verified"


def apply_status_styles(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    """Colour the Status column; works across pandas versions where
    Styler.applymap was renamed/removed in favour of Styler.map."""
    def _style(val: str) -> str:
        if "Match" in val:
            return "background-color: #DEF3E7; color: #14532D; font-weight: 600;"
        if "Review" in val:
            return "background-color: #FBF0D2; color: #78430A; font-weight: 600;"
        if "Mismatch" in val:
            return "background-color: #F7DEE1; color: #7A1626; font-weight: 600;"
        return ""
    styler = df.style
    if hasattr(styler, "map"):
        return styler.map(_style, subset=["Status"])
    return styler.applymap(_style, subset=["Status"])  # older pandas fallback


# =====================================================================
# Sidebar
# =====================================================================
def render_sidebar() -> dict:
    with st.sidebar:
        st.markdown("### 🪪 Nepal KYC IDP Portal")
        st.caption("Intelligent Document Processing for citizenship-based KYC.")

        with st.expander("ℹ️ How this works", expanded=False):
            st.markdown(
                "1. **Preprocess** - denoise + adaptive threshold each image.\n"
                "2. **Localize** - crop the ROI for each field.\n"
                "3. **Recognize** - Tesseract OCR with the Nepali (`nep`) model.\n"
                "4. **Validate** - clean text, extract numbers/dates.\n"
                "5. **Cross-check** - compare the certificate against the KYC form."
            )

        st.markdown("#### Engine status")
        ok, msg = check_tesseract_ready()
        if ok:
            st.success(msg, icon="✅")
        else:
            st.error(msg, icon="🚫")

        st.markdown("#### Settings")
        match_threshold = st.slider(
            "Match threshold (%)", min_value=50, max_value=100, value=80, step=5,
            help="Similarity score at or above this is a Match. Roughly the next 30 points down is flagged for Review.",
        )
        denoise_strength = st.slider(
            "Denoise strength", min_value=3, max_value=25, value=10, step=1,
            help="Higher values remove more noise/glare but can blur fine strokes on low-resolution photos.",
        )

        if "roi_config" not in st.session_state:
            st.session_state.roi_config = {
                "citizenship": dict(DEFAULT_ROI["citizenship"]),
                "kyc": dict(DEFAULT_ROI["kyc"]),
            }

        with st.expander("🎯 Calibrate ROI regions", expanded=False):
            st.caption("Default boxes are illustrative. Adjust them to match your own scans.")
            doc_choice = st.selectbox("Document", ["citizenship", "kyc"], format_func=lambda d: "Citizenship Certificate" if d == "citizenship" else "KYC Form")
            field_choice = st.selectbox("Field", FIELD_KEYS, format_func=lambda k: FIELD_LABELS[k])
            current_box = st.session_state.roi_config[doc_choice].get(field_choice, DEFAULT_ROI[doc_choice][field_choice])
            key_prefix = f"roi_{doc_choice}_{field_choice}"
            x1 = st.slider("Left (x1)", 0.0, 1.0, float(current_box[0]), 0.01, key=f"{key_prefix}_x1")
            y1 = st.slider("Top (y1)", 0.0, 1.0, float(current_box[1]), 0.01, key=f"{key_prefix}_y1")
            x2 = st.slider("Right (x2)", 0.0, 1.0, float(current_box[2]), 0.01, key=f"{key_prefix}_x2")
            y2 = st.slider("Bottom (y2)", 0.0, 1.0, float(current_box[3]), 0.01, key=f"{key_prefix}_y2")
            st.session_state.roi_config[doc_choice][field_choice] = (x1, y1, x2, y2)
            if st.button("Reset this field to default", key=f"{key_prefix}_reset"):
                st.session_state.roi_config[doc_choice][field_choice] = DEFAULT_ROI[doc_choice][field_choice]
                st.rerun()

        st.divider()
        st.caption(
            "Prototype for internal review workflows. Uploaded images are processed "
            "in memory for this session only and are not written to disk or sent "
            "anywhere outside this app. Confirm your own data-retention and KYC/AML "
            "policy requirements before using this in production."
        )

    return {"match_threshold": float(match_threshold), "denoise_strength": int(denoise_strength)}


# =====================================================================
# Results rendering
# =====================================================================
def render_stamp(status_class: str, status_text: str, matched_count: int, total_count: int) -> str:
    sub = f"{matched_count}/{total_count} fields"
    return (
        f'<div class="kyc-stamp kyc-stamp--{status_class}">{status_text}'
        f'<span class="kyc-stamp-sub">{sub}</span></div>'
    )


def build_export_payload(results: dict) -> dict:
    rows = results["comparison_rows"]
    status_class, status_text = results["overall_status"]
    return {
        "verification_id": results["verification_id"],
        "generated_at": results["timestamp"],
        "overall_status": status_text,
        "match_threshold_percent": results["match_threshold"],
        "fields": [
            {
                "field": r["Field"],
                "citizenship_certificate": r["Citizenship Certificate"],
                "kyc_form": r["KYC Form"],
                "similarity_percent": r["Similarity (%)"],
                "status": r["Status"],
            }
            for r in rows
        ],
        "ocr": {
            "citizenship_certificate": {
                "fields": results["citizenship"]["fields"],
                "confidence": results["citizenship"]["confidences"],
                "warnings": results["citizenship"]["warnings"],
            },
            "kyc_form": {
                "fields": results["kyc"]["fields"],
                "confidence": results["kyc"]["confidences"],
                "warnings": results["kyc"]["warnings"],
            },
        },
    }


def render_results(results: dict) -> None:
    rows = results["comparison_rows"]
    status_class, status_text = results["overall_status"]
    matched_count = sum(1 for r in rows if r["Status"] == STATUS_MATCH)
    all_confidences = list(results["citizenship"]["confidences"].values()) + list(results["kyc"]["confidences"].values())
    avg_conf = round(sum(all_confidences) / len(all_confidences), 1) if all_confidences else 0.0

    st.markdown("## Verification result")
    col_stamp, col_metrics = st.columns([1, 3])
    with col_stamp:
        st.markdown(render_stamp(status_class, status_text, matched_count, len(rows)), unsafe_allow_html=True)
    with col_metrics:
        m1, m2, m3 = st.columns(3)
        m1.metric("Fields matched", f"{matched_count}/{len(rows)}")
        m2.metric("Avg. OCR confidence", f"{avg_conf}%")
        m3.metric("Match threshold", f"{results['match_threshold']:.0f}%")
        if results["citizenship"]["warnings"] or results["kyc"]["warnings"]:
            with st.expander("⚠️ Processing warnings", expanded=False):
                for w in results["citizenship"]["warnings"]:
                    st.warning(f"Citizenship certificate: {w}")
                for w in results["kyc"]["warnings"]:
                    st.warning(f"KYC form: {w}")

    tab_table, tab_roi, tab_raw, tab_json = st.tabs(
        ["📊 Comparison table", "🖼️ ROI preview", "📄 Raw OCR text", "🧾 JSON export"]
    )

    with tab_table:
        display_cols = ["Field", "Citizenship Certificate", "KYC Form", "Similarity (%)", "Status"]
        display_df = pd.DataFrame(rows)[display_cols]
        st.dataframe(apply_status_styles(display_df), use_container_width=True, hide_index=True)

    with tab_roi:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Citizenship certificate**")
            st.image(results["citizenship"]["overlay"], use_container_width=True)
        with c2:
            st.markdown("**KYC form**")
            st.image(results["kyc"]["overlay"], use_container_width=True)

    with tab_raw:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Citizenship certificate - extracted fields**")
            for k in FIELD_KEYS:
                st.markdown(f'<span class="kyc-field-label">{FIELD_LABELS[k]}</span>', unsafe_allow_html=True)
                st.code(results["citizenship"]["fields"].get(k, "") or "(empty)", language=None)
        with c2:
            st.markdown("**KYC form - extracted fields**")
            for k in FIELD_KEYS:
                st.markdown(f'<span class="kyc-field-label">{FIELD_LABELS[k]}</span>', unsafe_allow_html=True)
                st.code(results["kyc"]["fields"].get(k, "") or "(empty)", language=None)

    with tab_json:
        payload = build_export_payload(results)
        st.json(payload)
        json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        st.download_button(
            "⬇️ Download JSON",
            data=json_bytes,
            file_name=f"kyc_verification_{results['verification_id']}.json",
            mime="application/json",
            type="primary",
        )


# =====================================================================
# Main app
# =====================================================================
def main() -> None:
    settings = render_sidebar()

    st.markdown(
        '<div class="kyc-header"><div class="kyc-flagbar">🪪</div>'
        "<div><h1>Nepal KYC IDP Portal</h1>"
        "<p>Devanagari OCR for citizenship certificates, cross-checked against your KYC form.</p>"
        "</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown('<div class="kyc-rule"></div>', unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### 1. Citizenship certificate")
        citizenship_upload = st.file_uploader(
            "Upload the front or back of the citizenship certificate",
            type=["png", "jpg", "jpeg"], key="citizenship_upload",
        )
        citizenship_image = None
        if citizenship_upload is not None:
            citizenship_image = load_image(citizenship_upload)
            if citizenship_image is None:
                st.error("Could not read that file as an image. Please upload a JPG or PNG.")
            else:
                st.image(citizenship_image, caption="Citizenship certificate preview", use_container_width=True)

    with col_b:
        st.markdown("#### 2. Physical KYC form")
        kyc_upload = st.file_uploader(
            "Upload a photo of the completed KYC form",
            type=["png", "jpg", "jpeg"], key="kyc_upload",
        )
        kyc_image = None
        if kyc_upload is not None:
            kyc_image = load_image(kyc_upload)
            if kyc_image is None:
                st.error("Could not read that file as an image. Please upload a JPG or PNG.")
            else:
                st.image(kyc_image, caption="KYC form preview", use_container_width=True)

    st.write("")
    ready_to_process = citizenship_image is not None and kyc_image is not None
    process_clicked = st.button(
        "🔍 Process KYC & Extract Data", type="primary",
        use_container_width=True, disabled=not ready_to_process,
    )
    if not ready_to_process:
        st.caption("Upload both documents to enable processing.")

    if process_clicked:
        engine_ok, engine_msg = check_tesseract_ready()
        if not engine_ok:
            st.error(f"Can't run OCR yet: {engine_msg}")
        else:
            with st.spinner("Processing documents - preprocessing, OCR, validation..."):
                try:
                    citizenship_result = extract_fields_from_document(
                        citizenship_image, st.session_state.roi_config["citizenship"], settings["denoise_strength"]
                    )
                    kyc_result = extract_fields_from_document(
                        kyc_image, st.session_state.roi_config["kyc"], settings["denoise_strength"]
                    )
                    comparison_rows = compare_fields(
                        citizenship_result["fields"], kyc_result["fields"], settings["match_threshold"]
                    )
                    overall_status = compute_overall_status(comparison_rows)
                    st.session_state.kyc_results = {
                        "verification_id": datetime.now().strftime("%Y%m%d-%H%M%S"),
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "citizenship": citizenship_result,
                        "kyc": kyc_result,
                        "comparison_rows": comparison_rows,
                        "overall_status": overall_status,
                        "match_threshold": settings["match_threshold"],
                    }
                except Exception as exc:
                    st.error(f"Processing failed unexpectedly: {exc}")
                    with st.expander("Technical details"):
                        st.exception(exc)

    if "kyc_results" in st.session_state:
        st.divider()
        render_results(st.session_state.kyc_results)


main()
