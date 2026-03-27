from __future__ import annotations

import time
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import pytz
from dateutil import parser as date_parser

IST = pytz.timezone("Asia/Kolkata")

INITIAL_IMPORT_ENTRY_LIMIT = 25
POLL_ENTRY_SCAN_LIMIT = 50


def is_youtube_playlist_feed(feed_url: str | None) -> bool:
    if not feed_url:
        return False

    try:
        parsed = urlparse(feed_url)
        hostname = parsed.netloc.lower()
        query = parse_qs(parsed.query)
        return "youtube.com" in hostname and "playlist_id" in query
    except Exception:
        return False


def get_entry_timestamp(entry, feed_url: str | None = None):
    """
    Return the best timestamp for a feed entry.

    YouTube playlist feeds are treated specially because an item may represent an
    older video that was recently surfaced/updated in the playlist. In that case
    prefer `updated` over `published`.
    """

    prefer_updated = is_youtube_playlist_feed(feed_url)

    raw_value = None
    struct = None

    candidate_fields = (
        (
            "updated",
            "updated_parsed",
            getattr(entry, "updated", None),
            getattr(entry, "updated_parsed", None),
        ),
        (
            "published",
            "published_parsed",
            getattr(entry, "published", None),
            getattr(entry, "published_parsed", None),
        ),
    )
    if not prefer_updated:
        candidate_fields = candidate_fields[::-1]

    for _, _, raw_candidate, struct_candidate in candidate_fields:
        if raw_candidate is not None:
            raw_value = raw_candidate
            struct = struct_candidate
            break

    if struct:
        dt_utc = datetime.fromtimestamp(time.mktime(struct), tz=pytz.utc)
        return raw_value, dt_utc.astimezone(IST)

    if not raw_value:
        return None, None

    try:
        parsed_dt = date_parser.parse(raw_value)
        if parsed_dt.tzinfo:
            parsed_dt = parsed_dt.astimezone(IST)
        else:
            parsed_dt = IST.localize(parsed_dt)
        return raw_value, parsed_dt
    except Exception:
        return raw_value, None
