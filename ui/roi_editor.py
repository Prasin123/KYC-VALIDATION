"""
Interactive ROI editor.

Primary interaction model is numeric X/Y/Width/Height fields with a live
preview overlay (robust, works everywhere, and is explicitly requested as a
fallback in the spec). If `streamlit-drawable-canvas` is importable, a
"draw directly on the page" tab is also offered -- marked Experimental,
since that package trails current Streamlit releases and can be flaky.
"""
from __future__ import annotations

import streamlit as st

from roi.config import DocumentTemplate, ROI_TYPES, LANGUAGES, PRIORITIES, VALIDATION_RULES
from roi.manager import ROIManager
from roi.editor import draw_rois, crop_roi
from ui.upload import UploadedPage

try:
    from streamlit_drawable_canvas import st_canvas
    _CANVAS_AVAILABLE = True
except Exception:
    _CANVAS_AVAILABLE = False


def _roi_form(manager: ROIManager, page_number: int, existing_name: str | None = None):
    roi = manager.get(existing_name) if existing_name else None
    with st.form(key=f"roi_form_{existing_name or 'new'}_{page_number}"):
        name = st.text_input("ROI Name:", value=roi.roi_name if roi else "")
        field_type = st.selectbox("Field Type:", ROI_TYPES,
                                   index=ROI_TYPES.index(roi.field_type) if roi else 0)
        language = st.selectbox("Language:", LANGUAGES,
                                 index=LANGUAGES.index(roi.language) if roi and roi.language in LANGUAGES else 0)
        ocr_engine = st.selectbox("OCR Engine:", ["tesseract"], index=0)
        required = st.checkbox("Required", value=roi.required if roi else False)
        priority = st.selectbox("Priority:", PRIORITIES,
                                 index=PRIORITIES.index(roi.priority) if roi else 2)
        validation = st.selectbox("Validation:", VALIDATION_RULES,
                                   index=VALIDATION_RULES.index(roi.validation) if roi else 0)
        validation_target = st.text_input("Validation target (e.g. citizenship.full_name):",
                                           value=roi.validation_target or "" if roi else "")
        conf_threshold = st.slider("Confidence Threshold:", 0, 100,
                                    int(roi.confidence_threshold) if roi else 60)

        st.caption("Position (in the template's native coordinate space)")
        c1, c2, c3, c4 = st.columns(4)
        box = roi.box if roi and roi.box else [50, 50, 200, 80]
        x0 = c1.number_input("X", value=float(box[0]))
        y0 = c2.number_input("Y", value=float(box[1]))
        x1 = c3.number_input("Width", value=float(box[2] - box[0]), min_value=1.0) + x0
        y1 = c4.number_input("Height", value=float(box[3] - box[1]), min_value=1.0) + y0

        submitted = st.form_submit_button("Save ROI")
        if submitted:
            if not name:
                st.error("ROI Name is required.")
                return
            fields = dict(
                field_type=field_type, language=language, ocr_engine=ocr_engine,
                required=required, priority=priority, validation=validation,
                validation_target=validation_target or None,
                confidence_threshold=conf_threshold,
            )
            if roi:
                manager.set_field(existing_name, **fields)
                manager.update_box(existing_name, [x0, y0, x1, y1])
                if name != existing_name:
                    manager.rename(existing_name, name)
            else:
                manager.add_roi(roi_name=name, page=page_number, box=[x0, y0, x1, y1], **fields)
            st.success(f"Saved ROI '{name}'.")
            st.rerun()


def render_roi_editor(manager: ROIManager, page: UploadedPage, page_number: int):
    st.subheader(f"ROI Editor — Page {page_number}")

    page_rois = manager.list_for_page(page_number)
    names = [r.roi_name for r in page_rois]

    left, right = st.columns([2, 1])
    with left:
        highlight = st.session_state.get("roi_editor_highlight")
        preview = draw_rois(page.image, page_rois, native_size=page.native_size, highlight=highlight)
        st.image(preview, width=min(900, preview.width))

    with right:
        st.markdown("**ROIs on this page**")
        for r in page_rois:
            cols = st.columns([3, 1, 1, 1])
            if cols[0].button(r.roi_name, key=f"select_{r.roi_name}"):
                st.session_state["roi_editor_highlight"] = r.roi_name
                st.session_state["roi_editor_selected"] = r.roi_name
                st.rerun()
            if cols[1].button("⧉", key=f"dup_{r.roi_name}", help="Duplicate"):
                manager.duplicate(r.roi_name)
                st.rerun()
            if cols[2].button("🗑", key=f"del_{r.roi_name}", help="Delete"):
                manager.delete(r.roi_name)
                st.rerun()
            if not r.calibrated:
                cols[3].caption("⚠")

        st.divider()
        selected = st.session_state.get("roi_editor_selected")
        tab_edit, tab_new = st.tabs(["Edit selected", "+ Add ROI"])
        with tab_edit:
            if selected and manager.get(selected):
                _roi_form(manager, page_number, existing_name=selected)
                crop = crop_roi(page.image, manager.get(selected), page.native_size)
                if crop:
                    st.caption("Source crop")
                    st.image(crop)
            else:
                st.caption("Select an ROI on the left to edit it.")
        with tab_new:
            _roi_form(manager, page_number, existing_name=None)

    if _CANVAS_AVAILABLE:
        with st.expander("Draw ROI directly on the page (Experimental)"):
            st.caption("Draw a rectangle, then use the numeric form above to name and save it "
                       "at the coordinates shown.")
            canvas_result = st_canvas(
                fill_color="rgba(255, 0, 0, 0.1)", stroke_width=2, stroke_color="#e02020",
                background_image=page.image, height=min(700, page.image.height),
                width=min(900, page.image.width), drawing_mode="rect",
                key=f"canvas_{page_number}",
            )
            if canvas_result.json_data and canvas_result.json_data.get("objects"):
                obj = canvas_result.json_data["objects"][-1]
                sx = page.image.width / min(900, page.image.width)
                sy = page.image.height / min(700, page.image.height)
                x0, y0 = obj["left"] * sx, obj["top"] * sy
                w, h = obj["width"] * obj.get("scaleX", 1) * sx, obj["height"] * obj.get("scaleY", 1) * sy
                st.write(f"Last drawn rectangle (image pixels): X={x0:.0f}, Y={y0:.0f}, "
                         f"Width={w:.0f}, Height={h:.0f}")
    else:
        st.caption("Tip: install `streamlit-drawable-canvas` to enable drawing ROIs directly on the page. "
                   "The numeric editor above works without it.")
