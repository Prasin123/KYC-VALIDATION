import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import fitz
import pytest

from document.pdf_processor import get_page_count, render_pdf, render_single_page, PDFReadError


def _make_pdf_bytes(n_pages=3):
    doc = fitz.open()
    for _ in range(n_pages):
        page = doc.new_page()
        page.insert_text((72, 72), "Test page")
    data = doc.tobytes()
    doc.close()
    return data


def test_get_page_count():
    assert get_page_count(_make_pdf_bytes(6)) == 6


def test_render_pdf_returns_one_image_per_page():
    pages = render_pdf(_make_pdf_bytes(4), dpi=100)
    assert len(pages) == 4
    assert [p.page_number for p in pages] == [1, 2, 3, 4]
    for p in pages:
        assert p.image.size[0] > 0 and p.image.size[1] > 0


def test_render_single_page():
    p = render_single_page(_make_pdf_bytes(5), page_number=3, dpi=100)
    assert p.page_number == 3


def test_corrupted_pdf_raises_readable_error():
    with pytest.raises(PDFReadError):
        get_page_count(b"this is not a pdf")


def test_render_single_page_out_of_range():
    with pytest.raises(PDFReadError):
        render_single_page(_make_pdf_bytes(2), page_number=99, dpi=100)
