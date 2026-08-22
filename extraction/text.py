"""
Applies the ROI crop -> preprocessing -> OCR pipeline for TEXT/NAME/NUMBER/
DATE/ADDRESS field types, and packages the result (value, confidence,
source crop for the "show source ROI" debug view, and any error) in one
place so the UI layer doesn't need to know about OCR internals.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from ocr.tesseract_engine import get_engine
from preprocessing.image_processing import pil_to_cv, crop, run_pipeline, cv_to_pil
from roi.config import ROI
from utils.helpers import scale_box


@dataclass
class ExtractedField:
    roi_name: str
    field_type: str
    raw_value: str
    edited_value: str | None  # set once a human corrects it in the review UI
    confidence: float | None
    below_threshold: bool
    error: str | None
    source_crop: Image.Image | None
    debug_trace: list[tuple[str, np.ndarray]] | None = None

    @property
    def value(self) -> str:
        return self.edited_value if self.edited_value is not None else self.raw_value


def extract_text_field(page_image: Image.Image, roi: ROI, native_size: tuple[float, float],
                        debug: bool = False) -> ExtractedField:
    if not roi.box:
        return ExtractedField(roi.roi_name, roi.field_type, "", None, None, True,
                               "ROI has no box configured.", None)
    try:
        scaled_box = scale_box(roi.box, native_size, page_image.size)
        arr = pil_to_cv(page_image)
        crop_arr = crop(arr, scaled_box)
        if crop_arr.shape[0] < 2 or crop_arr.shape[1] < 2:
            return ExtractedField(roi.roi_name, roi.field_type, "", None, None, True,
                                   "ROI crop is empty or out of bounds.", None)
        processed, trace = run_pipeline(crop_arr, roi.field_type, debug=debug)
        engine = get_engine()
        result = engine.recognize(processed, language=roi.language or "english", field_type=roi.field_type)
        source_crop = cv_to_pil(crop_arr)
        below = result.confidence is not None and result.confidence < roi.confidence_threshold
        return ExtractedField(
            roi_name=roi.roi_name, field_type=roi.field_type, raw_value=result.text,
            edited_value=None, confidence=result.confidence, below_threshold=below,
            error=result.error, source_crop=source_crop,
            debug_trace=trace if debug else None,
        )
    except Exception as e:  # one bad field must never crash the whole document
        return ExtractedField(roi.roi_name, roi.field_type, "", None, None, True,
                               f"Extraction error: {e}", None)
