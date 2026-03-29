from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    youtube = "youtube"
    reddit = "reddit"
    website = "website"


class YouTubeFeedType(str, Enum):
    all = "all"
    videos = "videos"
    shorts = "shorts"
    live = "live"


class RedditFeedType(str, Enum):
    hot = "hot"
    new = "new"
    rising = "rising"
    top = "top"
    controversial = "controversial"


class Attribution(BaseModel):
    label: str
    url: str


class FeedLink(BaseModel):
    label: str
    url: str
    type: str
    external: bool = True
    count: int | None = None
    description: str | None = None
    is_podcast: bool = False


class PreviewItem(BaseModel):
    title: str
    url: str
    published: str = ""
    author: str = ""
    badge: str = ""


class FeedsearchFeedResult(BaseModel):
    bozo: int = 0
    content_length: int | None = None
    content_type: str | None = None
    description: str | None = None
    favicon: str | None = None
    favicon_data_uri: str | None = None
    hubs: list[str] = Field(default_factory=list)
    is_podcast: bool = False
    is_push: bool = False
    item_count: int | None = None
    last_seen: str | None = None
    last_updated: str | None = None
    score: int | float | None = None
    self_url: str | None = None
    site_name: str | None = None
    site_url: str | None = None
    title: str | None = None
    url: str
    velocity: float | None = None
    version: str | None = None


class FeedsearchSearchResponse(BaseModel):
    query: str
    results: list[FeedsearchFeedResult]
    attribution: Attribution


class ResolvedSourceResponse(BaseModel):
    source: SourceType
    input: str
    entity_name: str
    entity_url: str | None = None
    feeds: list[FeedLink]
    preview_items: list[PreviewItem] = Field(default_factory=list)
    preview_feed_label: str | None = None
    attribution: Attribution | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error_code: str
    detail: str


class HealthResponse(BaseModel):
    status: str
