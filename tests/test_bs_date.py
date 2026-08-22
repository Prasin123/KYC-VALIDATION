import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from validation.bs_date import parse_date_string, parse_bs, parse_ad, dates_equivalent, ad_to_bs


def test_parse_bs_explicit_suffix():
    d = parse_date_string("2059/04/12 B.S.")
    assert d.calendar == "BS"
    assert d.ad_date is not None


def test_parse_ad_explicit_suffix():
    d = parse_date_string("2002/07/28 A.D.")
    assert d.calendar == "AD"
    assert d.ad_date.year == 2002


def test_bs_ad_round_trip_matches_spec_example():
    bs = parse_date_string("2059/04/12 B.S.")
    ad = parse_date_string("2002/07/28 A.D.")
    assert dates_equivalent(bs, ad) == "MATCH"


def test_dates_equivalent_mismatch():
    bs = parse_date_string("2059/04/12 B.S.")
    ad = parse_date_string("1999/01/01 A.D.")
    assert dates_equivalent(bs, ad) == "MISMATCH"


def test_invalid_ad_date_has_error():
    d = parse_ad(2002, 2, 30)  # Feb 30 doesn't exist
    assert d.error is not None
    assert d.ad_date is None


def test_bs_out_of_supported_range_flags_error_not_guess():
    d = parse_bs(500, 1, 1)  # far outside nepali_datetime's supported range
    assert d.ad_date is None
    assert d.error is not None


def test_unparseable_string_returns_none():
    assert parse_date_string("not a date") is None
    assert parse_date_string("") is None


def test_ad_to_bs_round_trip():
    import datetime
    ad = datetime.date(2002, 7, 28)
    bs = ad_to_bs(ad)
    assert bs.ad_date == ad
    assert bs.year == 2059
