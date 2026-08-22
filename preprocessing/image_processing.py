"""
Configurable preprocessing operations, applied per-ROI according to that
ROI's field type. Every function takes and returns a numpy BGR or grayscale
array so they can be chained.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def pil_to_cv(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def cv_to_pil(arr: np.ndarray) -> Image.Image:
    if len(arr.shape) == 2:
        return Image.fromarray(arr)
    return Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))


def crop(arr: np.ndarray, box: list[float]) -> np.ndarray:
    h, w = arr.shape[:2]
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    if x1 <= x0 or y1 <= y0:
        return arr[0:1, 0:1]
    return arr[y0:y1, x0:x1]


def to_grayscale(arr: np.ndarray) -> np.ndarray:
    if len(arr.shape) == 2:
        return arr
    return cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)


def resize(arr: np.ndarray, scale: float) -> np.ndarray:
    if scale == 1.0:
        return arr
    h, w = arr.shape[:2]
    interp = cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA
    return cv2.resize(arr, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=interp)


def denoise(arr: np.ndarray) -> np.ndarray:
    gray = to_grayscale(arr)
    return cv2.fastNlMeansDenoising(gray, h=10)


def increase_contrast(arr: np.ndarray) -> np.ndarray:
    gray = to_grayscale(arr)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    return clahe.apply(gray)


def threshold(arr: np.ndarray) -> np.ndarray:
    gray = to_grayscale(arr)
    _, out = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return out


def adaptive_threshold(arr: np.ndarray) -> np.ndarray:
    gray = to_grayscale(arr)
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY, 25, 15)


def sharpen(arr: np.ndarray) -> np.ndarray:
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    return cv2.filter2D(arr, -1, kernel)


def deskew(arr: np.ndarray) -> np.ndarray:
    """Estimate and correct small rotations using the minimum-area bounding box of dark pixels."""
    gray = to_grayscale(arr)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = cv2.findNonZero(thresh)
    if coords is None or len(coords) < 20:
        return arr
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.3 or abs(angle) > 15:
        return arr  # not worth correcting / probably a bad estimate
    h, w = arr.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(arr, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


PIPELINES = {
    # ROI field type -> ordered list of operations, used by extraction/text.py
    "TEXT": [("resize", 2.0), ("grayscale", None), ("denoise", None), ("contrast", None)],
    "NAME": [("resize", 2.0), ("grayscale", None), ("denoise", None), ("contrast", None)],
    "ADDRESS": [("resize", 2.0), ("grayscale", None), ("denoise", None), ("contrast", None)],
    "NUMBER": [("resize", 3.0), ("grayscale", None), ("threshold", None)],
    "DATE": [("resize", 3.0), ("grayscale", None), ("threshold", None)],
    "CHECKBOX": [("grayscale", None), ("threshold", None)],
    "SIGNATURE": [("grayscale", None), ("threshold", None)],
    "DEFAULT": [("resize", 2.0), ("grayscale", None), ("contrast", None)],
}

_OPS = {
    "grayscale": lambda a, _: to_grayscale(a),
    "denoise": lambda a, _: denoise(a),
    "contrast": lambda a, _: increase_contrast(a),
    "threshold": lambda a, _: threshold(a),
    "adaptive_threshold": lambda a, _: adaptive_threshold(a),
    "sharpen": lambda a, _: sharpen(a),
    "deskew": lambda a, _: deskew(a),
    "resize": lambda a, scale: resize(a, scale),
}


def run_pipeline(arr: np.ndarray, field_type: str, debug: bool = False) -> tuple[np.ndarray, list[tuple[str, np.ndarray]]]:
    """
    Run the preprocessing pipeline appropriate for a given ROI field type.
    Returns the final array, and (if debug=True) a list of (step_name, intermediate_array)
    for the Debug Mode view.
    """
    steps = PIPELINES.get(field_type, PIPELINES["DEFAULT"])
    out = arr
    trace = [("original", out)] if debug else []
    for name, arg in steps:
        out = _OPS[name](out, arg)
        if debug:
            trace.append((name, out))
    return out, trace
