import datetime

from app.core.time import utc_now, utc_now_iso


def test_utc_now_returns_naive_datetime():
    value = utc_now()

    assert isinstance(value, datetime.datetime)
    assert value.tzinfo is None


def test_utc_now_iso_returns_utc_offset():
    value = utc_now_iso()

    assert value.endswith("+00:00")
