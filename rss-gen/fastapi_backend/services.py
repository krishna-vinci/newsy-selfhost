from __future__ import annotations

import io
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse
from xml.sax.saxutils import XMLGenerator

import httpx
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from fastapi_backend.cache import DEFAULT_CACHE_MAX_AGE_SECONDS, TTLFileCache
from fastapi_backend.models import (
    Attribution,
    FeedLink,
    FeedsearchFeedResult,
    PreviewItem,
    RedditFeedType,
    ResolvedSourceResponse,
    SourceType,
    YouTubeFeedType,
)


YOUTUBE_BASE = "https://www.youtube.com"
YOUTUBE_FEED_BASE = "https://www.youtube.com/feeds/videos.xml"
PLAYLIST_PREFIXES = {
    YouTubeFeedType.videos.value: "UULF",
    YouTubeFeedType.shorts.value: "UUSH",
    YouTubeFeedType.live.value: "UULV",
}
YOUTUBE_FEED_META = {
    YouTubeFeedType.all.value: (
        "All uploads",
        "Every video, short, and live stream.",
    ),
    YouTubeFeedType.videos.value: (
        "Videos",
        "Long-form uploads only — no Shorts or live streams.",
    ),
    YouTubeFeedType.shorts.value: (
        "Shorts",
        "Vertical short-form content only.",
    ),
    YouTubeFeedType.live.value: (
        "Live",
        "Live streams and replays only.",
    ),
}
REDDIT_BASE = "https://www.reddit.com"
REDDIT_FEED_META = {
    RedditFeedType.hot.value: ("Hot", "Active posts right now."),
    RedditFeedType.new.value: ("New", "Latest posts in chronological order."),
    RedditFeedType.rising.value: (
        "Rising",
        "Posts currently gaining traction.",
    ),
    RedditFeedType.top.value: ("Top", "Highest-scoring posts."),
    RedditFeedType.controversial.value: (
        "Controversial",
        "Most divisively discussed posts.",
    ),
}
SHORTS_DURATION_SECONDS = 60
CHANNEL_TTL_SECONDS = 30 * 60
FEEDSEARCH_TTL_SECONDS = 15 * 60
PREVIEW_TIMEOUT_SECONDS = 5
MAX_ITEMS_PER_TAB = 20
SUBREDDIT_RE = re.compile(r"^[A-Za-z0-9_]{2,21}$")
FEEDSEARCH_ATTRIBUTION = Attribution(
    label="powered by Feedsearch",
    url="https://feedsearch.dev",
)


class APIError(Exception):
    def __init__(self, detail: str, error_code: str, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.error_code = error_code
        self.status_code = status_code


class BadRequestError(APIError):
    def __init__(self, detail: str, error_code: str = "bad_request") -> None:
        super().__init__(detail=detail, error_code=error_code, status_code=400)


class NotFoundError(APIError):
    def __init__(self, detail: str, error_code: str = "not_found") -> None:
        super().__init__(detail=detail, error_code=error_code, status_code=404)


class UpstreamServiceError(APIError):
    def __init__(self, detail: str, error_code: str = "upstream_error") -> None:
        super().__init__(detail=detail, error_code=error_code, status_code=502)


@dataclass(slots=True)
class Settings:
    app_name: str = "RSS Gen"
    cache_dir: str = ".cache"
    cache_max_age_seconds: int = DEFAULT_CACHE_MAX_AGE_SECONDS
    channel_cache_ttl_seconds: int = CHANNEL_TTL_SECONDS
    feedsearch_cache_ttl_seconds: int = FEEDSEARCH_TTL_SECONDS
    request_timeout_seconds: int = 15
    preview_timeout_seconds: int = PREVIEW_TIMEOUT_SECONDS
    user_agent: str = "rss-gen-fastapi/1.0"
    feedsearch_url: str = "https://feedsearch.dev/api/v1/search"
    cors_origins_raw: str = "*"

    @property
    def cors_origins(self) -> list[str]:
        value = self.cors_origins_raw.strip()
        if not value:
            return []
        if value == "*":
            return ["*"]
        return [origin.strip() for origin in value.split(",") if origin.strip()]

    @classmethod
    def from_env(cls) -> "Settings":
        defaults = cls()

        def _int(name: str, default: int) -> int:
            raw = os.getenv(name)
            if raw is None:
                return default
            try:
                return int(raw)
            except ValueError:
                return default

        return cls(
            app_name=os.getenv("RSS_GEN_APP_NAME", defaults.app_name),
            cache_dir=os.getenv("RSS_GEN_CACHE_DIR", defaults.cache_dir),
            cache_max_age_seconds=_int(
                "RSS_GEN_CACHE_MAX_AGE_SECONDS", defaults.cache_max_age_seconds
            ),
            channel_cache_ttl_seconds=_int(
                "RSS_GEN_CHANNEL_CACHE_TTL_SECONDS",
                defaults.channel_cache_ttl_seconds,
            ),
            feedsearch_cache_ttl_seconds=_int(
                "RSS_GEN_FEEDSEARCH_CACHE_TTL_SECONDS",
                defaults.feedsearch_cache_ttl_seconds,
            ),
            request_timeout_seconds=_int(
                "RSS_GEN_REQUEST_TIMEOUT_SECONDS", defaults.request_timeout_seconds
            ),
            preview_timeout_seconds=_int(
                "RSS_GEN_PREVIEW_TIMEOUT_SECONDS", defaults.preview_timeout_seconds
            ),
            user_agent=os.getenv("RSS_GEN_USER_AGENT", defaults.user_agent),
            feedsearch_url=os.getenv("RSS_GEN_FEEDSEARCH_URL", defaults.feedsearch_url),
            cors_origins_raw=os.getenv(
                "RSS_GEN_CORS_ORIGINS", defaults.cors_origins_raw
            ),
        )


@dataclass(slots=True)
class ServiceContainer:
    settings: Settings
    cache: TTLFileCache
    preview: PreviewService
    youtube: YouTubeService
    reddit: RedditService
    feedsearch: FeedsearchService


def detect_source(query: str) -> SourceType:
    value = (query or "").strip()
    if not value:
        raise BadRequestError("Query is required.", error_code="missing_query")

    lowered = value.lower()
    if (
        value.startswith("@")
        or "youtube.com/" in lowered
        or "youtu.be/" in lowered
        or re.fullmatch(r"UC[\w-]{22}", value)
    ):
        return SourceType.youtube

    if lowered.startswith("r/") or "reddit.com/r/" in lowered:
        return SourceType.reddit

    if "://" in value or "." in value:
        return SourceType.website

    return SourceType.reddit


def classify_video(item: dict[str, Any]) -> str:
    webpage_url = (item.get("webpage_url") or item.get("url") or "").lower()
    duration = item.get("duration")
    live_status = (item.get("live_status") or "").lower()
    was_live = bool(item.get("was_live"))
    is_live = bool(item.get("is_live"))

    if (
        live_status in {"is_live", "was_live", "post_live", "is_upcoming"}
        or was_live
        or is_live
    ):
        return YouTubeFeedType.live.value

    if "/shorts/" in webpage_url or (
        isinstance(duration, (int, float)) and duration <= SHORTS_DURATION_SECONDS
    ):
        return YouTubeFeedType.shorts.value

    return YouTubeFeedType.videos.value


def filter_by_type(items: list[dict[str, Any]], feed_type: str) -> list[dict[str, Any]]:
    if feed_type == YouTubeFeedType.all.value:
        return items
    return [item for item in items if item.get("content_type") == feed_type]


def build_youtube_feed_url(channel_id: str, feed_type: YouTubeFeedType) -> str:
    if feed_type == YouTubeFeedType.all:
        return f"{YOUTUBE_FEED_BASE}?channel_id={channel_id}"
    if not channel_id.startswith("UC"):
        raise BadRequestError(
            "Could not build a native YouTube feed URL.",
            error_code="invalid_channel_id",
        )
    playlist_id = f"{PLAYLIST_PREFIXES[feed_type.value]}{channel_id[2:]}"
    return f"{YOUTUBE_FEED_BASE}?playlist_id={playlist_id}"


def build_rss(
    feed_type: str,
    channel: dict[str, Any],
    items: list[dict[str, Any]],
    feed_url: str,
) -> str:
    output = io.StringIO()
    xml = XMLGenerator(output, encoding="utf-8")
    xml.startDocument()
    xml.startElement(
        "rss",
        {
            "version": "2.0",
            "xmlns:content": "http://purl.org/rss/1.0/modules/content/",
            "xmlns:atom": "http://www.w3.org/2005/Atom",
            "xmlns:dc": "http://purl.org/dc/elements/1.1/",
            "xmlns:media": "http://search.yahoo.com/mrss/",
        },
    )
    xml.startElement("channel", {})
    _text_tag(xml, "title", f"{channel['channel_name']} - {feed_type.title()}")
    _text_tag(xml, "link", channel["channel_url"])
    _text_tag(
        xml,
        "description",
        f"YouTube {feed_type} feed for {channel['channel_name']}",
    )
    _text_tag(xml, "generator", "rss-gen-fastapi")
    _text_tag(xml, "ttl", str(channel.get("ttl_minutes", 30)))
    _text_tag(xml, "lastBuildDate", format_datetime(datetime.now(tz=timezone.utc)))
    _text_tag(xml, "docs", "https://www.rssboard.org/rss-specification")
    xml.startElement(
        "atom:link",
        {"href": feed_url, "rel": "self", "type": "application/rss+xml"},
    )
    xml.endElement("atom:link")

    for item in items:
        xml.startElement("item", {})
        _text_tag(xml, "title", item.get("title") or "Untitled")
        _text_tag(xml, "link", item["webpage_url"])
        xml.startElement("guid", {"isPermaLink": "false"})
        xml.characters(f"yt:video:{item.get('id') or item['webpage_url']}")
        xml.endElement("guid")
        if isinstance(item.get("timestamp"), (int, float)):
            dt = datetime.fromtimestamp(item["timestamp"], tz=timezone.utc)
            _text_tag(xml, "pubDate", format_datetime(dt))
        _text_tag(xml, "description", item.get("description") or "")
        _text_tag(xml, "dc:creator", item.get("uploader") or channel["channel_name"])
        if item.get("thumbnail"):
            xml.startElement("media:thumbnail", {"url": item["thumbnail"]})
            xml.endElement("media:thumbnail")
        xml.endElement("item")

    xml.endElement("channel")
    xml.endElement("rss")
    xml.endDocument()
    return output.getvalue()


def _text_tag(xml: XMLGenerator, tag: str, value: str) -> None:
    xml.startElement(tag, {})
    xml.characters(value)
    xml.endElement(tag)


class PreviewService:
    def __init__(
        self,
        client: httpx.AsyncClient,
        user_agent: str,
        timeout_seconds: int,
    ) -> None:
        self.client = client
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds

    async def fetch(self, url: str, max_items: int = 6) -> list[PreviewItem]:
        if not self._is_safe_url(url):
            return []

        try:
            response = await self.client.get(
                url,
                headers={"User-Agent": self.user_agent},
                follow_redirects=True,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return []

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            return []

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
        }
        items: list[PreviewItem] = []

        for entry in root.findall(".//item"):
            title = (entry.findtext("title") or "").strip() or "(no title)"
            link = (entry.findtext("link") or "").strip()
            pub = (entry.findtext("pubDate") or "").strip()
            author = (entry.findtext("author") or "").strip()
            creator = entry.findtext("{http://purl.org/dc/elements/1.1/}creator") or ""
            items.append(
                PreviewItem(
                    title=title,
                    url=link,
                    published=self._fmt_date(pub) if pub else "",
                    author=author or creator.strip(),
                )
            )
            if len(items) >= max_items:
                return items

        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            title = (title_el.text or "").strip() if title_el is not None else ""
            link_el = entry.find("atom:link[@rel='alternate']", ns) or entry.find(
                "atom:link", ns
            )
            link = link_el.get("href", "") if link_el is not None else ""
            pub_el = entry.find("atom:published", ns) or entry.find("atom:updated", ns)
            pub = pub_el.text.strip() if pub_el is not None and pub_el.text else ""
            author_name_el = entry.find("atom:author/atom:name", ns)
            author = (
                (author_name_el.text or "").strip()
                if author_name_el is not None
                else ""
            )
            items.append(
                PreviewItem(
                    title=title or "(no title)",
                    url=link,
                    published=self._fmt_date(pub) if pub else "",
                    author=author,
                )
            )
            if len(items) >= max_items:
                return items

        return items

    def _is_safe_url(self, url: str) -> bool:
        hostname = (urlparse(url).hostname or "").strip().lower()
        if not hostname:
            return False
        if hostname in {"localhost", "127.0.0.1", "::1"} or hostname.endswith(".local"):
            return False
        try:
            parsed_ip = ip_address(hostname)
        except ValueError:
            return True
        return not (
            parsed_ip.is_private
            or parsed_ip.is_loopback
            or parsed_ip.is_link_local
            or parsed_ip.is_multicast
            or parsed_ip.is_reserved
            or parsed_ip.is_unspecified
        )

    def _fmt_date(self, raw: str) -> str:
        for fmt in (
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
        ):
            try:
                dt = datetime.strptime(raw.strip(), fmt)
                dt = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
                now = datetime.now(timezone.utc)
                delta = now - dt
                if delta.days == 0:
                    hours = delta.seconds // 3600
                    return f"{hours}h ago" if hours else "just now"
                if delta.days < 7:
                    return f"{delta.days}d ago"
                return dt.strftime("%-d %b %Y")
            except ValueError:
                continue
        return raw[:10] if len(raw) >= 10 else raw


class YouTubeService:
    def __init__(self, cache: TTLFileCache, channel_cache_ttl_seconds: int) -> None:
        self.cache = cache
        self.channel_cache_ttl_seconds = channel_cache_ttl_seconds

    def resolve_channel(self, raw_input: str) -> dict[str, Any]:
        normalized = self._normalize_channel_input(raw_input)
        cache_key = f"resolve::{normalized}"
        cached = self.cache.get(cache_key, self.channel_cache_ttl_seconds)
        if cached:
            return cached

        info = self._extract_channel_info(normalized)
        channel = self._channel_payload_from_info(info, normalized)
        self.cache.set(cache_key, channel)
        return channel

    def get_channel_bundle(self, channel_input: str) -> dict[str, Any]:
        channel = self.resolve_channel(channel_input)
        cache_key = f"channel_bundle::{channel['channel_id']}"
        cached = self.cache.get(cache_key, self.channel_cache_ttl_seconds)
        if cached:
            return cached

        items = self._fetch_recent_items(channel)
        bundle = {"channel": channel, "items": items}
        self.cache.set(cache_key, bundle)
        return bundle

    def get_channel_bundle_by_id(self, channel_id: str) -> dict[str, Any]:
        cache_key = f"channel_bundle::{channel_id}"
        cached = self.cache.get(cache_key, self.channel_cache_ttl_seconds)
        if cached:
            return cached

        return self.get_channel_bundle(f"{YOUTUBE_BASE}/channel/{channel_id}")

    def build_resolved_response(
        self,
        channel_input: str,
        base_feed_url: str,
        preview_items: list[PreviewItem],
    ) -> ResolvedSourceResponse:
        bundle = self.get_channel_bundle(channel_input)
        channel = bundle["channel"]
        items = bundle["items"]

        feeds: list[FeedLink] = []
        for feed_type in YouTubeFeedType:
            label, description = YOUTUBE_FEED_META[feed_type.value]
            count = len(filter_by_type(items, feed_type.value))
            try:
                feed_url = build_youtube_feed_url(channel["channel_id"], feed_type)
                external = True
            except BadRequestError:
                feed_url = f"{base_feed_url}/{feed_type.value}/{channel['channel_id']}.xml"
                external = False
            feeds.append(
                FeedLink(
                    label=label,
                    url=feed_url,
                    type=feed_type.value,
                    external=external,
                    count=count,
                    description=description,
                )
            )

        item_map = {
            item.get("webpage_url", ""): item.get("content_type", "") for item in items
        }
        for preview_item in preview_items:
            content_type = item_map.get(preview_item.url, "")
            if content_type:
                preview_item.badge = content_type.title()

        return ResolvedSourceResponse(
            source=SourceType.youtube,
            input=channel_input,
            entity_name=channel["channel_name"],
            entity_url=channel.get("channel_url"),
            feeds=feeds,
            preview_items=preview_items,
            preview_feed_label=f"{channel['channel_name']} · all uploads",
            metadata={"channel_id": channel["channel_id"]},
        )

    def build_feed_xml(
        self, channel_id: str, feed_type: YouTubeFeedType, feed_url: str
    ) -> str:
        bundle = self.get_channel_bundle_by_id(channel_id)
        channel = bundle["channel"]
        items = filter_by_type(bundle["items"], feed_type.value)
        return build_rss(
            feed_type=feed_type.value,
            channel=channel,
            items=items,
            feed_url=feed_url,
        )

    def native_preview_url(self, channel_input: str) -> str:
        channel = self.resolve_channel(channel_input)
        return build_youtube_feed_url(channel["channel_id"], YouTubeFeedType.all)

    def _normalize_channel_input(self, raw_input: str) -> str:
        value = (raw_input or "").strip()
        if not value:
            raise BadRequestError(
                "Enter a YouTube channel URL, channel ID, or @handle.",
                error_code="invalid_youtube_input",
            )

        lowered = value.lower()
        if lowered.startswith("youtube.com/") or lowered.startswith("www.youtube.com/"):
            value = f"https://{value.lstrip('/')}"
        elif lowered.startswith("youtu.be/") or lowered.startswith("www.youtu.be/"):
            value = f"https://{value.lstrip('/')}"

        if value.startswith("@"):
            return f"{YOUTUBE_BASE}/{value}"

        if value.startswith("http://") or value.startswith("https://"):
            parsed = urlparse(value)
            netloc = parsed.netloc.lower().split("@")[-1].split(":")[0]
            is_youtube = (
                netloc == "youtube.com"
                or netloc.endswith(".youtube.com")
                or netloc == "youtu.be"
            )
            if not is_youtube:
                raise BadRequestError(
                    "Only YouTube channel URLs are supported.",
                    error_code="invalid_youtube_url",
                )
            return value

        if re.fullmatch(r"UC[\w-]{22}", value):
            return f"{YOUTUBE_BASE}/channel/{value}"

        raise BadRequestError(
            "Use a YouTube channel URL, channel ID, or @handle.",
            error_code="invalid_youtube_input",
        )

    def _extract_channel_info(self, channel_url: str) -> dict[str, Any]:
        options = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
            "playlistend": 1,
            "socket_timeout": 15,
        }
        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(channel_url, download=False)
        except DownloadError as exc:
            raise NotFoundError(
                "Could not resolve that YouTube channel.",
                error_code="youtube_not_found",
            ) from exc

        if not info:
            raise NotFoundError(
                "Could not resolve that YouTube channel.",
                error_code="youtube_not_found",
            )
        return info

    def _fetch_recent_items(self, channel: dict[str, Any]) -> list[dict[str, Any]]:
        tab_urls = {
            YouTubeFeedType.videos.value: f"{channel['channel_url']}/videos",
            YouTubeFeedType.shorts.value: f"{channel['channel_url']}/shorts",
            YouTubeFeedType.live.value: f"{channel['channel_url']}/streams",
        }

        merged: dict[str, dict[str, Any]] = {}
        for hinted_type, tab_url in tab_urls.items():
            for item in self._extract_playlist_items(tab_url):
                if not item.get("id") or item.get("availability") == "private":
                    continue
                cleaned = self._normalize_video(item, channel, hinted_type)
                merged[cleaned["id"]] = cleaned

        return sorted(
            merged.values(),
            key=lambda item: (item.get("timestamp") or 0, item.get("id") or ""),
            reverse=True,
        )

    def _extract_playlist_items(self, tab_url: str) -> list[dict[str, Any]]:
        options = {
            "quiet": True,
            "skip_download": True,
            "playlistend": MAX_ITEMS_PER_TAB,
            "extract_flat": True,
            "ignore_no_formats_error": True,
            "socket_timeout": 15,
        }
        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(tab_url, download=False)
        except DownloadError:
            return []
        return info.get("entries") or []

    def _channel_payload_from_info(
        self,
        info: dict[str, Any],
        source_url: str,
    ) -> dict[str, Any]:
        channel_id = info.get("channel_id") or info.get("id")
        if not channel_id:
            raise NotFoundError(
                "Could not resolve a stable channel ID.",
                error_code="youtube_missing_channel_id",
            )

        channel_name = (
            info.get("channel")
            or info.get("uploader")
            or info.get("title")
            or channel_id
        )
        canonical = (
            info.get("channel_url")
            or info.get("uploader_url")
            or f"{YOUTUBE_BASE}/channel/{channel_id}"
        )
        return {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "channel_url": canonical.rstrip("/"),
            "source_input": source_url,
            "ttl_minutes": self.channel_cache_ttl_seconds // 60,
        }

    def _normalize_video(
        self,
        item: dict[str, Any],
        channel: dict[str, Any],
        hinted_type: str,
    ) -> dict[str, Any]:
        video_id = item.get("id")
        webpage_url = (
            item.get("webpage_url")
            or item.get("url")
            or f"{YOUTUBE_BASE}/watch?v={video_id}"
        )
        if webpage_url.startswith("/"):
            webpage_url = f"{YOUTUBE_BASE}{webpage_url}"
        elif not webpage_url.startswith("http"):
            webpage_url = f"{YOUTUBE_BASE}/watch?v={video_id}"

        thumbnails = item.get("thumbnails") or []
        thumbnail = item.get("thumbnail")
        if not thumbnail and thumbnails:
            thumbnail = thumbnails[-1].get("url")
        if not thumbnail and video_id:
            thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

        timestamp = item.get("timestamp") or item.get("release_timestamp")
        if timestamp is None and item.get("upload_date"):
            try:
                timestamp = int(
                    datetime.strptime(item["upload_date"], "%Y%m%d")
                    .replace(tzinfo=timezone.utc)
                    .timestamp()
                )
            except ValueError:
                timestamp = None

        normalized = {
            "id": video_id,
            "title": item.get("title") or "Untitled",
            "description": item.get("description") or "",
            "duration": item.get("duration"),
            "timestamp": timestamp,
            "thumbnail": thumbnail,
            "webpage_url": webpage_url,
            "uploader": item.get("channel")
            or item.get("uploader")
            or channel["channel_name"],
            "live_status": item.get("live_status"),
            "was_live": item.get("was_live"),
            "is_live": item.get("is_live"),
        }
        detected_type = classify_video(normalized)
        if (
            hinted_type == YouTubeFeedType.live.value
            and detected_type == YouTubeFeedType.videos.value
        ):
            detected_type = YouTubeFeedType.live.value
        normalized["content_type"] = detected_type
        return normalized


class RedditService:
    def normalize_subreddit_input(self, raw_input: str) -> str:
        value = (raw_input or "").strip()
        if not value:
            raise BadRequestError(
                "Enter a subreddit name or Reddit URL.",
                error_code="invalid_reddit_input",
            )

        if value.startswith("http://") or value.startswith("https://"):
            parsed = urlparse(value)
            netloc = parsed.netloc.lower().split("@")[-1].split(":")[0]
            is_reddit = netloc == "reddit.com" or netloc.endswith(".reddit.com")
            if not is_reddit:
                raise BadRequestError(
                    "Only Reddit subreddit URLs are supported.",
                    error_code="invalid_reddit_url",
                )

            path = [part for part in parsed.path.split("/") if part]
            if len(path) >= 2 and path[0].lower() == "r":
                return self._validate_subreddit_name(path[1])
            raise BadRequestError(
                "Use a Reddit subreddit URL like reddit.com/r/selfhosted.",
                error_code="invalid_reddit_url",
            )

        if value.lower().startswith("r/"):
            value = value[2:]

        return self._validate_subreddit_name(value)

    def normalize_limit(self, raw_limit: str | int | None) -> int:
        try:
            value = int(raw_limit or 10)
        except (TypeError, ValueError) as exc:
            raise BadRequestError(
                "Number of posts must be a valid number.",
                error_code="invalid_reddit_limit",
            ) from exc
        if value < 1 or value > 100:
            raise BadRequestError(
                "Number of posts must be between 1 and 100.",
                error_code="invalid_reddit_limit",
            )
        return value

    def build_feed_url(
        self, subreddit: str, feed_type: RedditFeedType, limit: int
    ) -> str:
        safe_limit = self.normalize_limit(limit)
        return f"{REDDIT_BASE}/r/{subreddit}/{feed_type.value}.rss?limit={safe_limit}"

    def build_resolved_response(
        self,
        subreddit_input: str,
        limit: int,
        preview_items: list[PreviewItem],
    ) -> ResolvedSourceResponse:
        subreddit = self.normalize_subreddit_input(subreddit_input)
        safe_limit = self.normalize_limit(limit)
        feeds: list[FeedLink] = []
        for feed_type in RedditFeedType:
            label, description = REDDIT_FEED_META[feed_type.value]
            feeds.append(
                FeedLink(
                    label=label,
                    url=self.build_feed_url(subreddit, feed_type, safe_limit),
                    type=feed_type.value,
                    external=True,
                    description=description,
                )
            )

        return ResolvedSourceResponse(
            source=SourceType.reddit,
            input=subreddit_input,
            entity_name=f"r/{subreddit}",
            entity_url=f"{REDDIT_BASE}/r/{subreddit}/",
            feeds=feeds,
            preview_items=preview_items,
            preview_feed_label=f"r/{subreddit} · hot",
            metadata={"subreddit": subreddit, "limit": safe_limit},
        )

    def hot_feed_url(self, subreddit_input: str, limit: int) -> str:
        subreddit = self.normalize_subreddit_input(subreddit_input)
        return self.build_feed_url(subreddit, RedditFeedType.hot, limit)

    def _validate_subreddit_name(self, subreddit: str) -> str:
        normalized = subreddit.strip().strip("/")
        if not normalized:
            raise BadRequestError(
                "Enter a valid subreddit name.",
                error_code="invalid_reddit_input",
            )
        if not SUBREDDIT_RE.fullmatch(normalized):
            raise BadRequestError(
                "Use a valid subreddit name, for example r/selfhosted.",
                error_code="invalid_reddit_input",
            )
        return normalized


class FeedsearchService:
    def __init__(
        self,
        client: httpx.AsyncClient,
        cache: TTLFileCache,
        settings: Settings,
    ) -> None:
        self.client = client
        self.cache = cache
        self.settings = settings

    async def search(
        self,
        url: str,
        *,
        info: bool = True,
        favicon: bool = False,
        skip_crawl: bool = False,
        opml: bool = False,
    ) -> list[FeedsearchFeedResult] | str:
        target = (url or "").strip()
        if not target:
            raise BadRequestError(
                "The url query parameter is required.",
                error_code="missing_feedsearch_url",
            )

        cache_key = (
            f"feedsearch::{target}::info={info}::favicon={favicon}::"
            f"skip_crawl={skip_crawl}::opml={opml}"
        )
        cached = self.cache.get(cache_key, self.settings.feedsearch_cache_ttl_seconds)
        if cached is not None:
            if opml:
                return str(cached)
            return [FeedsearchFeedResult.model_validate(item) for item in cached]

        try:
            response = await self.client.get(
                self.settings.feedsearch_url,
                params={
                    "url": target,
                    "info": str(info).lower(),
                    "favicon": str(favicon).lower(),
                    "skip_crawl": str(skip_crawl).lower(),
                    "opml": str(opml).lower(),
                },
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(
                "Feedsearch is currently unavailable.",
                error_code="feedsearch_unavailable",
            ) from exc

        if response.status_code == 400:
            raise BadRequestError(
                "Feedsearch rejected the provided url.",
                error_code="feedsearch_bad_request",
            )
        if response.status_code >= 500:
            raise UpstreamServiceError(
                "Feedsearch returned an upstream error.",
                error_code="feedsearch_upstream_error",
            )
        if response.status_code >= 400:
            raise UpstreamServiceError(
                "Feedsearch request failed.",
                error_code="feedsearch_request_failed",
            )

        if opml:
            payload = response.text
            self.cache.set(cache_key, payload)
            return payload

        try:
            data = response.json()
        except ValueError as exc:
            raise UpstreamServiceError(
                "Feedsearch returned an invalid response.",
                error_code="feedsearch_invalid_response",
            ) from exc

        if not isinstance(data, list):
            raise UpstreamServiceError(
                "Feedsearch returned an unexpected response shape.",
                error_code="feedsearch_invalid_response",
            )

        results = [FeedsearchFeedResult.model_validate(item) for item in data]
        self.cache.set(cache_key, [result.model_dump() for result in results])
        return results

    async def build_resolved_response(
        self,
        url: str,
        preview_items: list[PreviewItem],
        *,
        info: bool = True,
        favicon: bool = False,
        skip_crawl: bool = False,
        results: list[FeedsearchFeedResult] | None = None,
    ) -> ResolvedSourceResponse:
        if results is None:
            results = await self.search(
                url,
                info=info,
                favicon=favicon,
                skip_crawl=skip_crawl,
                opml=False,
            )
        if not isinstance(results, list) or not results:
            raise NotFoundError(
                "No feeds were found for that website.",
                error_code="website_feeds_not_found",
            )

        first = results[0]
        entity_name = first.site_name or first.title or first.site_url or url
        entity_url = first.site_url or first.url
        feeds = [
            FeedLink(
                label=result.title or result.site_name or result.url,
                url=result.url,
                type=result.version or "feed",
                external=True,
                count=result.item_count,
                description=result.description,
                is_podcast=result.is_podcast,
            )
            for result in results
        ]

        preview_feed_label = None
        if preview_items:
            preview_feed_label = f"{entity_name} · {results[0].url}"

        return ResolvedSourceResponse(
            source=SourceType.website,
            input=url,
            entity_name=entity_name,
            entity_url=entity_url,
            feeds=feeds,
            preview_items=preview_items,
            preview_feed_label=preview_feed_label,
            attribution=FEEDSEARCH_ATTRIBUTION,
            metadata={
                "provider": "feedsearch",
                "feedsearch_results": [result.model_dump() for result in results],
            },
        )


def build_service_container(
    settings: Settings, client: httpx.AsyncClient
) -> ServiceContainer:
    cache = TTLFileCache(
        cache_dir=settings.cache_dir,
        max_cache_age_seconds=settings.cache_max_age_seconds,
    )
    preview = PreviewService(
        client=client,
        user_agent=settings.user_agent,
        timeout_seconds=settings.preview_timeout_seconds,
    )
    youtube = YouTubeService(
        cache=cache,
        channel_cache_ttl_seconds=settings.channel_cache_ttl_seconds,
    )
    reddit = RedditService()
    feedsearch = FeedsearchService(client=client, cache=cache, settings=settings)
    return ServiceContainer(
        settings=settings,
        cache=cache,
        preview=preview,
        youtube=youtube,
        reddit=reddit,
        feedsearch=feedsearch,
    )
