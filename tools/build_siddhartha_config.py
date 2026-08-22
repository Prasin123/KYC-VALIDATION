"""
Builds configs/banks/siddhartha/personal_account_opening.json from the real
vector geometry of the supplied Siddhartha Bank "Personal Account Opening
Form Single/Joint" PDF (SBL-PRT-002), using tools/inspect_pdf_layout.py.

Text-field ROI boxes are computed as: start just to the right of (or below)
the printed label, and extend to a width that keeps them inside the visible
underline/box on the form. Checkbox ROIs use the *exact* circle coordinates
recovered from the PDF's vector drawings, so those are precise. Text-field
boxes are a good starting point but are heuristic -- an operator should
sanity-check them once against a real scanned copy in the ROI editor and
adjust as needed. Every field carries a "calibrated" flag reflecting this.

Re-run this script if Siddhartha Bank revises the form (point it at the new
PDF) rather than hand-editing hundreds of coordinates.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inspect_pdf_layout import extract_words, extract_checkbox_circles, pair_checkbox_labels, find_phrase
import fitz

PDF_PATH = "/mnt/user-data/uploads/Personal_account_opening_form_single-joint.pdf"
OUT_PATH = Path(__file__).parent.parent / "configs" / "banks" / "siddhartha" / "personal_account_opening.json"

doc = fitz.open(PDF_PATH)
PAGE_WORDS = {i + 1: extract_words(doc[i]) for i in range(doc.page_count)}
PAGE_SIZE = [round(doc[0].rect.width, 1), round(doc[0].rect.height, 1)]

rois = []


def label_end(page, text, occurrence=0):
    w = find_phrase(PAGE_WORDS[page], text, occurrence)
    return w


def text_field(name, page, label_text, width=140, height=16, dx=6, dy=-3, occurrence=0,
                field_type="TEXT", language="english", required=False, priority="OPTIONAL",
                validation="none", validation_target=None, notes=None, y_override=None,
                below=False):
    """Anchor a text ROI just after (or below) a known label word."""
    w = label_end(page, label_text, occurrence)
    calibrated = w is not None
    if w is None:
        box = [0, 0, width, height]
    elif below:
        box = [round(w.x0, 1), round(w.y1 + 4, 1), round(w.x0 + width, 1), round(w.y1 + 4 + height, 1)]
    else:
        y0 = y_override if y_override is not None else w.y0 + dy
        box = [round(w.x1 + dx, 1), round(y0, 1), round(w.x1 + dx + width, 1), round(y0 + height, 1)]
    # keep boxes inside the page
    page_w, page_h = PAGE_SIZE
    box = [max(0, box[0]), max(0, box[1]), min(page_w, box[2]), min(page_h, box[3])]
    rois.append({
        "roi_name": name, "field_type": field_type, "page": page, "language": language,
        "box": box, "required": required, "priority": priority,
        "validation": validation, "validation_target": validation_target,
        "calibrated": calibrated, "notes": notes,
    })


def checkbox_group(name, page, expected_labels, priority="OPTIONAL", validation="none",
                    validation_target=None, notes=None):
    """Build a CHECKBOX_GROUP from the exact circle geometry, matched by expected label text."""
    words = PAGE_WORDS[page]
    circles = extract_checkbox_circles(doc[page - 1])
    pairs = pair_checkbox_labels(words, circles)
    options = []
    for want in expected_labels:
        best = None
        for p in pairs:
            if p.label and want.lower() in p.label.lower():
                best = p
                break
        if best:
            options.append({"value": want.lower().replace(" ", "_").replace(".", ""),
                             "label": want, "box": best.box})
    rois.append({
        "roi_name": name, "field_type": "CHECKBOX_GROUP", "page": page, "language": "english",
        "options": options, "required": False, "priority": priority,
        "validation": validation, "validation_target": validation_target,
        "calibrated": len(options) == len(expected_labels), "notes": notes,
    })


# ---------------------------------------------------------------------------
# PAGE 1 -- Siddhartha relationship, account details, Applicant 1 personal info
# ---------------------------------------------------------------------------
checkbox_group("existing_siddhartha_account", 1, ["Yes", "No"], priority="OPTIONAL",
                notes="Do you already have an account with Siddhartha Bank Limited?")
text_field("existing_account_number", 1, "Existing A/C No", width=150, priority="OPTIONAL")

checkbox_group("relation_with_other_banks", 1, ["Yes", "No"], priority="OPTIONAL")
text_field("other_bank_name", 1, "Name of Bank", width=160, priority="OPTIONAL")
text_field("other_bank_account_no", 1, "Account No.", width=120, priority="OPTIONAL", occurrence=0)
text_field("other_bank_avg_balance", 1, "Avg. Balance", width=100, priority="OPTIONAL")
checkbox_group("other_bank_credit_facility", 1, ["Yes", "No"], priority="OPTIONAL")

checkbox_group("account_category", 1, ["Current", "Call", "Saving", "Others"], priority="IMPORTANT",
                notes="Account Category radio group. NOTE: 'Saving' also appears in Purpose of A/C Opening group below -- verify page-region if re-running on a different layout.")
checkbox_group("account_currency", 1, ["NPR", "USD", "EURO", "Others"], priority="IMPORTANT")
checkbox_group("account_purpose", 1, ["Saving", "Payroll", "Remittance", "Others"], priority="OPTIONAL")

text_field("applicant_1_name", 1, "1. Applicant Name", width=380, priority="CRITICAL",
           field_type="NAME", validation="match_citizenship", validation_target="citizenship.full_name")
text_field("applicant_2_name", 1, "2. Applicant Name", width=380, priority="OPTIONAL", field_type="NAME")
text_field("applicant_3_name", 1, "3. Applicant Name", width=380, priority="OPTIONAL", field_type="NAME")

# Minor's account block
text_field("minor_birth_reg_no", 1, "Birth Reg. No", width=130, priority="OPTIONAL")
text_field("minor_guardian_name", 1, "Guardian's Name", width=220, priority="OPTIONAL", field_type="NAME")
text_field("minor_guardian_relationship", 1, "Relationship with the Minor", width=150, priority="OPTIONAL")
text_field("minor_guardian_address", 1, "Guardian's Address", width=220, priority="OPTIONAL", field_type="ADDRESS")

# Applicant 1 personal information
checkbox_group("gender_applicant_1", 1, ["Male", "Female", "Others"], priority="IMPORTANT",
                validation="match_citizenship", validation_target="citizenship.gender")
checkbox_group("marital_status_applicant_1", 1, ["Married", "Single", "Others"], priority="OPTIONAL")

text_field("dob_applicant_1", 1, "Date of Birth:", width=140, priority="CRITICAL", field_type="DATE",
           validation="match_citizenship", validation_target="citizenship.dob")
text_field("nationality_applicant_1", 1, "Nationality", width=130, priority="IMPORTANT")

text_field("citizenship_no_applicant_1", 1, "Citizenship No.", width=150, priority="CRITICAL",
           validation="match_citizenship", validation_target="citizenship.citizenship_number")
text_field("citizenship_issue_date_applicant_1", 1, "Issue Date:", width=140, priority="CRITICAL",
           field_type="DATE", occurrence=1,
           validation="match_citizenship", validation_target="citizenship.issue_date")
text_field("citizenship_issue_district_applicant_1", 1, "Issue District", width=140, priority="IMPORTANT")

text_field("national_id_no_applicant_1", 1, "National ID No.", width=150, priority="OPTIONAL")
text_field("national_id_issue_date_applicant_1", 1, "Issue Date:", width=140, priority="OPTIONAL",
           field_type="DATE", occurrence=2)
text_field("national_id_district_applicant_1", 1, "Issued District/Place", width=140, priority="OPTIONAL", occurrence=0)

text_field("passport_no_applicant_1", 1, "Passport No.", width=150, priority="OPTIONAL")
text_field("passport_issue_date_applicant_1", 1, "Issue Date:", width=140, priority="OPTIONAL",
           field_type="DATE", occurrence=3)
text_field("passport_issue_district_applicant_1", 1, "Issue District/Place", width=140, priority="OPTIONAL")
text_field("passport_expiry_date_applicant_1", 1, "Passport Expiry Date:", width=140, priority="OPTIONAL",
           field_type="DATE")
text_field("social_media_id_applicant_1", 1, "Social Media ID", width=180, priority="OPTIONAL")

text_field("other_id_type_applicant_1", 1, "Type of ID Document", width=180, priority="OPTIONAL")
text_field("other_id_number_applicant_1", 1, "ID Document Number", width=160, priority="OPTIONAL")
text_field("other_id_office_applicant_1", 1, "Name and address of ID Document issuing office",
           width=300, priority="OPTIONAL", below=True, field_type="ADDRESS")
text_field("other_id_issue_date_applicant_1", 1, "Issue Date:", width=140, priority="OPTIONAL",
           field_type="DATE", occurrence=4)
text_field("other_id_expiry_date_applicant_1", 1, "Expiry Date:", width=140, priority="OPTIONAL",
           field_type="DATE", occurrence=1,
           notes="occurrence=1 because 'Passport Expiry Date:' also contains the substring 'Expiry Date:'.")

checkbox_group("education_applicant_1", 1,
                ["Illiterate", "Literate", "SEE", "+2", "Graduate", "Post Graduate", "Others"],
                priority="OPTIONAL")
text_field("university_applicant_1", 1, "University", width=200, priority="OPTIONAL")
text_field("pan_number_applicant_1", 1, "PAN Number", width=140, priority="OPTIONAL")
text_field("pan_issue_date_applicant_1", 1, "Issue Date:", width=140, priority="OPTIONAL",
           field_type="DATE", occurrence=5)
text_field("pan_issued_district_applicant_1", 1, "Issued District/Place", width=140, priority="OPTIONAL", occurrence=1)

# ---------------------------------------------------------------------------
# PAGE 2 -- Non-resident block, Permanent/Correspondence address, Family, Occupation
# ---------------------------------------------------------------------------
text_field("nrn_local_contact", 2, "Local Contact Person/Organization", width=220, priority="OPTIONAL")
text_field("nrn_phone", 2, "Phone No.", width=140, priority="OPTIONAL")
text_field("nrn_address", 2, "Address", width=200, priority="OPTIONAL", field_type="ADDRESS")
text_field("nrn_visa_no", 2, "Visa No.", width=140, priority="OPTIONAL")

for prefix, occ in [("permanent", 0), ("correspondence", 1)]:
    text_field(f"{prefix}_post_box", 2, "Post Box", width=110, priority="OPTIONAL", occurrence=occ)
    text_field(f"{prefix}_house_no", 2, "House No.", width=110, priority="OPTIONAL", occurrence=occ)
    text_field(f"{prefix}_street_tole", 2, "Street/Tole", width=140, priority="IMPORTANT", occurrence=occ)
    text_field(f"{prefix}_ward_no", 2, "Ward No.", width=80, priority="IMPORTANT", occurrence=occ)
    text_field(f"{prefix}_municipality", 2, "Municipality", width=140, priority="IMPORTANT", occurrence=occ)
    text_field(f"{prefix}_district", 2, "District", width=120, priority="IMPORTANT", occurrence=occ,
               validation=("match_citizenship" if prefix == "permanent" else "none"),
               validation_target=("citizenship.permanent_address_district" if prefix == "permanent" else None))
    text_field(f"{prefix}_province", 2, "Province", width=120, priority="OPTIONAL", occurrence=occ)
    text_field(f"{prefix}_country", 2, "Country", width=110, priority="OPTIONAL", occurrence=occ)
    text_field(f"{prefix}_phone_res", 2, "Phone: (Res)", width=120, priority="OPTIONAL", occurrence=occ)
    text_field(f"{prefix}_phone_work", 2, "Work", width=110, priority="OPTIONAL", occurrence=occ)
    text_field(f"{prefix}_mobile", 2, "Mobile", width=120, priority="IMPORTANT", occurrence=occ)
    text_field(f"{prefix}_email", 2, "e-mail", width=160, priority="OPTIONAL", occurrence=occ)

checkbox_group("present_address_verification_doc", 2,
                ["Land Ownership Certificate", "Voter's ID Card", "Phone Line/Electricity/Water Bill", "Others"],
                priority="OPTIONAL")

# Family details table -- fixed relation rows, columns anchored per row via S.No.
family_relations = ["Spouse", "Father", "Mother", "Grand Father", "Grand Mother",
                     "Son", "Daughter in Law", "Father in Law"]
rois.append({
    "roi_name": "family_details_table", "field_type": "TABLE", "page": 2, "language": "mixed",
    "box": None, "required": False, "priority": "IMPORTANT",
    "validation": "none", "validation_target": None, "calibrated": False,
    "columns": ["relation", "name_surname", "id_number", "issue_date", "issued_district"],
    "rows": family_relations,
    "notes": ("Row positions were not individually re-derived by this script; use the ROI editor to drop "
              "one row of column ROIs (name/ID/issue date/district) per relation listed in the Family "
              "Details table on page 2. The relation labels themselves are fixed print, not something to OCR."),
})

checkbox_group("occupation", 2,
                ["Professional", "Govt. Sector", "Business", "Private Sector", "Public Sector", "Others"],
                priority="IMPORTANT")

# ---------------------------------------------------------------------------
# PAGE 3 -- Source of income, related profession, students, nominee, services,
#           statement prefs, self declaration
# ---------------------------------------------------------------------------
checkbox_group("source_of_income", 3,
                ["Own Business", "Salary", "Sale of Assets", "Remittance", "Return on Investments", "Others"],
                priority="IMPORTANT")

text_field("nominee_name", 3, "Mr./Mrs./Ms.", width=260, priority="OPTIONAL", field_type="NAME", occurrence=1)
text_field("nominee_account_no", 3, "Nominee's A/c No.", width=150, priority="OPTIONAL")
text_field("nominee_relation", 3, "Relation to me", width=140, priority="OPTIONAL")
text_field("nominee_guardian_name", 3, "Name of Nominee's Mother/Father/Spouse", width=260,
           priority="OPTIONAL", field_type="NAME", below=True)
text_field("nominee_dob", 3, "Date of Birth of Nominee", width=140, priority="OPTIONAL", field_type="DATE")
text_field("nominee_age", 3, "Age", width=60, priority="OPTIONAL", field_type="NUMBER")
text_field("nominee_tel", 3, "Tel No.", width=120, priority="OPTIONAL")
text_field("nominee_id_type", 3, "Type of ID", width=140, priority="OPTIONAL")
text_field("nominee_id_no", 3, "ID No.", width=140, priority="OPTIONAL")
text_field("nominee_id_issue_district", 3, "Issue District", width=140, priority="OPTIONAL")
text_field("nominee_id_issue_date", 3, "Issue Date:", width=140, priority="OPTIONAL", field_type="DATE")
text_field("nominee_permanent_address", 3, "Permanent Address", width=300, priority="OPTIONAL",
           field_type="ADDRESS", below=True)

checkbox_group("service_debit_card", 3, ["Yes", "No"], priority="OPTIONAL")
checkbox_group("service_mobile_banking", 3, ["Yes", "No"], priority="OPTIONAL")
checkbox_group("service_demat", 3, ["Yes", "No"], priority="OPTIONAL")
checkbox_group("service_cheque_book", 3, ["Yes", "No"], priority="OPTIONAL")
checkbox_group("service_locker", 3, ["Yes", "No"], priority="OPTIONAL")

checkbox_group("statement_frequency", 3, ["Monthly", "Quarterly", "Half Yearly", "Annually", "On Demand"],
                priority="OPTIONAL")
checkbox_group("statement_delivery", 3, ["Post", "Email", "Courier", "Self Collect"], priority="OPTIONAL")

checkbox_group("declaration_convicted", 3, ["No", "Yes"], priority="IMPORTANT",
                notes="Declaration of Convicted/Non-Convicted for any crime in past.")
text_field("declaration_convicted_detail", 3, "please specify", width=220, priority="OPTIONAL")
checkbox_group("declaration_foreign_residence", 3, ["No", "Yes"], priority="IMPORTANT",
                notes="Do you hold Residence/Citizenship/Green card of foreign country?")
checkbox_group("residential_status", 3, ["Citizen", "Permanent Resident", "Resident"], priority="OPTIONAL")

# ---------------------------------------------------------------------------
# PAGE 4 -- PEP declaration, Beneficial owner, Introduction, Signature specimen
# ---------------------------------------------------------------------------
checkbox_group("pep_declaration", 4, ["Yes", "No"], priority="CRITICAL",
                notes="Are you a Politically Exposed Person? The app only records what is checked on the "
                      "form -- it does not make its own PEP determination.")
text_field("pep_name", 4, "please specify the name of PEP", width=220, priority="OPTIONAL", field_type="NAME")
text_field("pep_relationship", 4, "Relationship with you", width=160, priority="OPTIONAL")
text_field("pep_position", 4, "Position of PEP", width=160, priority="OPTIONAL")

checkbox_group("beneficial_owner_declaration", 4, ["No", "Yes"], priority="IMPORTANT")
text_field("beneficial_owner_name", 4, "Please specify the name", width=220, priority="OPTIONAL", field_type="NAME")
text_field("beneficial_owner_relationship", 4, "Relationship with you", width=160, priority="OPTIONAL", occurrence=1)

text_field("introduced_by", 4, "Introduced by", width=260, priority="OPTIONAL", field_type="NAME")
text_field("introducer_contact_no", 4, "Contact No.", width=140, priority="OPTIONAL")
text_field("introducer_account_no", 4, "Account No.", width=140, priority="OPTIONAL")

checkbox_group("account_operation_mode", 4, ["Single", "Any Two", "As per special instruction"],
                priority="OPTIONAL")

for n in range(1, 5):
    rois.append({
        "roi_name": f"signature_applicant_{n}", "field_type": "SIGNATURE", "page": 4, "language": None,
        "box": None, "required": (n == 1), "priority": ("IMPORTANT" if n == 1 else "OPTIONAL"),
        "validation": "none", "validation_target": None, "calibrated": False,
        "notes": "Position not auto-derived; place over the 'Signature (Please Sign within the box)' cell "
                 f"for applicant {n} using the ROI editor.",
    })
    rois.append({
        "roi_name": f"photo_applicant_{n}", "field_type": "PHOTO", "page": 4, "language": None,
        "box": None, "required": False, "priority": "OPTIONAL",
        "validation": "none", "validation_target": None, "calibrated": False, "notes": None,
    })

# ---------------------------------------------------------------------------
# PAGE 6 -- Declaration/consent, thumbprints, bank-use-only section
# ---------------------------------------------------------------------------
for n in range(1, 4):
    rois.append({
        "roi_name": f"thumbprint_applicant_{n}", "field_type": "THUMBPRINT", "page": 6, "language": None,
        "box": None, "required": False, "priority": "OPTIONAL",
        "validation": "none", "validation_target": None, "calibrated": False, "notes": None,
    })
checkbox_group("aml_risk_category", 6, ["Low Risk", "Medium Risk", "*High Risk"], priority="OPTIONAL",
                notes="Bank-use-only section.")
text_field("account_opened_date", 6, "Account Opened Date", width=140, priority="OPTIONAL", field_type="DATE")
text_field("next_kyc_review_date", 6, "Next KYC Review Date", width=140, priority="OPTIONAL", field_type="DATE")

# ---------------------------------------------------------------------------
config = {
    "template_id": "siddhartha_personal_account_opening_v1",
    "display_name": "Siddhartha Bank -- Personal Account Opening Form (Single/Joint)",
    "form_code": "SBL-PRT-002",
    "bank": "Siddhartha Bank",
    "document_type": "kyc",
    "page_count": 6,
    "page_size_pts": PAGE_SIZE,
    "coordinate_units": "pdf_points_72dpi",
    "source_note": ("ROI coordinates were generated by tools/build_siddhartha_config.py directly from the "
                     "vector layout of the supplied SBL-PRT-002 PDF. Checkbox boxes are exact (matched to the "
                     "PDF's own drawn circle geometry). Text-field boxes are anchored to the printed label's "
                     "exact position but use a heuristic width, and pages without a native text layer (i.e. a "
                     "scanned photocopy of this form) will need those refined in the ROI editor. Fields with "
                     "\"calibrated\": false have no verified real coordinates yet and are placeholders for the "
                     "ROI editor -- most of these are on pages 4/6 (signature/photo/thumbprint boxes and the "
                     "family-details table) where the box itself, not a text label, marks the field."),
    "field_priority_levels": ["CRITICAL", "IMPORTANT", "OPTIONAL"],
    "rois": rois,
}

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

calibrated = sum(1 for r in rois if r.get("calibrated"))
print(f"Wrote {OUT_PATH}")
print(f"Total ROIs: {len(rois)}  |  calibrated (exact/label-anchored): {calibrated}  |  placeholder: {len(rois)-calibrated}")
