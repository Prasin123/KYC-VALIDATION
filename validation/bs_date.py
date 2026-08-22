"""
Bikram Sambat (BS) <-> Gregorian (AD) date handling.

Nepali documents routinely record dates in BS, which does not have
fixed-length months (unlike AD), so this is not something you can compute
with a simple offset -- it requires a real calendar table. We use the
`nepali_datetime` package for that rather than approximating, and only ever
fall back to "REVIEW REQUIRED" (never a guess) when a date falls outside
what it supports or fails to parse.
"""
from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass

import nepali_datetime

# Nepali month names (and common two/three-letter abbreviations sometimes
# handwritten/printed on forms) -> month number.
_BS_MONTHS = {
    "baishakh": 1, "bais": 1, "jestha": 2, "jeth": 2, "ashadh": 3, "asar": 3,
    "shrawan": 4, "saun": 4, "bhadra": 5, "bhadau": 5, "ashwin": 6, "asoj": 6,
    "kartik": 7, "mangsir": 8, "manshir": 8, "poush": 9, "push": 9,
    "magh": 10, "falgun": 11, "chaitra": 12, "chait": 12,
}


@dataclass
class ParsedDate:
    calendar: str  # "AD" or "BS"
    year: int
    month: int
    day: int
    ad_date: _dt.date | None  # resolved AD equivalent, or None if out of range/unparseable
    error: str | None = None


def parse_ad(year: int, month: int, day: int) -> ParsedDate:
    try:
        d = _dt.date(year, month, day)
        return ParsedDate("AD", year, month, day, d)
    except ValueError as e:
        return ParsedDate("AD", year, month, day, None, error=str(e))


def parse_bs(year: int, month: int, day: int) -> ParsedDate:
    try:
        bs = nepali_datetime.date(year, month, day)
        return ParsedDate("BS", year, month, day, bs.to_datetime_date())
    except Exception as e:
        # Outside nepali_datetime's supported year range, or an invalid BS date.
        return ParsedDate("BS", year, month, day, None,
                           error=f"Could not resolve BS {year}-{month:02d}-{day:02d} to AD: {e}")


def ad_to_bs(d: _dt.date) -> ParsedDate:
    try:
        bs = nepali_datetime.date.from_datetime_date(d)
        return ParsedDate("BS", bs.year, bs.month, bs.day, d)
    except Exception as e:
        return ParsedDate("BS", 0, 0, 0, None, error=str(e))


_DATE_PATTERNS = [
    re.compile(r"^(?P<y>\d{4})[/\-.](?P<m>\d{1,2})[/\-.](?P<d>\d{1,2})$"),  # 2059/04/12
    re.compile(r"^(?P<d>\d{1,2})[/\-.](?P<m>\d{1,2})[/\-.](?P<y>\d{4})$"),  # 12/04/2059
]


def parse_date_string(s: str, assume_calendar: str | None = None) -> ParsedDate | None:
    """
    Parse a loosely-formatted date string as found on the form (numeric,
    slash/dash/dot separated, optionally followed by "B.S."/"A.D."/"BS"/"AD").
    Returns None if the string doesn't look like a date at all -- callers
    should treat that as UNREADABLE, not guess.
    """
    if not s:
        return None
    raw = s.strip()
    upper = raw.upper()
    calendar = assume_calendar
    if "B.S" in upper or re.search(r"\bBS\b", upper):
        calendar = "BS"
    elif "A.D" in upper or re.search(r"\bAD\b", upper):
        calendar = "AD"
    # Strip the calendar indicator itself before reducing to digits/separators,
    # so trailing punctuation from "B.S."/"A.D." doesn't leak into `cleaned`.
    no_indicator = re.sub(r"(?i)\b[ab]\.?\s*[sd]\.?\b", "", raw)
    cleaned = re.sub(r"[^0-9/\-.]", "", no_indicator).strip(" ./-")
    for pat in _DATE_PATTERNS:
        m = pat.match(cleaned)
        if m:
            y, mo, d = int(m["y"]), int(m["m"]), int(m["d"])
            if calendar is None:
                # Heuristic: BS is currently ~56-57 years ahead of AD.
                calendar = "BS" if y >= 2000 and y <= 2100 and y - _dt.date.today().year > 30 else "AD"
            return parse_bs(y, mo, d) if calendar == "BS" else parse_ad(y, mo, d)
    return None


def dates_equivalent(a: ParsedDate | None, b: ParsedDate | None, tolerance_days: int = 0) -> str:
    """
    Compare two parsed dates (regardless of which calendar each was
    originally recorded in) via their resolved AD equivalents.
    Returns one of: "MATCH", "MISMATCH", "REVIEW_REQUIRED", "UNREADABLE".
    """
    if a is None or b is None:
        return "UNREADABLE"
    if a.ad_date is None or b.ad_date is None:
        return "REVIEW_REQUIRED"
    diff = abs((a.ad_date - b.ad_date).days)
    if diff <= tolerance_days:
        return "MATCH"
    if diff <= 2:  # off-by-a-day inputs are common with OCR digit confusion
        return "REVIEW_REQUIRED"
    return "MISMATCH"
