import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend import database
from backend.auth import authenticate_request, require_request_user, require_session_user
from backend.config import Config
from backend.worker import extract_article_content_with_readability
from backend.youtube_embed import convert_links_to_embeds

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/external", tags=["external-api"])

STREAM_POLL_INTERVAL_SECONDS = 2
STREAM_HEARTBEAT_SECONDS = 15
STREAM_CURSOR_PATTERN = re.compile(r"^a(?P<article_id>\d+)-n(?P<notification_id>\d+)$")


class ExternalApiConfigPayload(BaseModel):
    enabled: bool | None = None
    sse_enabled: bool | None = None


class ExternalArticleExtractPayload(BaseModel):
    force_refresh: bool = Field(default=False)


def _default_external_api_settings() -> dict[str, bool]:
    return {"enabled": False, "sse_enabled": True}


async def _get_external_api_settings(conn: Any, user_id: int) -> dict[str, bool]:
    row = await conn.fetchrow(
        "SELECT is_enabled, sse_enabled FROM user_external_api_settings WHERE user_id = $1",
        user_id,
    )
    if not row:
        return _default_external_api_settings()
    return {
        "enabled": bool(row["is_enabled"]),
        "sse_enabled": bool(row["sse_enabled"]),
    }


async def _save_external_api_settings(
    conn: Any, user_id: int, *, enabled: bool, sse_enabled: bool
) -> dict[str, bool]:
    await conn.execute(
        """
        INSERT INTO user_external_api_settings (user_id, is_enabled, sse_enabled, updated_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (user_id)
        DO UPDATE SET is_enabled = $2, sse_enabled = $3, updated_at = NOW()
        """,
        user_id,
        enabled,
        sse_enabled,
    )
    return {"enabled": enabled, "sse_enabled": sse_enabled}


def _build_external_api_config_response(request: Request, settings: dict[str, bool]) -> dict[str, Any]:
    public_base_url = Config.PUBLIC_URL.rstrip("/") if Config.PUBLIC_URL else None
    return {
        **settings,
        "public_base_url": public_base_url,
        "endpoints": {
            "categories": "/api/external/categories",
            "feeds": "/api/external/feeds",
            "articles": "/api/external/articles",
            "article_detail": "/api/external/articles/{article_id}",
            "article_extract": "/api/external/articles/{article_id}/extract",
            "stream": "/api/external/stream",
        },
        "auth": {
            "scheme": "Bearer",
            "token_prefix": "nsy_",
            "note": "Use a personal API token in the Authorization header.",
        },
    }


async def _require_external_api_enabled(request: Request, *, require_sse: bool = False) -> dict[str, Any]:
    user = require_request_user(request)
    conn = await database.get_db_connection()
    try:
        settings = await _get_external_api_settings(conn, user["id"])
    finally:
        await database.release_db_connection(conn)

    if not settings["enabled"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="External API is disabled for this account",
        )
    if require_sse and not settings["sse_enabled"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="External API streaming is disabled for this account",
        )
    return user


def _parse_since(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid ISO 8601 timestamp") from exc


def _append_article_filters(
    query_parts: list[str],
    params: list[Any],
    *,
    article_id: int | None = None,
    category: str | None = None,
    feed_url: str | None = None,
    starred: bool = False,
    search_query: str | None = None,
    since: datetime | None = None,
) -> None:
    if article_id is not None:
        params.append(article_id)
        query_parts.append(f"AND a.id = ${len(params)}")

    if category:
        params.append(category)
        query_parts.append(f"AND a.category = ${len(params)}")

    if feed_url:
        params.append(feed_url)
        query_parts.append(f"AND f.url = ${len(params)}")

    if since is not None:
        params.append(since)
        query_parts.append(f"AND a.published_datetime >= ${len(params)}")

    if starred:
        query_parts.append("AND COALESCE(uas.is_saved, false) = true")

    if search_query:
        params.append(f"%{search_query}%")
        query_parts.append(
            f"AND (a.title ILIKE ${len(params)} OR a.description ILIKE ${len(params)} OR a.content ILIKE ${len(params)})"
        )


def _serialize_article_row(row: Any, *, include_content: bool = False) -> dict[str, Any]:
    has_full_content = _has_full_content(row["content"])
    payload = {
        "id": row["id"],
        "title": row["title"],
        "link": row["link"],
        "description": row["description"],
        "thumbnail": row["thumbnail"],
        "published": row["published"],
        "published_at": row["published_datetime"].isoformat()
        if row["published_datetime"]
        else None,
        "category": row["category"],
        "source": row["source"] or "Unknown",
        "starred": bool(row["starred"]),
        "read": bool(row["is_read"]),
        "has_full_content": has_full_content,
        "feed": {
            "id": row["feed_id"],
            "name": row["feed_name"],
            "url": row["feed_url"],
        },
    }
    if include_content:
        payload["content"] = row["content"]
    return payload


def _has_full_content(content: str | None) -> bool:
    if not content or not content.strip():
        return False

    normalized = content.strip().lower()
    invalid_markers = (
        "<p>no content could be extracted.</p>",
        "<p>request timed out while fetching article.</p>",
    )
    if normalized in invalid_markers:
        return False
    if normalized.startswith("<p>failed to fetch article"):
        return False
    if normalized.startswith("<p>error extracting content"):
        return False
    return True


def _article_select_columns(*, include_content: bool) -> list[str]:
    columns = [
        "a.id",
        "a.title",
        "a.link",
        "a.description",
        "a.thumbnail",
        "a.published",
        "a.published_datetime",
        "a.category",
        "a.source",
        "COALESCE(uas.is_saved, false) AS starred",
        "COALESCE(uas.is_read, false) AS is_read",
        "f.id AS feed_id",
        "f.name AS feed_name",
        "f.url AS feed_url",
    ]
    if include_content:
        columns.append("a.content")
    else:
        columns.append("NULL::TEXT AS content")
    return columns


async def _get_article_row(
    conn: Any, user_id: int, article_id: int, *, include_content: bool = True
) -> Any:
    query_parts = [
        f"SELECT {', '.join(_article_select_columns(include_content=include_content))}",
        "FROM articles a",
        'JOIN feeds f ON f.id = a.feed_id AND f.user_id = $1 AND f."isActive" = true',
        "LEFT JOIN user_article_state uas ON uas.article_id = a.id AND uas.user_id = $1",
        "WHERE a.user_id = $1",
    ]
    params: list[Any] = [user_id]
    _append_article_filters(query_parts, params, article_id=article_id)
    return await conn.fetchrow("\n".join(query_parts), *params)


def _serialize_notification_row(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "channel": row["channel"],
        "kind": row["kind"],
        "title": row["title"],
        "body": row["body"],
        "link": row["link"],
        "article_id": row["article_id"],
        "sent_at": row["sent_at"].isoformat() if row["sent_at"] else None,
    }


def _parse_stream_cursor(last_event_id: str | None) -> tuple[int, int]:
    if not last_event_id:
        return 0, 0

    match = STREAM_CURSOR_PATTERN.fullmatch(last_event_id.strip())
    if not match:
        return 0, 0

    return int(match.group("article_id")), int(match.group("notification_id"))


def _format_stream_cursor(article_id: int, notification_id: int) -> str:
    return f"a{article_id}-n{notification_id}"


def _format_sse(event: str, data: dict[str, Any], event_id: str | None = None) -> str:
    message_parts = []
    if event_id:
        message_parts.append(f"id: {event_id}")
    if event:
        message_parts.append(f"event: {event}")
    message_parts.append(f"data: {json.dumps(data, separators=(',', ':'))}")
    return "\n".join(message_parts) + "\n\n"


async def _fetch_stream_articles(
    conn: Any,
    user_id: int,
    article_cursor: int,
    *,
    category: str | None,
    feed_url: str | None,
    since: datetime | None,
) -> list[Any]:
    query_parts = [
        """
        SELECT a.id, a.title, a.link, a.description, a.thumbnail, a.published, a.published_datetime,
               a.category, a.content, a.source,
               COALESCE(uas.is_saved, false) AS starred,
               COALESCE(uas.is_read, false) AS is_read,
               f.id AS feed_id, f.name AS feed_name, f.url AS feed_url
        FROM articles a
        JOIN feeds f ON f.id = a.feed_id AND f.user_id = $1
        LEFT JOIN user_article_state uas ON uas.article_id = a.id AND uas.user_id = $1
        WHERE a.user_id = $1
        """
    ]
    params: list[Any] = [user_id]

    if article_cursor > 0:
        params.append(article_cursor)
        query_parts.append(f"AND a.id > ${len(params)}")
    elif since is not None:
        params.append(since)
        query_parts.append(f"AND a.published_datetime >= ${len(params)}")

    if category:
        params.append(category)
        query_parts.append(f"AND a.category = ${len(params)}")

    if feed_url:
        params.append(feed_url)
        query_parts.append(f"AND f.url = ${len(params)}")

    query_parts.append("ORDER BY a.id ASC LIMIT 50")
    return await conn.fetch("\n".join(query_parts), *params)


async def _fetch_stream_notifications(
    conn: Any,
    user_id: int,
    notification_cursor: int,
    *,
    category: str | None,
    feed_url: str | None,
    since: datetime | None,
) -> list[Any]:
    query_parts = [
        """
        SELECT n.id, n.channel, n.kind, n.title, n.body, n.link, n.article_id, n.sent_at
        FROM user_notifications n
        LEFT JOIN articles a ON a.id = n.article_id AND a.user_id = $1
        LEFT JOIN feeds f ON f.id = a.feed_id AND f.user_id = $1
        WHERE n.user_id = $1
        """
    ]
    params: list[Any] = [user_id]

    if notification_cursor > 0:
        params.append(notification_cursor)
        query_parts.append(f"AND n.id > ${len(params)}")
    elif since is not None:
        params.append(since)
        query_parts.append(f"AND n.sent_at >= ${len(params)}")

    if category:
        params.append(category)
        query_parts.append(f"AND a.category = ${len(params)}")

    if feed_url:
        params.append(feed_url)
        query_parts.append(f"AND f.url = ${len(params)}")

    query_parts.append("ORDER BY n.id ASC LIMIT 50")
    return await conn.fetch("\n".join(query_parts), *params)


@router.get("/config")
async def get_external_api_config(request: Request) -> JSONResponse:
    user = require_session_user(request)
    conn = await database.get_db_connection()
    try:
        settings = await _get_external_api_settings(conn, user["id"])
    finally:
        await database.release_db_connection(conn)

    response = JSONResponse(_build_external_api_config_response(request, settings))
    response.headers["Cache-Control"] = "no-store"
    return response


@router.put("/config")
async def update_external_api_config(
    payload: ExternalApiConfigPayload, request: Request
) -> JSONResponse:
    user = require_session_user(request)
    conn = await database.get_db_connection()
    try:
        existing = await _get_external_api_settings(conn, user["id"])
        next_enabled = payload.enabled if payload.enabled is not None else existing["enabled"]
        next_sse_enabled = (
            payload.sse_enabled
            if payload.sse_enabled is not None
            else existing["sse_enabled"]
        )
        settings = await _save_external_api_settings(
            conn,
            user["id"],
            enabled=next_enabled,
            sse_enabled=next_enabled and next_sse_enabled,
        )
    finally:
        await database.release_db_connection(conn)

    response = JSONResponse(_build_external_api_config_response(request, settings))
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/categories")
async def list_external_categories(request: Request) -> JSONResponse:
    user = await _require_external_api_enabled(request)
    conn = await database.get_db_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT c.id,
                   c.name,
                   c.priority,
                   c.is_default,
                   COUNT(DISTINCT f.id) AS feed_count,
                   COUNT(DISTINCT a.id) AS article_count,
                   COUNT(DISTINCT CASE WHEN uas.is_read IS NULL OR uas.is_read = false THEN a.id END) AS unread_count
            FROM categories c
            LEFT JOIN feeds f ON f.category_id = c.id AND f.user_id = c.user_id
            LEFT JOIN articles a ON a.category_id = c.id AND a.user_id = c.user_id
            LEFT JOIN user_article_state uas ON uas.article_id = a.id AND uas.user_id = c.user_id
            WHERE c.user_id = $1
            GROUP BY c.id, c.name, c.priority, c.is_default
            ORDER BY c.priority ASC, c.name ASC
            """,
            user["id"],
        )
        return JSONResponse(
            {
                "items": [
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "priority": row["priority"],
                        "is_default": row["is_default"],
                        "feed_count": row["feed_count"],
                        "article_count": row["article_count"],
                        "unread_count": row["unread_count"],
                    }
                    for row in rows
                ]
            }
        )
    finally:
        await database.release_db_connection(conn)


@router.get("/feeds")
async def list_external_feeds(request: Request) -> JSONResponse:
    user = await _require_external_api_enabled(request)
    conn = await database.get_db_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT f.id,
                   f.name,
                   f.url,
                   f."isActive" AS is_active,
                   f.priority,
                   f.retention_days,
                   f.polling_interval,
                   f.fetch_full_content,
                   c.id AS category_id,
                   c.name AS category_name,
                   COUNT(DISTINCT a.id) AS article_count,
                   COUNT(DISTINCT CASE WHEN uas.is_read IS NULL OR uas.is_read = false THEN a.id END) AS unread_count
            FROM feeds f
            JOIN categories c ON c.id = f.category_id AND c.user_id = f.user_id
            LEFT JOIN articles a ON a.feed_id = f.id AND a.user_id = f.user_id
            LEFT JOIN user_article_state uas ON uas.article_id = a.id AND uas.user_id = f.user_id
            WHERE f.user_id = $1
            GROUP BY f.id, c.id, c.name
            ORDER BY c.name ASC, f.priority ASC, f.name ASC
            """,
            user["id"],
        )
        return JSONResponse(
            {
                "items": [
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "url": row["url"],
                        "is_active": row["is_active"],
                        "priority": row["priority"],
                        "retention_days": row["retention_days"],
                        "polling_interval": row["polling_interval"],
                        "fetch_full_content": row["fetch_full_content"],
                        "article_count": row["article_count"],
                        "unread_count": row["unread_count"],
                        "category": {
                            "id": row["category_id"],
                            "name": row["category_name"],
                        },
                    }
                    for row in rows
                ]
            }
        )
    finally:
        await database.release_db_connection(conn)


@router.get("/articles")
async def list_external_articles(
    request: Request,
    category: str | None = Query(default=None),
    feed_url: str | None = Query(default=None),
    q: str | None = Query(default=None),
    since: str | None = Query(default=None),
    starred: bool = Query(default=False),
    include_content: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JSONResponse:
    user = await _require_external_api_enabled(request)
    since_dt = _parse_since(since)
    conn = await database.get_db_connection()
    try:
        query_parts = [
            f"SELECT {', '.join(_article_select_columns(include_content=include_content))}",
            "FROM articles a",
            'JOIN feeds f ON f.id = a.feed_id AND f.user_id = $1 AND f."isActive" = true',
            "LEFT JOIN user_article_state uas ON uas.article_id = a.id AND uas.user_id = $1",
            "WHERE a.user_id = $1",
        ]
        params: list[Any] = [user["id"]]
        _append_article_filters(
            query_parts,
            params,
            category=category,
            feed_url=feed_url,
            starred=starred,
            search_query=q,
            since=since_dt,
        )
        query_parts.append("ORDER BY a.published_datetime DESC NULLS LAST, a.id DESC")
        params.extend([limit, offset])
        query_parts.append(f"LIMIT ${len(params) - 1} OFFSET ${len(params)}")

        count_query_parts = [
            "SELECT COUNT(*)",
            "FROM articles a",
            'JOIN feeds f ON f.id = a.feed_id AND f.user_id = $1 AND f."isActive" = true',
            "LEFT JOIN user_article_state uas ON uas.article_id = a.id AND uas.user_id = $1",
            "WHERE a.user_id = $1",
        ]
        count_params: list[Any] = [user["id"]]
        _append_article_filters(
            count_query_parts,
            count_params,
            category=category,
            feed_url=feed_url,
            starred=starred,
            search_query=q,
            since=since_dt,
        )

        rows = await conn.fetch("\n".join(query_parts), *params)
        total = await conn.fetchval("\n".join(count_query_parts), *count_params)

        return JSONResponse(
            {
                "items": [
                    _serialize_article_row(row, include_content=include_content)
                    for row in rows
                ],
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total": total,
                    "has_more": offset + limit < total,
                },
            }
        )
    finally:
        await database.release_db_connection(conn)


@router.get("/articles/{article_id}")
async def get_external_article(article_id: int, request: Request) -> JSONResponse:
    user = await _require_external_api_enabled(request)
    conn = await database.get_db_connection()
    try:
        row = await _get_article_row(conn, user["id"], article_id, include_content=True)
        if not row:
            raise HTTPException(status_code=404, detail="Article not found")
        return JSONResponse({"item": _serialize_article_row(row, include_content=True)})
    finally:
        await database.release_db_connection(conn)


@router.post("/articles/{article_id}/extract")
async def extract_external_article_content(
    article_id: int,
    request: Request,
    payload: ExternalArticleExtractPayload | None = None,
) -> JSONResponse:
    user = await _require_external_api_enabled(request)
    request_payload = payload or ExternalArticleExtractPayload()
    conn = await database.get_db_connection()
    try:
        row = await _get_article_row(conn, user["id"], article_id, include_content=True)
        if not row:
            raise HTTPException(status_code=404, detail="Article not found")

        existing_content = row["content"]
        cached = _has_full_content(existing_content)
        extraction_performed = False

        if request_payload.force_refresh or not cached:
            extracted_content = await extract_article_content_with_readability(row["link"])
            extraction_performed = True
            if not _has_full_content(extracted_content):
                raise HTTPException(
                    status_code=422,
                    detail="Full article content could not be extracted for this article",
                )

            normalized_content = convert_links_to_embeds(extracted_content)
            await conn.execute(
                "UPDATE articles SET content = $1 WHERE id = $2 AND user_id = $3",
                normalized_content,
                article_id,
                user["id"],
            )
            row = await _get_article_row(conn, user["id"], article_id, include_content=True)
            cached = False

        return JSONResponse(
            {
                "item": _serialize_article_row(row, include_content=True),
                "extraction": {
                    "performed": extraction_performed,
                    "cached": cached and not request_payload.force_refresh,
                    "force_refresh": request_payload.force_refresh,
                },
            }
        )
    finally:
        await database.release_db_connection(conn)


@router.get("/stream")
async def stream_external_events(
    request: Request,
    category: str | None = Query(default=None),
    feed_url: str | None = Query(default=None),
    since: str | None = Query(default=None),
    include_notifications: bool = Query(default=True),
) -> StreamingResponse:
    user = await _require_external_api_enabled(request, require_sse=True)
    since_dt = _parse_since(since)
    last_event_id = request.headers.get("last-event-id") or request.query_params.get("last_event_id")
    article_cursor, notification_cursor = _parse_stream_cursor(last_event_id)

    async def event_generator():
        nonlocal article_cursor, notification_cursor
        loop = asyncio.get_running_loop()
        last_heartbeat_at = loop.time()
        next_revalidation_at = last_heartbeat_at
        ready_cursor = _format_stream_cursor(article_cursor, notification_cursor)
        yield _format_sse(
            "ready",
            {
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "article_cursor": article_cursor,
                "notification_cursor": notification_cursor,
            },
            ready_cursor,
        )

        while True:
            if await request.is_disconnected():
                break

            now = loop.time()
            if now >= next_revalidation_at:
                current_user = await authenticate_request(
                    request, touch_api_token_last_used=False
                )
                if not current_user or current_user["id"] != user["id"]:
                    yield _format_sse(
                        "stream.closed",
                        {"reason": "authentication_expired"},
                        _format_stream_cursor(article_cursor, notification_cursor),
                    )
                    break
                next_revalidation_at = now + STREAM_HEARTBEAT_SECONDS

            conn = await database.get_db_connection()
            try:
                stream_settings = await _get_external_api_settings(conn, user["id"])
                if not stream_settings["enabled"] or not stream_settings["sse_enabled"]:
                    yield _format_sse(
                        "stream.closed",
                        {"reason": "stream_disabled"},
                        _format_stream_cursor(article_cursor, notification_cursor),
                    )
                    break

                article_rows = await _fetch_stream_articles(
                    conn,
                    user["id"],
                    article_cursor,
                    category=category,
                    feed_url=feed_url,
                    since=since_dt,
                )
                notification_rows = (
                    await _fetch_stream_notifications(
                        conn,
                        user["id"],
                        notification_cursor,
                        category=category,
                        feed_url=feed_url,
                        since=since_dt,
                    )
                    if include_notifications
                    else []
                )
            finally:
                await database.release_db_connection(conn)

            emitted = False

            for row in article_rows:
                article_cursor = max(article_cursor, int(row["id"]))
                emitted = True
                yield _format_sse(
                    "article.created",
                    _serialize_article_row(row, include_content=False),
                    _format_stream_cursor(article_cursor, notification_cursor),
                )

            for row in notification_rows:
                notification_cursor = max(notification_cursor, int(row["id"]))
                emitted = True
                yield _format_sse(
                    "notification.created",
                    _serialize_notification_row(row),
                    _format_stream_cursor(article_cursor, notification_cursor),
                )

            if not emitted and now - last_heartbeat_at >= STREAM_HEARTBEAT_SECONDS:
                last_heartbeat_at = now
                yield _format_sse(
                    "heartbeat",
                    {
                        "connected": True,
                        "server_time": datetime.now(timezone.utc).isoformat(),
                    },
                    _format_stream_cursor(article_cursor, notification_cursor),
                )

            await asyncio.sleep(STREAM_POLL_INTERVAL_SECONDS)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
