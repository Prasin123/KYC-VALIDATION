"""
ROI CRUD manager. Wraps a DocumentTemplate with add/edit/delete/duplicate
operations, used by the Streamlit ROI editor UI (ui/roi_editor.py). Kept
separate from the Streamlit code so it's independently testable.
"""
from __future__ import annotations

import copy

from roi.config import ROI, DocumentTemplate, ROI_TYPES
from utils.helpers import new_id


class ROIManager:
    def __init__(self, template: DocumentTemplate):
        self.template = template

    # -- create -----------------------------------------------------------
    def add_roi(self, roi_name: str, field_type: str, page: int, box: list[float], **kwargs) -> ROI:
        if field_type not in ROI_TYPES:
            raise ValueError(f"Unknown field_type {field_type!r}; must be one of {ROI_TYPES}")
        if self.template.get_roi(roi_name):
            roi_name = f"{roi_name}_{new_id('')}"
        roi = ROI(roi_name=roi_name, field_type=field_type, page=page, box=box, **kwargs)
        self.template.rois.append(roi)
        return roi

    # -- read ---------------------------------------------------------------
    def get(self, roi_name: str) -> ROI | None:
        return self.template.get_roi(roi_name)

    def list_for_page(self, page: int) -> list[ROI]:
        return self.template.rois_for_page(page)

    # -- update ---------------------------------------------------------------
    def update_box(self, roi_name: str, box: list[float]) -> None:
        roi = self._require(roi_name)
        roi.box = box
        roi.calibrated = True  # a human just placed it, so trust it

    def move(self, roi_name: str, dx: float, dy: float) -> None:
        roi = self._require(roi_name)
        if not roi.box:
            return
        x0, y0, x1, y1 = roi.box
        roi.box = [x0 + dx, y0 + dy, x1 + dx, y1 + dy]

    def resize(self, roi_name: str, width: float, height: float) -> None:
        roi = self._require(roi_name)
        if not roi.box:
            return
        x0, y0, _, _ = roi.box
        roi.box = [x0, y0, x0 + width, y0 + height]

    def rename(self, old_name: str, new_name: str) -> None:
        roi = self._require(old_name)
        if new_name != old_name and self.template.get_roi(new_name):
            raise ValueError(f"An ROI named {new_name!r} already exists.")
        roi.roi_name = new_name

    def set_field(self, roi_name: str, **fields) -> None:
        roi = self._require(roi_name)
        for k, v in fields.items():
            if hasattr(roi, k):
                setattr(roi, k, v)

    # -- delete / duplicate ---------------------------------------------------
    def delete(self, roi_name: str) -> None:
        self.template.rois = [r for r in self.template.rois if r.roi_name != roi_name]

    def duplicate(self, roi_name: str, new_name: str | None = None) -> ROI:
        roi = self._require(roi_name)
        clone = copy.deepcopy(roi)
        clone.roi_name = new_name or f"{roi_name}_copy"
        if self.template.get_roi(clone.roi_name):
            clone.roi_name = f"{clone.roi_name}_{new_id('')}"
        self.template.rois.append(clone)
        return clone

    def _require(self, roi_name: str) -> ROI:
        roi = self.template.get_roi(roi_name)
        if roi is None:
            raise KeyError(f"No ROI named {roi_name!r}")
        return roi
