import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from validation.matcher import match_name, match_id, match_date, match_enum, match_text, match_field


def test_match_name_cross_script_exact():
    r = match_name("full_name", "राम बहादुर थापा", "Ram Bahadur Thapa")
    assert r.result == "MATCH"


def test_match_name_empty_value_is_review():
    r = match_name("full_name", "", "Ram Thapa")
    assert r.result == "REVIEW_REQUIRED"


def test_match_name_clear_mismatch():
    r = match_name("full_name", "राम बहादुर थापा", "Sita Kumari Gurung")
    assert r.result == "MISMATCH"


def test_match_id_exact():
    r = match_id("citizenship_no", "12-34-56789", "12-34-56789")
    assert r.result == "EXACT_MATCH"


def test_match_id_normalized():
    r = match_id("citizenship_no", "12-34-56789", "12 34 56789")
    assert r.result == "NORMALIZED_MATCH"


def test_match_id_mismatch_not_fuzzy():
    # Deliberately close-but-different IDs must NOT match -- no fuzzy matching for IDs.
    r = match_id("citizenship_no", "12-34-56789", "12-34-56780")
    assert r.result == "MISMATCH"


def test_match_id_unreadable():
    r = match_id("citizenship_no", "", "12-34-56789")
    assert r.result == "UNREADABLE"


def test_match_date_bs_ad_equivalent():
    r = match_date("dob", "2059/04/12 B.S.", "2002/07/28 A.D.")
    assert r.result == "MATCH"


def test_match_date_mismatch():
    r = match_date("dob", "2059/04/12 B.S.", "2002/07/29 A.D.")
    assert r.result in ("REVIEW_REQUIRED", "MISMATCH")
    assert r.result != "MATCH"


def test_match_enum_gender_translation():
    r = match_enum("gender", "पुरुष", "Male")
    assert r.result == "MATCH"


def test_match_enum_gender_mismatch():
    r = match_enum("gender", "पुरुष", "Female")
    assert r.result == "MISMATCH"


def test_match_field_dispatches_by_type():
    r = match_field("applicant_1_name", "NAME", "राम थापा", "Ram Thapa")
    assert r.result == "MATCH"


def test_match_field_dispatches_id_by_name_keyword():
    r = match_field("citizenship_no_applicant_1", "TEXT", "12-34-56789", "12-34-56789")
    assert r.result == "EXACT_MATCH"


def test_never_auto_match_on_ambiguous_similarity():
    # A middling similarity score must land on REVIEW_REQUIRED or PROBABLE_MATCH,
    # never a bare MATCH -- this is the "never auto-approve an uncertain identity
    # match" requirement.
    r = match_text("address", "Kathmandu Ward 5", "Lalitpur Ward 5")
    assert r.result != "MATCH"
