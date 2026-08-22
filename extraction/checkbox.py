"""
Checkbox / mark detection using computer vision, not OCR.

The form's checkboxes are printed as small circles (radio-button style).
A human marks one by drawing a tick, cross, dot, or filling it in by hand.
None of that is reliably "readable" as text, so this module instead measures
how much dark ink sits inside each option's circle relative to a blank
circle, and how that ink is distributed (a stray scanner speck vs. an actual
mark drawn by a pen).

Returns one of: checked=True, checked=False, or "REVIEW REQUIRED" when the
ink ratio sits in the ambiguous middle band -- per the app's rule that
ambiguous marks must never be auto-resolved.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# Ink-ratio thresholds, tuned as a starting point for scanned/photographed
# forms at ~150-300dpi. Treat these as configurable, not gospel -- if a
# particular scanner/lighting setup runs consistently darker or lighter,
# adjust via the ROI's confidence_threshold or recalibrate here.
INK_RATIO_UNCHECKED_MAX = 0.10
INK_RATIO_CHECKED_MIN = 0.22


@dataclass
class MarkResult:
    checked: bool | None  # None means REVIEW REQUIRED (ambiguous)
    ink_ratio: float
    confidence: float  # 0-100, how far the ink ratio sits from the ambiguous band
    status: str  # "CHECKED" | "UNCHECKED" | "REVIEW_REQUIRED"


def _ink_ratio(gray_crop: np.ndarray) -> float:
    """
    Ratio of dark ("ink") pixels within the *center* of the crop, using a
    circular mask so the checkbox's own printed circular outline (which is
    dark too, but not a mark) doesn't get counted. A pen mark -- tick,
    cross, dot, scribble -- necessarily crosses the interior, while an
    unmarked circle only has ink in a thin ring right at the edge.
    """
    if gray_crop.size == 0:
        return 0.0
    h, w = gray_crop.shape[:2]
    cy, cx = h / 2, w / 2
    radius = min(h, w) / 2
    yy, xx = np.ogrid[:h, :w]
    dist = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    # keep only the inner 65% of the radius -- excludes the printed ring
    mask = dist <= (radius * 0.65)
    if not mask.any():
        mask[:] = True

    _, thresh = cv2.threshold(gray_crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink_pixels = np.count_nonzero(thresh[mask])
    return float(ink_pixels) / int(mask.sum())


def detect_mark(gray_crop: np.ndarray) -> MarkResult:
    """Detect whether a single checkbox/circle ROI crop appears marked."""
    ratio = _ink_ratio(gray_crop)
    if ratio <= INK_RATIO_UNCHECKED_MAX:
        conf = round(100 * (1 - ratio / INK_RATIO_UNCHECKED_MAX), 1)
        return MarkResult(checked=False, ink_ratio=ratio, confidence=conf, status="UNCHECKED")
    if ratio >= INK_RATIO_CHECKED_MIN:
        conf = round(min(100, 100 * ratio / (INK_RATIO_CHECKED_MIN * 2)), 1)
        return MarkResult(checked=True, ink_ratio=ratio, confidence=conf, status="CHECKED")
    # ambiguous middle band
    mid = (INK_RATIO_UNCHECKED_MAX + INK_RATIO_CHECKED_MIN) / 2
    conf = round(100 * (1 - abs(ratio - mid) / (mid - INK_RATIO_UNCHECKED_MAX)), 1)
    return MarkResult(checked=None, ink_ratio=ratio, confidence=max(0.0, conf), status="REVIEW_REQUIRED")


def detect_group(option_crops: dict[str, np.ndarray]) -> dict[str, MarkResult]:
    """
    Detect marks across every option in a CHECKBOX_GROUP. If more than one
    option comes back CHECKED (shouldn't happen on a well-formed single-select
    form, but scans are messy), the weaker of the two is downgraded to
    REVIEW_REQUIRED rather than silently picking one -- the whole point of
    keeping a human in the loop.
    """
    results = {name: detect_mark(crop) for name, crop in option_crops.items()}
    checked = [name for name, r in results.items() if r.checked is True]
    if len(checked) > 1:
        checked_sorted = sorted(checked, key=lambda n: results[n].ink_ratio, reverse=True)
        for name in checked_sorted[1:]:
            r = results[name]
            results[name] = MarkResult(checked=None, ink_ratio=r.ink_ratio, confidence=r.confidence,
                                        status="REVIEW_REQUIRED")
    return results


def group_to_dict(results: dict[str, MarkResult]) -> dict[str, bool | None]:
    """Convenience: {"yes": true, "no": false} shape requested by the spec."""
    return {name: r.checked for name, r in results.items()}
