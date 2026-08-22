"""
Upload UI: two clearly separated uploaders (KYC form / Citizenship), each
accepting multiple files (PDF and/or several page images) so the app can
construct the page sequence automatically regardless of whether the operator
uploads one multi-page PDF or a stack of individually scanned page images.
"""
from __future__ import annotations

from dataclasses import dataclass

import streamlit as st
from PIL import Image

from document.image_processor import load_image, ImageReadError
from document.pdf_processor import render_pdf, PDFReadError

SUPPORTED_TYPES = ["pdf", "jpg", "jpeg", "png"]


@dataclass
class UploadedPage:
    source_label: str  # e.g. "page1.jpg" or "form.pdf (p.2)"
    image: Image.Image
    native_size: tuple[float, float]  # coordinate space the ROI config expects (pts for PDF, px for images)
    page_number: int  # position within this document
    is_from_pdf: bool


def _ingest_files(files, dpi: int) -> tuple[list[UploadedPage], list[str]]:
    pages: list[UploadedPage] = []
    errors: list[str] = []
    counter = 1
    for f in files:
        data = f.read()
        name = f.name
        ext = name.lower().rsplit(".", 1)[-1]
        try:
            if ext == "pdf":
                rendered = render_pdf(data, dpi=dpi)
                for rp in rendered:
                    pages.append(UploadedPage(
                        source_label=f"{name} (p.{rp.page_number})",
                        image=rp.image, native_size=rp.pdf_size_pts,
                        page_number=counter, is_from_pdf=True,
                    ))
                    counter += 1
            elif ext in ("jpg", "jpeg", "png"):
                loaded = load_image(data)
                pages.append(UploadedPage(
                    source_label=name, image=loaded.image,
                    native_size=(float(loaded.image.width), float(loaded.image.height)),
                    page_number=counter, is_from_pdf=False,
                ))
                counter += 1
            else:
                errors.append(f"{name}: unsupported file type '.{ext}'.")
        except (PDFReadError, ImageReadError) as e:
            errors.append(f"{name}: {e}")
        except Exception as e:
            errors.append(f"{name}: unexpected error ({e}).")
    return pages, errors


def render_kyc_uploader(dpi: int) -> list[UploadedPage]:
    st.subheader("Upload KYC Form")
    files = st.file_uploader(
        "Drag and drop files here (PDF / JPG / JPEG / PNG, multiple pages supported)",
        type=SUPPORTED_TYPES, accept_multiple_files=True, key="kyc_uploader",
    )
    if not files:
        return []
    pages, errors = _ingest_files(files, dpi)
    for e in errors:
        st.error(e)
    if pages:
        st.caption(f"KYC FORM — {len(pages)} page(s) loaded")
    return pages


def render_citizenship_uploader(dpi: int) -> list[UploadedPage]:
    st.subheader("Upload Citizenship")
    files = st.file_uploader(
        "Drag and drop files here (PDF / JPG / JPEG / PNG — front + back supported)",
        type=SUPPORTED_TYPES, accept_multiple_files=True, key="citizenship_uploader",
    )
    if not files:
        return []
    pages, errors = _ingest_files(files, dpi)
    for e in errors:
        st.error(e)
    if pages:
        labels = ["Front", "Back"] + [f"Page {i}" for i in range(3, len(pages) + 1)]
        st.caption(f"CITIZENSHIP — {len(pages)} page(s) loaded "
                   f"({', '.join(labels[:len(pages)])})")
    return pages
