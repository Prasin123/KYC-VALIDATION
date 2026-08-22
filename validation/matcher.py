"""
Field-level match verdicts between a KYC value and its citizenship
counterpart.

Two different verdict vocabularies are used, matching the spec:
  - Free text (names, addresses): MATCH / PROBABLE_MATCH / REVIEW_REQUIRED / MISMATCH
  - High-risk identifiers (citizenship no., PAN, etc.): EXACT_MATCH / NORMALIZED_MATCH / MISMATCH / UNREADABLE

Nothing in this module ever "auto-approves" an uncertain identity match --
ambiguous cases land on REVIEW_REQUIRED, never MATCH, and the matching
functions never see or use each other's private thresholds to sneak past
that rule.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass

from validation.bs_date import ParsedDate, dates_equivalent, parse_date_string
from validation.normalizer import canonical_name, canonical_id, canonical_text

NAME_MATCH_THRESHOLD = 0.90
NAME_PROBABLE_THRESHOLD = 0.75
NAME_REVIEW_THRESHOLD = 0.55

TEXT_MATCH_THRESHOLD = 0.92
TEXT_PROBABLE_THRESHOLD = 0.78
TEXT_REVIEW_THRESHOLD = 0.55

# Enum-like fields (gender, yes/no, marital status) are translated, not
# transliterated, between Nepali and English -- "पुरुष" doesn't sound like
# "Male", so fuzzy string similarity is the wrong tool. These need an
# explicit value map instead.
_ENUM_VALUE_GROUPS = [
    {"male", "पुरुष", "m"},
    {"female", "महिला", "स्त्री", "f"},
    {"others", "अन्य", "other"},
    {"yes", "छ", "हो", "y"},
    {"no", "छैन", "होइन", "n"},
    {"married", "विवाहित"},
    {"single", "अविवाहित", "एकल"},
]


@dataclass
class MatchOutcome:
    field: str
    value_a: str
    value_b: str
    result: str  # verdict string, vocabulary depends on match type
    confidence: float  # 0-100
    detail: str | None = None


def _similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def match_name(field: str, citizenship_value: str, kyc_value: str) -> MatchOutcome:
    """Cross-script-aware name matching. Never returns MATCH on a low-confidence signal."""
    if not citizenship_value or not kyc_value:
        return MatchOutcome(field, citizenship_value, kyc_value, "REVIEW_REQUIRED", 0.0,
                             "One or both values are empty/unread.")
    a, b = canonical_name(citizenship_value), canonical_name(kyc_value)
    ratio = _similarity(a, b)
    conf = round(ratio * 100, 1)
    if a == b:
        return MatchOutcome(field, citizenship_value, kyc_value, "MATCH", 99.0, "Exact match after normalization.")
    if ratio >= NAME_MATCH_THRESHOLD:
        return MatchOutcome(field, citizenship_value, kyc_value, "MATCH", conf,
                             "High similarity after transliteration/normalization.")
    if ratio >= NAME_PROBABLE_THRESHOLD:
        return MatchOutcome(field, citizenship_value, kyc_value, "PROBABLE_MATCH", conf,
                             "Likely the same name, but not close enough to auto-confirm.")
    if ratio >= NAME_REVIEW_THRESHOLD:
        return MatchOutcome(field, citizenship_value, kyc_value, "REVIEW_REQUIRED", conf,
                             "Partial similarity only -- needs human review.")
    return MatchOutcome(field, citizenship_value, kyc_value, "MISMATCH", conf, "Names do not appear to correspond.")


def match_text(field: str, citizenship_value: str, kyc_value: str) -> MatchOutcome:
    """General free-text matching (addresses, districts, etc.) -- same idea as match_name but a stricter bar."""
    if not citizenship_value or not kyc_value:
        return MatchOutcome(field, citizenship_value, kyc_value, "REVIEW_REQUIRED", 0.0,
                             "One or both values are empty/unread.")
    a, b = canonical_text(citizenship_value), canonical_text(kyc_value)
    ratio = _similarity(a, b)
    conf = round(ratio * 100, 1)
    if a == b:
        return MatchOutcome(field, citizenship_value, kyc_value, "MATCH", 99.0, "Exact match after normalization.")
    if ratio >= TEXT_MATCH_THRESHOLD:
        return MatchOutcome(field, citizenship_value, kyc_value, "MATCH", conf, None)
    if ratio >= TEXT_PROBABLE_THRESHOLD:
        return MatchOutcome(field, citizenship_value, kyc_value, "PROBABLE_MATCH", conf, None)
    if ratio >= TEXT_REVIEW_THRESHOLD:
        return MatchOutcome(field, citizenship_value, kyc_value, "REVIEW_REQUIRED", conf, None)
    return MatchOutcome(field, citizenship_value, kyc_value, "MISMATCH", conf, None)


def match_enum(field: str, citizenship_value: str, kyc_value: str) -> MatchOutcome:
    """Value-mapped matching for translated (not transliterated) enum fields like gender/yes-no/marital status."""
    if not citizenship_value or not kyc_value:
        return MatchOutcome(field, citizenship_value, kyc_value, "REVIEW_REQUIRED", 0.0,
                             "One or both values are empty/unread.")
    a_raw = citizenship_value.strip().lower()
    b_raw = kyc_value.strip().lower()

    def group_of(v: str) -> frozenset | None:
        for group in _ENUM_VALUE_GROUPS:
            if v in group or any(v == g.lower() for g in group):
                return frozenset(group)
        return None

    ga, gb = group_of(a_raw), group_of(b_raw)
    if ga is not None and ga == gb:
        return MatchOutcome(field, citizenship_value, kyc_value, "MATCH", 95.0,
                             "Matched via translated value equivalence.")
    if ga is not None and gb is not None and ga != gb:
        return MatchOutcome(field, citizenship_value, kyc_value, "MISMATCH", 0.0, None)
    # Unrecognized value on one or both sides -- fall back to text similarity
    # rather than declaring a mismatch outright.
    return match_text(field, citizenship_value, kyc_value)


def match_id(field: str, citizenship_value: str, kyc_value: str) -> MatchOutcome:
    """
    High-risk identifier matching (citizenship number, PAN, national ID).
    Only exact-after-normalization equality counts as a match -- deliberately
    NO fuzzy/similarity matching here, since two different real ID numbers
    can easily be a few characters apart and must never be conflated.
    """
    if not citizenship_value or not kyc_value:
        return MatchOutcome(field, citizenship_value, kyc_value, "UNREADABLE", 0.0,
                             "One or both values are empty/unread.")
    raw_a, raw_b = citizenship_value.strip(), kyc_value.strip()
    norm_a, norm_b = canonical_id(raw_a), canonical_id(raw_b)
    if not norm_a or not norm_b:
        return MatchOutcome(field, citizenship_value, kyc_value, "UNREADABLE", 0.0, "Could not extract digits/letters.")
    if raw_a == raw_b:
        return MatchOutcome(field, citizenship_value, kyc_value, "EXACT_MATCH", 100.0, None)
    if norm_a == norm_b:
        return MatchOutcome(field, citizenship_value, kyc_value, "NORMALIZED_MATCH", 92.0,
                             "Matches once spacing/hyphenation/case differences are removed.")
    return MatchOutcome(field, citizenship_value, kyc_value, "MISMATCH", 0.0, "Identifiers do not match.")


def match_date(field: str, citizenship_value: str, kyc_value: str,
               citizenship_calendar: str | None = None, kyc_calendar: str | None = None) -> MatchOutcome:
    a = parse_date_string(citizenship_value, assume_calendar=citizenship_calendar)
    b = parse_date_string(kyc_value, assume_calendar=kyc_calendar)
    verdict = dates_equivalent(a, b)
    conf = {"MATCH": 97.0, "REVIEW_REQUIRED": 40.0, "MISMATCH": 0.0, "UNREADABLE": 0.0}[verdict]
    detail = None
    if verdict == "UNREADABLE":
        detail = "Could not parse one or both dates."
    elif verdict == "REVIEW_REQUIRED" and a and b and (a.error or b.error):
        detail = "BS date could not be confidently resolved to AD (out of supported range) or dates differ by ~1 day."
    return MatchOutcome(field, citizenship_value, kyc_value, verdict, conf, detail)


_ID_FIELD_KEYWORDS = ("citizenship_no", "citizenship_number", "national_id", "pan_number", "pan_no", "passport_no")
_ENUM_FIELD_KEYWORDS = ("gender", "marital", "sex")


def match_field(field: str, field_type: str, citizenship_value: str, kyc_value: str) -> MatchOutcome:
    """Dispatch to the right matcher based on ROI field_type and field name."""
    if field_type == "NAME":
        return match_name(field, citizenship_value, kyc_value)
    if field_type == "DATE":
        return match_date(field, citizenship_value, kyc_value)
    if any(kw in field.lower() for kw in _ID_FIELD_KEYWORDS):
        return match_id(field, citizenship_value, kyc_value)
    if any(kw in field.lower() for kw in _ENUM_FIELD_KEYWORDS):
        return match_enum(field, citizenship_value, kyc_value)
    return match_text(field, citizenship_value, kyc_value)
