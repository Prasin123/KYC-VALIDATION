"""
Table extraction (the Family Details table on KYC page 2, and similar
repeated-row structures like the Student Information / Related Profession
tables).

A TABLE ROI in the config carries fixed `rows` (relation labels, which are
printed text and never OCR'd) and `columns` (the data fields to extract per
row). Actual per-cell boxes are supplied separately as `cell_boxes`
(populated via the ROI editor, since row heights vary per form) -- this
module just walks that grid and extracts each cell with extract_text_field.
"""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from extraction.text import ExtractedField, extract_text_field
from roi.config import ROI


@dataclass
class TableRow:
    row_label: str
    cells: dict[str, ExtractedField]


def extract_table(page_image: Image.Image, roi: ROI, native_size: tuple[float, float],
                   cell_boxes: dict[str, dict[str, list[float]]], debug: bool = False) -> list[TableRow]:
    """
    cell_boxes shape: {row_label: {column_name: [x0,y0,x1,y1]}}
    Only rows/columns present in cell_boxes are extracted -- rows the
    operator hasn't calibrated yet are simply skipped rather than guessed.
    """
    rows_out = []
    for row_label in (roi.rows or []):
        row_boxes = cell_boxes.get(row_label, {})
        if not row_boxes:
            continue
        cells = {}
        for col in (roi.columns or []):
            box = row_boxes.get(col)
            if not box:
                continue
            cell_roi = ROI(
                roi_name=f"{roi.roi_name}.{row_label}.{col}", field_type="TEXT", page=roi.page,
                language=roi.language, box=box, confidence_threshold=roi.confidence_threshold,
            )
            cells[col] = extract_text_field(page_image, cell_roi, native_size, debug=debug)
        rows_out.append(TableRow(row_label=row_label, cells=cells))
    return rows_out
