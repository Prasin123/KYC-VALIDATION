"""
Normalization utilities used before any comparison: unicode/whitespace/
punctuation normalization, and a rule-based Devanagari -> Latin
transliteration for Nepali names so "राम बहादुर थापा" can be compared
against "Ram Bahadur Thapa" without treating a script difference as a
mismatch.

The transliteration table is intentionally simple (character/conjunct
mapping, not a trained model) -- it is good enough to get two independent
spellings of the same name close enough for fuzzy string matching, but it
is NOT a substitute for a human confirming an identity match. Matcher.py
never auto-approves on transliteration alone; see match_name().
"""
from __future__ import annotations

import re
import unicodedata

# Ordered longest-match-first: multi-character conjuncts before base consonants.
_CONJUNCTS = {"क्ष": "ksh", "त्र": "tr", "ज्ञ": "gy", "श्र": "shr"}

_INDEPENDENT_VOWELS = {
    "अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u",
    "ऋ": "ri", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au",
}
_CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ng",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "ny",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "w",
    "श": "sh", "ष": "sh", "स": "s", "ह": "h",
}
_MATRAS = {
    "ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "ृ": "ri",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ं": "n", "ः": "h",
}
_HALANT = "्"
_DIGITS = {"०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
           "५": "5", "६": "6", "७": "7", "८": "8", "९": "9"}


def transliterate_devanagari(s: str) -> str:
    """
    Best-effort Devanagari -> Latin transliteration for comparison purposes
    only (never for display). Handles the inherent vowel correctly: a bare
    consonant carries an implicit "a" (e.g. ब -> "ba") unless followed by a
    vowel matra (which replaces it) or a halant/virama (which suppresses it
    entirely, for conjunct consonant clusters).
    """
    out = []
    i, n = 0, len(s)
    while i < n:
        # 1. known irregular conjuncts first
        conjunct_hit = None
        for dev, lat in _CONJUNCTS.items():
            if s.startswith(dev, i):
                conjunct_hit = (dev, lat)
                break
        if conjunct_hit:
            dev, base = conjunct_hit
            i += len(dev)
            nxt = s[i] if i < n else ""
            if nxt in _MATRAS:
                out.append(base + _MATRAS[nxt])
                i += 1
            elif nxt == _HALANT:
                out.append(base)
                i += 1
            elif nxt == "" or nxt.isspace():
                out.append(base)
            else:
                out.append(base + "a")
            continue

        ch = s[i]
        if ch in _INDEPENDENT_VOWELS:
            out.append(_INDEPENDENT_VOWELS[ch])
            i += 1
        elif ch in _CONSONANTS:
            base = _CONSONANTS[ch]
            nxt = s[i + 1] if i + 1 < n else ""
            if nxt in _MATRAS:
                out.append(base + _MATRAS[nxt])
                i += 2
            elif nxt == _HALANT:
                out.append(base)
                i += 2
            elif nxt == "" or nxt.isspace():
                # Word-final bare consonant: modern Nepali pronunciation (and
                # common anglicization) drops the inherent vowel here --
                # "राम" -> "ram", not "rama". Mid-word bare consonants keep it.
                out.append(base)
                i += 1
            else:
                out.append(base + "a")
                i += 1
        elif ch in _DIGITS:
            out.append(_DIGITS[ch])
            i += 1
        elif ch == _HALANT:
            i += 1  # stray halant with no preceding consonant we tracked; skip
        else:
            out.append(ch)
            i += 1
    return "".join(out)


# Common alternate Latin spellings for the same Nepali name, so e.g.
# "Prasad"/"Parsad" or "Kumari"/"Kumary" don't read as a mismatch. This is
# deliberately a short, high-confidence list, not an exhaustive dictionary.
_NAME_EQUIVALENCE_GROUPS = [
    {"prasad", "parsad"}, {"kumar", "kumer"}, {"kumari", "kumary"},
    {"bahadur", "bdr"}, {"maya", "maiya"}, {"laxmi", "lakshmi"},
    {"shrestha", "shreshtha"}, {"gurung", "gurng"},
]


def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def normalize_unicode(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def strip_punctuation(s: str) -> str:
    return re.sub(r"[.,;:!?'\"()\[\]/\\-]", " ", s or "")


def has_devanagari(s: str) -> bool:
    return any("\u0900" <= ch <= "\u097F" for ch in (s or ""))


def canonical_name(s: str) -> str:
    """Normalize a name (in either script) to a comparable canonical Latin form."""
    s = normalize_unicode(s)
    if has_devanagari(s):
        s = transliterate_devanagari(s)
    s = strip_punctuation(s)
    s = normalize_whitespace(s).lower()
    # apply equivalence groups so e.g. "prasad"/"parsad" tokens compare equal
    tokens = s.split()
    canon_tokens = []
    for t in tokens:
        for group in _NAME_EQUIVALENCE_GROUPS:
            if t in group:
                t = sorted(group)[0]
                break
        canon_tokens.append(t)
    return " ".join(canon_tokens)


def canonical_id(s: str) -> str:
    """Normalize a high-risk identifier (citizenship no., PAN, etc.): keep digits and letters only."""
    s = normalize_unicode(s or "")
    # normalize common OCR confusions before stripping formatting
    s = s.upper()
    return re.sub(r"[^A-Z0-9]", "", s)


def canonical_text(s: str) -> str:
    """General-purpose normalization for non-identity free text fields."""
    s = normalize_unicode(s or "")
    if has_devanagari(s):
        s = transliterate_devanagari(s)
    return normalize_whitespace(strip_punctuation(s)).lower()
