import datetime

from app.services.newapi import _as_naive_utc


def test_as_naive_utc_keeps_naive_datetime():
    value = datetime.datetime(2026, 6, 6, 1, 0, 0)

    assert _as_naive_utc(value) == value
    assert _as_naive_utc(value).tzinfo is None


def test_as_naive_utc_normalizes_aware_datetime():
    value = datetime.datetime(
        2026,
        6,
        6,
        9,
        0,
        0,
        tzinfo=datetime.timezone(datetime.timedelta(hours=8)),
    )

    normalized = _as_naive_utc(value)

    assert normalized == datetime.datetime(2026, 6, 6, 1, 0, 0)
    assert normalized.tzinfo is None
