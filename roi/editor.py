"""
Rendering helpers for the ROI editor: draws ROI boxes over a rendered page
image so the operator can see (and, via the Streamlit UI, adjust) them.
Coordinate translation between a template's native coordinate space (PDF
points, or citizenship-template reference pixels) and the actual rendered
image size lives here too.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from roi.config import ROI
from utils.helpers import scale_box

PRIORITY_COLORS = {
    "CRITICAL": (220, 40, 40),
    "IMPORTANT": (230, 150, 20),
    "OPTIONAL": (40, 120, 220),
}
TYPE_COLORS = {
    "CHECKBOX_GROUP": (150, 40, 200),
    "SIGNATURE": (0, 150, 100),
    "PHOTO": (0, 150, 100),
    "THUMBPRINT": (0, 150, 100),
    "TABLE": (100, 100, 100),
}


def _color_for(roi: ROI) -> tuple[int, int, int]:
    return TYPE_COLORS.get(roi.field_type, PRIORITY_COLORS.get(roi.priority, (80, 80, 80)))


def draw_rois(
    page_image: Image.Image,
    rois: list[ROI],
    native_size: tuple[float, float],
    highlight: str | None = None,
    show_labels: bool = True,
) -> Image.Image:
    """
    Draw ROI boxes onto a copy of page_image. `native_size` is the (w, h)
    the ROI boxes were authored against (e.g. PDF points) -- boxes are
    rescaled to page_image's actual pixel size before drawing.
    """
    img = page_image.copy()
    draw = ImageDraw.Draw(img)
    to_size = img.size
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for roi in rois:
        color = _color_for(roi)
        width = 4 if roi.roi_name == highlight else 2
        boxes = []
        if roi.field_type == "CHECKBOX_GROUP" and roi.options:
            boxes = [(opt.get("box"), opt.get("label", "")) for opt in roi.options if opt.get("box")]
        elif roi.box:
            boxes = [(roi.box, roi.roi_name)]

        for box, label in boxes:
            if not box:
                continue
            scaled = scale_box(box, native_size, to_size)
            draw.rectangle(scaled, outline=color, width=width)
            if show_labels and label:
                tx, ty = scaled[0], max(0, scaled[1] - 12)
                if font:
                    draw.text((tx, ty), label, fill=color, font=font)
                else:
                    draw.text((tx, ty), label, fill=color)
    return img


def crop_roi(page_image: Image.Image, roi: ROI, native_size: tuple[float, float]) -> Image.Image | None:
    """Crop the region of `page_image` corresponding to `roi`, rescaled from native_size."""
    if not roi.box:
        return None
    scaled = scale_box(roi.box, native_size, page_image.size)
    x0, y0, x1, y1 = [int(round(v)) for v in scaled]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(page_image.width, x1), min(page_image.height, y1)
    if x1 <= x0 or y1 <= y0:
        return None
    return page_image.crop((x0, y0, x1, y1))
