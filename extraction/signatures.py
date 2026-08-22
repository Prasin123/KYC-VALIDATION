"""
Signature / photo / thumbprint presence detection.

Per the spec, this module only ever answers "does this area appear
populated?" with a confidence score -- it makes no attempt to identify a
person from a signature, photo, or thumbprint, and never should.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# A signature/thumbprint box that's genuinely blank should have close to 0%
# ink; real pen strokes or an embedded photo push this well above the noise
# floor of a scanned/photographed blank box (paper texture, faint printed
# guide lines).
SIGNATURE_INK_MIN = 0.015
PHOTO_VARIANCE_MIN = 250.0  # a real photo has much more pixel variance than a blank/lightly-lined box


@dataclass
class PresenceResult:
    present: bool
    confidence: float  # 0-100
    metric: float
    status: str  # "PRESENT" | "NOT_DETECTED" | "REVIEW_REQUIRED"


def detect_signature_or_thumbprint(gray_crop: np.ndarray) -> PresenceResult:
    if gray_crop.size == 0:
        return PresenceResult(present=False, confidence=0.0, metric=0.0, status="NOT_DETECTED")
    _, thresh = cv2.threshold(gray_crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink_ratio = float(np.count_nonzero(thresh)) / thresh.size

    if ink_ratio < SIGNATURE_INK_MIN * 0.4:
        return PresenceResult(present=False, confidence=round(90 + 10 * (1 - ink_ratio), 1),
                               metric=ink_ratio, status="NOT_DETECTED")
    if ink_ratio >= SIGNATURE_INK_MIN:
        conf = round(min(100, 60 + ink_ratio * 400), 1)
        return PresenceResult(present=True, confidence=conf, metric=ink_ratio, status="PRESENT")
    return PresenceResult(present=False, confidence=40.0, metric=ink_ratio, status="REVIEW_REQUIRED")


def detect_photo(bgr_crop: np.ndarray) -> PresenceResult:
    """Photos are detected by pixel variance/texture (a real photo is visually
    'busy'; an empty printed photo box is mostly flat with a thin border)."""
    if bgr_crop.size == 0:
        return PresenceResult(present=False, confidence=0.0, metric=0.0, status="NOT_DETECTED")
    gray = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2GRAY) if len(bgr_crop.shape) == 3 else bgr_crop
    variance = float(gray.var())
    if variance >= PHOTO_VARIANCE_MIN:
        conf = round(min(100, 50 + variance / 20), 1)
        return PresenceResult(present=True, confidence=conf, metric=variance, status="PRESENT")
    if variance < PHOTO_VARIANCE_MIN * 0.3:
        return PresenceResult(present=False, confidence=80.0, metric=variance, status="NOT_DETECTED")
    return PresenceResult(present=False, confidence=35.0, metric=variance, status="REVIEW_REQUIRED")
