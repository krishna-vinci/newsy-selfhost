import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
import httpx

from backend import database, notification_templates
from backend.auth import require_request_user
from backend.config import Config

try:
    from pywebpush import WebPushException, webpush
except (
    ImportError
):  # pragma: no cover - optional dependency during local dev until installed
    WebPushException = Exception
    webpush = None


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationReadPayload(BaseModel):
    is_read: bool = True


class TelegramPreferencesPayload(BaseModel):
    chat_id: Optional[str] = None
    enabled: bool = True


class PushSubscriptionKeysPayload(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionPayload(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeysPayload


class PushUnsubscribePayload(BaseModel):
    endpoint: str


def build_app_link(path: str, *, require_absolute: bool = False) -> Optional[str]:
    if path.startswith(("http://", "https://")):
        return path
    if Config.PUBLIC_URL:
        return f"{Config.PUBLIC_URL.rstrip('/')}{path}"
    if require_absolute:
        return None
    return path


def sanitize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    sanitized = text.replace("\n", " ").replace("\r", "")
    return " ".join(sanitized.split())


def sanitize_multiline(text: Optional[str]) -> str:
    """Collapse whitespace within lines but keep line breaks (in-app bodies)."""
    if not text:
        return ""
    lines = [" ".join(line.split()) for line in text.replace("\r", "").split("\n")]
    return "\n".join(line for line in lines if line)


def truncate_multiline(text: Optional[str], max_length: int = 500) -> str:
    cleaned = sanitize_multiline(text)
    if len(cleaned) <= max_length:
        return cleaned
    return f"{cleaned[: max_length - 3].rstrip()}..."


def truncate_text(text: Optional[str], max_length: int = 220) -> str:
    cleaned = sanitize_text(text)
    if len(cleaned) <= max_length:
        return cleaned
    return f"{cleaned[: max_length - 3].rstrip()}..."


def _web_push_available() -> bool:
    return bool(
        webpush
        and Config.WEB_PUSH_VAPID_PUBLIC_KEY
        and Config.WEB_PUSH_VAPID_PRIVATE_KEY
        and Config.WEB_PUSH_SUBJECT
    )


def _parse_json_config(raw_config: Any) -> dict[str, Any]:
    if not raw_config:
        return {}
    if isinstance(raw_config, dict):
        return raw_config
    if isinstance(raw_config, str):
        try:
            return json.loads(raw_config)
        except json.JSONDecodeError:
            return {}
    return {}


async def get_user_integration(
    conn: Any, user_id: int, provider: str
) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        "SELECT id, provider, config, is_enabled FROM user_integrations WHERE user_id = $1 AND provider = $2",
        user_id,
        provider,
    )
    if not row:
        return None
    return {
        "id": row["id"],
        "provider": row["provider"],
        "config": _parse_json_config(row["config"]),
        "is_enabled": row["is_enabled"],
    }


async def upsert_user_integration(
    conn: Any,
    user_id: int,
    provider: str,
    config: dict[str, Any],
    is_enabled: bool = True,
) -> None:
    await conn.execute(
        """
        INSERT INTO user_integrations (user_id, provider, config, is_enabled, updated_at)
        VALUES ($1, $2, $3::jsonb, $4, NOW())
        ON CONFLICT (user_id, provider)
        DO UPDATE SET config = $3::jsonb, is_enabled = $4, updated_at = NOW()
        """,
        user_id,
        provider,
        json.dumps(config),
        is_enabled,
    )


async def record_in_app_notification(
    user_id: int,
    title: str,
    body: Optional[str],
    link: Optional[str],
    *,
    article_id: Optional[int] = None,
    kind: str = "article",
) -> None:
    conn = await database.get_db_connection()
    try:
        await conn.execute(
            """
            INSERT INTO user_notifications (user_id, article_id, channel, kind, title, body, link)
            VALUES ($1, $2, 'in_app', $3, $4, $5, $6)
            """,
            user_id,
            article_id,
            kind,
            sanitize_text(title),
            truncate_multiline(body, 500),
            link,
        )
    finally:
        await database.release_db_connection(conn)


async def _send_telegram_message(
    chat_id: str,
    title: str,
    body: str,
    link: Optional[str],
    *,
    articles: Optional[list[dict[str, Any]]] = None,
    footer: Optional[str] = None,
    published_label: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    button_text: str = "Open article",
) -> bool:
    bot_token = Config.TELEGRAM_BOT_TOKEN
    if not bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not configured")
        return False

    resolved = notification_templates.resolve_telegram_payload(
        title,
        body,
        link,
        articles=articles,
        footer=footer,
        published_label=published_label,
        thumbnail_url=thumbnail_url,
        button_text=button_text,
    )

    reply_markup = None
    if resolved["button_url"]:
        reply_markup = json.dumps(
            {
                "inline_keyboard": [
                    [{"text": button_text, "url": resolved["button_url"]}]
                ]
            }
        )

    base_url = f"https://api.telegram.org/bot{bot_token}"
    disable_preview = bool(articles)

    async with httpx.AsyncClient(timeout=10.0) as client:
        if resolved["as_photo"]:
            photo_payload = {
                "chat_id": chat_id,
                "photo": resolved["thumbnail_url"],
                "caption": resolved["text"],
                "parse_mode": "HTML",
            }
            if reply_markup:
                photo_payload["reply_markup"] = reply_markup
            try:
                response = await client.post(
                    f"{base_url}/sendPhoto", json=photo_payload
                )
                response.raise_for_status()
                return True
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "Telegram sendPhoto failed, falling back to text: %s",
                    exc.response.text,
                )
            except Exception as exc:  # pragma: no cover - network dependent
                logger.warning("Telegram sendPhoto failed: %s", exc)

        message_payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": resolved["text"],
            "parse_mode": "HTML",
            "disable_web_page_preview": disable_preview,
        }
        if reply_markup:
            message_payload["reply_markup"] = reply_markup

        try:
            response = await client.post(
                f"{base_url}/sendMessage", json=message_payload
            )
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("Failed to send Telegram notification: %s", exc.response.text)
            if exc.response.status_code == 400:
                # Formatting was rejected (bad entities, stale photo, …) —
                # retry once as plain text so the alert is not lost.
                plain_payload: dict[str, Any] = {
                    "chat_id": chat_id,
                    "text": notification_templates.telegram_html_to_plain(
                        resolved["text"]
                    )[: notification_templates.TELEGRAM_MESSAGE_LIMIT],
                    "disable_web_page_preview": True,
                }
                if reply_markup:
                    plain_payload["reply_markup"] = reply_markup
                try:
                    response = await client.post(
                        f"{base_url}/sendMessage", json=plain_payload
                    )
                    response.raise_for_status()
                    return True
                except Exception as retry_exc:
                    logger.error("Plain-text Telegram retry failed: %s", retry_exc)
        except Exception as exc:  # pragma: no cover - network errors are environment-dependent
            logger.error("Failed to send Telegram notification: %s", exc)
    return False


async def send_telegram_notification(
    user_id: int,
    category_id: Optional[int],
    title: str,
    body: Optional[str],
    link: Optional[str],
    *,
    articles: Optional[list[dict[str, Any]]] = None,
    footer: Optional[str] = None,
    published_label: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    button_text: str = "Open article",
) -> bool:
    conn = await database.get_db_connection()
    try:
        if category_id is not None:
            category_row = await conn.fetchrow(
                "SELECT telegram_enabled FROM categories WHERE id = $1 AND user_id = $2",
                category_id,
                user_id,
            )
            if not category_row or category_row["telegram_enabled"] is False:
                return False

        integration = await get_user_integration(conn, user_id, "telegram")
        if not integration or not integration["is_enabled"]:
            return False

        chat_id = (integration["config"] or {}).get("chat_id")
        if not chat_id:
            return False
    finally:
        await database.release_db_connection(conn)

    telegram_link = build_app_link(link, require_absolute=True) if link else None
    return await _send_telegram_message(
        chat_id,
        title,
        body or "",
        telegram_link,
        articles=articles,
        footer=footer,
        published_label=published_label,
        thumbnail_url=thumbnail_url,
        button_text=button_text,
    )


async def send_web_push_notification(
    user_id: int,
    category_id: Optional[int],
    title: str,
    body: Optional[str],
    link: Optional[str],
    *,
    tag: Optional[str] = None,
) -> bool:
    if not _web_push_available():
        return False

    conn = await database.get_db_connection()
    try:
        if category_id is not None:
            web_push_enabled = await conn.fetchval(
                "SELECT web_push_enabled FROM categories WHERE id = $1 AND user_id = $2",
                category_id,
                user_id,
            )
            if web_push_enabled is False:
                return False

        rows = await conn.fetch(
            """
            SELECT id, endpoint, p256dh_key, auth_key
            FROM user_push_subscriptions
            WHERE user_id = $1
            ORDER BY updated_at DESC
            """,
            user_id,
        )
    finally:
        await database.release_db_connection(conn)

    if not rows:
        return False

    payload = json.dumps(
        {
            "title": sanitize_text(title),
            "body": truncate_text(body, 240),
            "url": link or "/feeds",
            "tag": tag or f"newsy-{user_id}",
        }
    )

    delivered = False
    vapid_claims = {"sub": Config.WEB_PUSH_SUBJECT}

    for row in rows:
        subscription_info = {
            "endpoint": row["endpoint"],
            "keys": {"p256dh": row["p256dh_key"], "auth": row["auth_key"]},
        }
        try:
            await run_in_threadpool(
                webpush,
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=Config.WEB_PUSH_VAPID_PRIVATE_KEY,
                vapid_claims=vapid_claims,
                ttl=300,
            )
            delivered = True
        except WebPushException as exc:  # pragma: no cover - network/runtime dependent
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning(
                "Web push delivery failed for subscription %s: %s", row["id"], exc
            )
            if status_code in {404, 410}:
                cleanup_conn = await database.get_db_connection()
                try:
                    await cleanup_conn.execute(
                        "DELETE FROM user_push_subscriptions WHERE id = $1", row["id"]
                    )
                finally:
                    await database.release_db_connection(cleanup_conn)
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            logger.warning(
                "Web push delivery failed for subscription %s: %s", row["id"], exc
            )

    return delivered


async def deliver_notification(
    user_id: int,
    category_id: Optional[int],
    title: str,
    body: Optional[str],
    link: Optional[str],
    *,
    article_id: Optional[int] = None,
    kind: str = "article",
    push_tag: Optional[str] = None,
    push_body: Optional[str] = None,
    articles: Optional[list[dict[str, Any]]] = None,
    footer: Optional[str] = None,
    published_label: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    button_text: str = "Open article",
) -> None:
    await record_in_app_notification(
        user_id,
        title,
        body,
        link,
        article_id=article_id,
        kind=kind,
    )
    await send_web_push_notification(
        user_id, category_id, title, push_body or body, link, tag=push_tag
    )
    await send_telegram_notification(
        user_id,
        category_id,
        title,
        body,
        link,
        articles=articles,
        footer=footer,
        published_label=published_label,
        thumbnail_url=thumbnail_url,
        button_text=button_text,
    )


async def get_notification_preferences(user_id: int) -> dict[str, Any]:
    conn = await database.get_db_connection()
    try:
        telegram_integration = await get_user_integration(conn, user_id, "telegram")
        push_count = await conn.fetchval(
            "SELECT COUNT(*) FROM user_push_subscriptions WHERE user_id = $1", user_id
        )
    finally:
        await database.release_db_connection(conn)

    telegram_config = (telegram_integration or {}).get("config", {})

    return {
        "telegram": {
            "available": bool(Config.TELEGRAM_BOT_TOKEN),
            "enabled": bool((telegram_integration or {}).get("is_enabled")),
            "configured": bool(telegram_config.get("chat_id")),
            "chat_id": telegram_config.get("chat_id"),
        },
        "web_push": {
            "available": _web_push_available(),
            "configured": bool(push_count),
            "subscription_count": push_count or 0,
            "public_key": Config.WEB_PUSH_VAPID_PUBLIC_KEY
            if _web_push_available()
            else None,
        },
    }


@router.get("")
async def list_notifications(request: Request, limit: int = 30):
    user = require_request_user(request)
    conn = await database.get_db_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT id, channel, kind, title, body, link, is_read, sent_at
            FROM user_notifications
            WHERE user_id = $1
            ORDER BY sent_at DESC
            LIMIT $2
            """,
            user["id"],
            max(1, min(limit, 100)),
        )
        unread_count = await conn.fetchval(
            "SELECT COUNT(*) FROM user_notifications WHERE user_id = $1 AND is_read = false",
            user["id"],
        )
    finally:
        await database.release_db_connection(conn)

    return JSONResponse(
        jsonable_encoder(
            {
                "items": [dict(row) for row in rows],
                "unread_count": unread_count or 0,
            }
        )
    )


@router.get("/summary")
async def notifications_summary(request: Request):
    user = require_request_user(request)
    conn = await database.get_db_connection()
    try:
        unread_count = await conn.fetchval(
            "SELECT COUNT(*) FROM user_notifications WHERE user_id = $1 AND is_read = false",
            user["id"],
        )
    finally:
        await database.release_db_connection(conn)
    return JSONResponse({"unread_count": unread_count or 0})


@router.put("/{notification_id}")
async def update_notification_read_state(
    notification_id: int, payload: NotificationReadPayload, request: Request
):
    user = require_request_user(request)
    conn = await database.get_db_connection()
    try:
        updated = await conn.execute(
            """
            UPDATE user_notifications
            SET is_read = $1
            WHERE id = $2 AND user_id = $3
            """,
            payload.is_read,
            notification_id,
            user["id"],
        )
    finally:
        await database.release_db_connection(conn)

    if updated.endswith("0"):
        raise HTTPException(status_code=404, detail="Notification not found")

    return JSONResponse({"message": "Notification updated"})


@router.post("/read-all")
async def mark_all_notifications_read(request: Request):
    user = require_request_user(request)
    conn = await database.get_db_connection()
    try:
        await conn.execute(
            "UPDATE user_notifications SET is_read = true WHERE user_id = $1 AND is_read = false",
            user["id"],
        )
    finally:
        await database.release_db_connection(conn)
    return JSONResponse({"message": "Notifications marked as read"})


@router.get("/preferences")
async def notification_preferences(request: Request):
    user = require_request_user(request)
    return JSONResponse(await get_notification_preferences(user["id"]))


@router.put("/preferences/telegram")
async def update_telegram_preferences(
    request: Request, payload: TelegramPreferencesPayload
):
    user = require_request_user(request)

    chat_id = (payload.chat_id or "").strip() or None
    if payload.enabled and not chat_id:
        raise HTTPException(
            status_code=400, detail="Chat ID is required to enable Telegram"
        )

    conn = await database.get_db_connection()
    try:
        await upsert_user_integration(
            conn,
            user["id"],
            "telegram",
            {"chat_id": chat_id},
            is_enabled=payload.enabled and bool(chat_id),
        )
    finally:
        await database.release_db_connection(conn)

    return JSONResponse({"message": "Telegram preferences updated"})


@router.post("/preferences/telegram/test")
async def send_test_telegram_notification(request: Request):
    user = require_request_user(request)
    sent = await send_telegram_notification(
        user["id"],
        None,
        "newsy Telegram is connected",
        "You will now receive article alerts for categories where Telegram is enabled.",
        build_app_link("/feeds", require_absolute=True),
    )
    if not sent:
        raise HTTPException(
            status_code=400,
            detail="Telegram is not ready yet. Start the bot, save your chat ID, and try again.",
        )
    return JSONResponse({"message": "Test notification sent"})


@router.post("/telegram/sample")
async def send_sample_telegram_notification(request: Request):
    """
    Send a demo of each notification style (batch, filter match, system).

    Messages are delivered only when the user has Telegram configured, but
    every style's rendered previews are always returned so the formats can
    be inspected without any delivery.
    """
    user = require_request_user(request)

    samples = notification_templates.build_sample_payloads(
        build_app_link("/feeds", require_absolute=True)
    )

    rendered: dict[str, dict[str, Any]] = {}
    for style, payload in samples.items():
        resolved = notification_templates.resolve_telegram_payload(
            payload["title"],
            payload["body"],
            payload.get("app_link"),
            articles=payload.get("telegram", {}).get("articles"),
            published_label=payload.get("telegram", {}).get("published_label"),
            thumbnail_url=payload.get("telegram", {}).get("thumbnail_url"),
            button_text=payload.get("telegram", {}).get(
                "button_text", "Open article"
            ),
        )
        rendered[style] = {
            "title": payload["title"],
            "in_app_body": payload["body"],
            "push_body": payload.get("push_body") or payload["body"],
            "telegram": resolved,
        }

    conn = await database.get_db_connection()
    try:
        integration = await get_user_integration(conn, user["id"], "telegram")
    finally:
        await database.release_db_connection(conn)

    chat_id = ((integration or {}).get("config") or {}).get("chat_id")
    delivered = False
    if (
        integration
        and integration["is_enabled"]
        and chat_id
        and Config.TELEGRAM_BOT_TOKEN
    ):
        for payload in samples.values():
            telegram = payload.get("telegram", {})
            if await _send_telegram_message(
                chat_id,
                payload["title"],
                payload["body"],
                payload.get("app_link"),
                articles=telegram.get("articles"),
                published_label=telegram.get("published_label"),
                thumbnail_url=telegram.get("thumbnail_url"),
                button_text=telegram.get("button_text", "Open article"),
            ):
                delivered = True

    return JSONResponse(jsonable_encoder({"sent": delivered, "styles": rendered}))


@router.post("/push/subscribe")
async def subscribe_push_notifications(
    request: Request, payload: PushSubscriptionPayload
):
    user = require_request_user(request)

    if not _web_push_available():
        raise HTTPException(status_code=400, detail="Web push is not configured")

    conn = await database.get_db_connection()
    try:
        await conn.execute(
            """
            INSERT INTO user_push_subscriptions (user_id, endpoint, p256dh_key, auth_key, user_agent, updated_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (endpoint)
            DO UPDATE SET user_id = $1, p256dh_key = $3, auth_key = $4, user_agent = $5, updated_at = NOW()
            """,
            user["id"],
            payload.endpoint,
            payload.keys.p256dh,
            payload.keys.auth,
            request.headers.get("user-agent"),
        )
    finally:
        await database.release_db_connection(conn)

    return JSONResponse({"message": "Push subscription saved"})


@router.post("/push/unsubscribe")
async def unsubscribe_push_notifications(
    request: Request, payload: PushUnsubscribePayload
):
    user = require_request_user(request)
    conn = await database.get_db_connection()
    try:
        await conn.execute(
            "DELETE FROM user_push_subscriptions WHERE user_id = $1 AND endpoint = $2",
            user["id"],
            payload.endpoint,
        )
    finally:
        await database.release_db_connection(conn)

    return JSONResponse({"message": "Push subscription removed"})


@router.post("/push/test")
async def send_test_push_notification(request: Request):
    user = require_request_user(request)
    if not _web_push_available():
        raise HTTPException(status_code=400, detail="Web push is not configured")

    sent = await send_web_push_notification(
        user["id"],
        None,
        "newsy mobile alerts are on",
        "This is a test browser notification from your account.",
        build_app_link("/feeds"),
        tag="newsy-test",
    )
    if not sent:
        raise HTTPException(
            status_code=400,
            detail="No active browser subscription found for this user",
        )
    return JSONResponse({"message": "Test push sent"})
