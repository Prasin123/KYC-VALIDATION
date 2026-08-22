"""Document viewer: page navigation, ROI overlay, rotate/zoom, reorder/remove."""
from __future__ import annotations

import streamlit as st

from document.image_processor import rotate as rotate_image
from roi.config import DocumentTemplate
from roi.editor import draw_rois
from ui.upload import UploadedPage


def render_preview(pages: list[UploadedPage], doc_label: str, template: DocumentTemplate | None,
                    show_roi: bool, key_prefix: str) -> UploadedPage | None:
    """Renders a page navigator + preview for one document (KYC or Citizenship).
    Returns the currently selected UploadedPage (post any rotation applied this session)."""
    if not pages:
        return None

    n = len(pages)
    idx_key = f"{key_prefix}_page_idx"
    if idx_key not in st.session_state:
        st.session_state[idx_key] = 0
    st.session_state[idx_key] = min(st.session_state[idx_key], n - 1)

    cols = st.columns([1, 3, 1])
    with cols[0]:
        if st.button("◀ Prev", key=f"{key_prefix}_prev", disabled=st.session_state[idx_key] == 0):
            st.session_state[idx_key] -= 1
    with cols[2]:
        if st.button("Next ▶", key=f"{key_prefix}_next", disabled=st.session_state[idx_key] >= n - 1):
            st.session_state[idx_key] += 1

    idx = st.session_state[idx_key]
    page = pages[idx]
    st.markdown(f"**{doc_label} — Page {idx + 1} of {n}** ({page.source_label})")

    rot_key = f"{key_prefix}_rot_{idx}"
    rotation = st.session_state.get(rot_key, 0)
    rc1, rc2, rc3 = st.columns(3)
    if rc1.button("⟲ Rotate CCW", key=f"{key_prefix}_ccw_{idx}"):
        rotation = (rotation - 90) % 360
        st.session_state[rot_key] = rotation
    if rc2.button("⟳ Rotate CW", key=f"{key_prefix}_cw_{idx}"):
        rotation = (rotation + 90) % 360
        st.session_state[rot_key] = rotation
    zoom = rc3.slider("Zoom", 50, 200, 100, 10, key=f"{key_prefix}_zoom_{idx}", label_visibility="collapsed")

    display_img = page.image
    if rotation:
        display_img = rotate_image(display_img, rotation)

    if show_roi and template is not None:
        page_rois = template.rois_for_page(idx + 1)
        display_img = draw_rois(display_img, page_rois, native_size=page.native_size)

    w = int(display_img.width * zoom / 100)
    st.image(display_img, width=w)

    return page
