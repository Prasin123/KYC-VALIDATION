import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import cv2

from extraction.checkbox import detect_mark, detect_group, group_to_dict


def _circle(mark=None):
    img = np.full((30, 30), 255, dtype=np.uint8)
    cv2.circle(img, (15, 15), 12, (0,), 2)
    if mark == "x":
        cv2.line(img, (8, 8), (22, 22), (0,), 3)
        cv2.line(img, (8, 22), (22, 8), (0,), 3)
    elif mark == "fill":
        cv2.circle(img, (15, 15), 10, (0,), -1)
    elif mark == "speck":
        cv2.circle(img, (16, 14), 1, (0,), -1)
    return img


def test_blank_circle_is_unchecked():
    r = detect_mark(_circle(None))
    assert r.status == "UNCHECKED"
    assert r.checked is False


def test_x_mark_is_checked():
    r = detect_mark(_circle("x"))
    assert r.status == "CHECKED"
    assert r.checked is True


def test_filled_circle_is_checked():
    r = detect_mark(_circle("fill"))
    assert r.checked is True


def test_scanner_speck_does_not_register_as_checked():
    r = detect_mark(_circle("speck"))
    assert r.checked is not True


def test_empty_crop_does_not_crash():
    r = detect_mark(np.zeros((0, 0), dtype=np.uint8))
    assert r.ink_ratio == 0.0


def test_group_single_selection():
    crops = {"yes": _circle("x"), "no": _circle(None)}
    result = group_to_dict(detect_group(crops))
    assert result == {"yes": True, "no": False}


def test_group_double_marked_downgrades_weaker_to_review():
    crops = {"yes": _circle("x"), "no": _circle("x")}
    results = detect_group(crops)
    checked = [n for n, r in results.items() if r.checked is True]
    review = [n for n, r in results.items() if r.status == "REVIEW_REQUIRED"]
    assert len(checked) <= 1
    assert len(review) >= 1
