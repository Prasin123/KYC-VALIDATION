"""
PDF ingestion.

Renders every page of a (possibly multi-page) PDF to a PIL image at a
configurable DPI, and reports page geometry (in PDF points) so ROI configs
authored against the points coordinate space can be rescaled to whatever
pixel resolution the page was rendered at.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import fitz  # PyMuPDF
from PIL import Image


class PDFReadError(Exception):
    pass


@dataclass
class RenderedPage:
    page_number: int  # 1-indexed
    image: Image.Image
    pdf_size_pts: tuple[float, float]  # (width, height) in PDF points, i.e. 72dpi
    pixel_size: tuple[int, int]
    dpi: int
    rotation: int


def get_page_count(pdf_bytes: bytes) -> int:
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise PDFReadError(f"Could not open PDF: {e}") from e
    n = doc.page_count
    doc.close()
    return n


def render_pdf(pdf_bytes: bytes, dpi: int = 200) -> list[RenderedPage]:
    """Render every page of the PDF to a PIL image. Raises PDFReadError on a corrupt file."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise PDFReadError(f"Could not open PDF: {e}") from e

    if doc.page_count == 0:
        doc.close()
        raise PDFReadError("PDF has no pages.")

    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    pages = []
    for i in range(doc.page_count):
        try:
            page = doc[i]
            pix = page.get_pixmap(matrix=matrix)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            pages.append(RenderedPage(
                page_number=i + 1,
                image=img,
                pdf_size_pts=(round(page.rect.width, 1), round(page.rect.height, 1)),
                pixel_size=(pix.width, pix.height),
                dpi=dpi,
                rotation=page.rotation,
            ))
        except Exception as e:
            # One bad page must not take down the whole document (req: error handling).
            pages.append(RenderedPage(
                page_number=i + 1,
                image=Image.new("RGB", (100, 100), (255, 200, 200)),
                pdf_size_pts=(0, 0),
                pixel_size=(100, 100),
                dpi=dpi,
                rotation=0,
            ))
    doc.close()
    return pages


def render_single_page(pdf_bytes: bytes, page_number: int, dpi: int = 200) -> RenderedPage:
    """Re-render one page only (used when the user asks to 'reprocess' a single page)."""
    pages = render_pdf(pdf_bytes, dpi=dpi)
    for p in pages:
        if p.page_number == page_number:
            return p
    raise PDFReadError(f"Page {page_number} not found (document has {len(pages)} pages).")


def image_to_bytes(img: Image.Image, fmt: str = "PNG") -> bytes:
    buf = BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()
