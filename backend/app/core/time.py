import datetime


def utc_now() -> datetime.datetime:
    """Return the current UTC time as a naive datetime for DB compatibility."""
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with timezone info."""
    return datetime.datetime.now(datetime.UTC).isoformat()
