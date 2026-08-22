import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from validation.normalizer import (
    canonical_name, canonical_id, canonical_text, transliterate_devanagari,
    has_devanagari, normalize_whitespace,
)


def test_has_devanagari():
    assert has_devanagari("राम") is True
    assert has_devanagari("Ram") is False
    assert has_devanagari("") is False


def test_transliteration_basic_names():
    assert transliterate_devanagari("राम") == "ram"
    assert transliterate_devanagari("सीता") == "sita"


def test_transliteration_conjuncts():
    result = transliterate_devanagari("क्षेत्री")
    assert result.startswith("kshe")


def test_canonical_name_cross_script_match():
    assert canonical_name("राम बहादुर थापा") == canonical_name("Ram Bahadur Thapa")


def test_canonical_name_ignores_case_and_punctuation():
    assert canonical_name("Ram, Bahadur. Thapa") == canonical_name("ram bahadur thapa")


def test_canonical_name_equivalence_group():
    assert canonical_name("Ram Prasad Sharma") == canonical_name("Ram Parsad Sharma")


def test_normalize_whitespace_collapses():
    assert normalize_whitespace("  Ram   Thapa  ") == "Ram Thapa"


def test_canonical_id_strips_formatting():
    assert canonical_id("12-34-56789") == canonical_id("12 34 56789") == "123456789"


def test_canonical_id_case_insensitive():
    assert canonical_id("ab-12") == canonical_id("AB12")


def test_canonical_text_translit_and_normalize():
    assert canonical_text("काठमाडौं") != ""  # doesn't crash, produces something
