"""
ROI schema and JSON config load/save.

A "template" (one JSON file) describes every ROI for one document type
(a specific bank's form, or the citizenship certificate). Templates are
never hardcoded into the app logic -- app.py and the extraction/validation
modules only ever read this schema, so adding NIC Asia, NMB, etc. later is
purely a matter of dropping in another JSON file under configs/banks/.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

ROI_TYPES = [
    "TEXT", "NUMBER", "DATE", "NAME", "ADDRESS", "CHECKBOX", "CHECKBOX_GROUP",
    "SIGNATURE", "PHOTO", "THUMBPRINT", "TABLE", "OPTION_GROUP", "CUSTOM",
]
LANGUAGES = ["english", "nepali", "mixed"]
PRIORITIES = ["CRITICAL", "IMPORTANT", "OPTIONAL"]
VALIDATION_RULES = [
    "none", "match_citizenship", "match_field", "required", "numeric", "date", "phone", "email", "custom",
]


@dataclass
class CheckboxOption:
    value: str
    label: str
    box: list[float]  # [x0,y0,x1,y1] in template coordinate space


@dataclass
class ROI:
    roi_name: str
    field_type: str
    page: int
    language: str | None = "english"
    box: list[float] | None = None  # None for TABLE/composite fields with no single box
    options: list[dict] | None = None  # for CHECKBOX_GROUP / OPTION_GROUP
    columns: list[str] | None = None  # for TABLE
    rows: list[str] | None = None  # for TABLE
    required: bool = False
    priority: str = "OPTIONAL"
    validation: str = "none"
    validation_target: str | None = None
    confidence_threshold: float = 60.0
    preprocessing: str = "default"
    ocr_engine: str = "tesseract"
    calibrated: bool = True
    notes: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DocumentTemplate:
    template_id: str
    display_name: str
    document_type: str  # "kyc" | "citizenship"
    page_count: int
    rois: list[ROI] = field(default_factory=list)
    raw: dict = field(default_factory=dict)  # full original JSON, for fields this schema doesn't model yet

    def rois_for_page(self, page: int) -> list[ROI]:
        return [r for r in self.rois if r.page == page]

    def get_roi(self, name: str) -> ROI | None:
        for r in self.rois:
            if r.roi_name == name:
                return r
        return None


def _roi_from_dict(d: dict, default_page: int = 1) -> ROI:
    return ROI(
        roi_name=d.get("roi_name", "unnamed"),
        field_type=d.get("field_type", "TEXT"),
        page=d.get("page", default_page),
        language=d.get("language", "english"),
        box=d.get("box"),
        options=d.get("options"),
        columns=d.get("columns"),
        rows=d.get("rows"),
        required=d.get("required", False),
        priority=d.get("priority", "OPTIONAL"),
        validation=d.get("validation", "none"),
        validation_target=d.get("validation_target"),
        confidence_threshold=d.get("confidence_threshold", 60.0),
        preprocessing=d.get("preprocessing", "default"),
        ocr_engine=d.get("ocr_engine", "tesseract"),
        calibrated=d.get("calibrated", True),
        notes=d.get("notes"),
    )


def load_template(path: str | Path) -> DocumentTemplate:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    document_type = raw.get("document_type", "kyc")
    rois: list[ROI] = []

    if "rois" in raw:
        # bank KYC config shape (flat list of ROI dicts, each carries its own "page")
        for d in raw["rois"]:
            rois.append(_roi_from_dict(d))
    elif "pages" in raw:
        # citizenship config shape (fields grouped under numbered pages)
        for page_block in raw["pages"]:
            pno = page_block.get("page_number", 1)
            for d in page_block.get("fields", []):
                d = dict(d)
                d.setdefault("box", d.get("box"))
                rois.append(_roi_from_dict(d, default_page=pno))

    return DocumentTemplate(
        template_id=raw.get("template_id", Path(path).stem),
        display_name=raw.get("display_name", Path(path).stem),
        document_type=document_type,
        page_count=raw.get("page_count", max([r.page for r in rois], default=1)),
        rois=rois,
        raw=raw,
    )


def save_template(template: DocumentTemplate, path: str | Path) -> None:
    """Persist edits made in the ROI editor back to the flat 'rois' shape."""
    out = dict(template.raw)
    out["rois"] = [r.to_dict() for r in template.rois]
    out.pop("pages", None)  # normalize citizenship-style configs to the flat shape once edited
    out["document_type"] = template.document_type
    out["template_id"] = template.template_id
    out["display_name"] = template.display_name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)


def list_bank_templates(configs_dir: str | Path = "configs/banks") -> dict[str, list[Path]]:
    """Discover {bank_name: [template_paths]} without any hardcoded bank list."""
    root = Path(configs_dir)
    result: dict[str, list[Path]] = {}
    if not root.exists():
        return result
    for bank_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        templates = sorted(bank_dir.glob("*.json"))
        templates = [t for t in templates if t.name != "version.json"]
        if templates:
            result[bank_dir.name] = templates
    return result
