"""Shared date parsing for scraper.py and digest.py.

Source dates arrive in inconsistent formats depending on feed type: ISO 8601
("2026-06-05T17:09:34+00:00", from YouTube/Atom feeds), RFC 822
("Fri, 01 May 2026 15:00:00 +0000" or "...GMT", from most TechCommunity/blog
RSS feeds), and RFC 822 with a non-standard " Z" suffix in place of a numeric
offset (the M365 Roadmap feed). A plain string comparison across these
formats does not sort chronologically — weekday/month names and inconsistent
lengths break it — which is how stale items slipped past the "most recent N"
caps in digest.py. Parse everything into a real, timezone-aware UTC datetime
before any sorting or age comparison happens.
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def parse_item_date(date_value) -> "datetime | None":
    """Parse a date string in any of the formats above into a UTC datetime.

    Returns None if the string can't be parsed at all — callers should treat
    that as "unknown age" rather than silently sorting it as oldest or newest.
    """
    if not date_value:
        return None
    s = str(date_value).strip()
    if not s:
        return None

    # Non-standard " Z" suffix used in place of a numeric offset (M365 Roadmap
    # feed) — normalize to a real RFC 822 offset before parsing.
    if s.endswith(" Z"):
        s = s[:-2].strip() + " +0000"

    try:
        dt = parsedate_to_datetime(s)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass

    try:
        iso = s[:-1] + "+00:00" if s.endswith("Z") else s
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass

    return None


def item_age_days(date_value, now: "datetime | None" = None) -> "float | None":
    """Age in days (float) of a date value, or None if unparseable."""
    dt = parse_item_date(date_value)
    if dt is None:
        return None
    now = now or datetime.now(timezone.utc)
    return (now - dt).total_seconds() / 86400
