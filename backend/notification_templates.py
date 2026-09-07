"""
Notification style templates.

Each compose_* function turns one notification event into per-channel
content: the in-app body, the web push body, and the data the Telegram
sender needs (article list, publish label, thumbnail, button). Pure
functions — no DB, no network — so formatting is fully unit-testable.

Telegram rendering goes through build_telegram_message, which is
fit-aware: it adds article links while they still fit Telegram's message
limits (4,096 chars for text, 1,024 for photo captions) and appends a
"+N more" marker for whatever did not fit, instead of a fixed top-N cap.
"""

from __future__ import annotations

import html
import re
from typing import Any, Optional

TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_CAPTION_LIMIT = 1024

IN_APP_BODY_LIMIT = 480  # DB write truncates at 500; leave marker headroom

PLACEHOLDER_THUMBNAIL_MARKERS = ("via.placeholder.com", "placehold.co", "placehold.it")

_TAG_PATTERN = re.compile(r"<[^>]+>")


def _single_line(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(text.replace("\r", "").split())


def _escape_telegram_html(text: Optional[str]) -> str:
    return html.escape(_single_line(text))


def _escape_telegram_html_multiline(text: Optional[str]) -> str:
    """Escape for Telegram HTML while keeping line breaks (bodies, excerpts)."""
    if not text:
        return ""
    return html.escape(text.replace("\r", ""))


def usable_thumbnail(url: Optional[str]) -> Optional[str]:
    if not url or not url.startswith(("http://", "https://")):
        return None
    if any(marker in url for marker in PLACEHOLDER_THUMBNAIL_MARKERS):
        return None
    return url


def telegram_html_to_plain(message: str) -> str:
    """Strip Telegram-HTML tags and unescape entities for the plain fallback."""
    return html.unescape(_TAG_PATTERN.sub("", message))


def build_telegram_message(
    title: str,
    body: Optional[str] = None,
    link: Optional[str] = None,
    *,
    articles: Optional[list[dict[str, Any]]] = None,
    footer: Optional[str] = None,
    published_label: Optional[str] = None,
    button_url: Optional[str] = None,
    button_text: str = "Open article",
    limit: int = TELEGRAM_MESSAGE_LIMIT,
) -> str:
    """
    Compose the Telegram-HTML message for a notification.

    Fit-aware: the article list grows entry by entry while the message fits
    `limit`; anything left over becomes a "+N more" line. The body paragraph
    is only used when there is no article list (batch lists replace it).
    """
    header = f"<b>{_escape_telegram_html(title)}</b>"
    published_section = f"<i>{_escape_telegram_html(published_label)}</i>"
    footer_section = f"<i>{_escape_telegram_html(footer)}</i>"

    link_section = ""
    if link and link.startswith(("http://", "https://")) and link != button_url:
        link_section = (
            f'<a href="{html.escape(link, quote=True)}">'
            f"{_escape_telegram_html(button_text)}</a>"
        )

    entries: list[str] = []
    if articles:
        for index, article in enumerate(articles, start=1):
            article_title = _escape_telegram_html(article.get("title"))
            article_link = article.get("link")
            if article_link and article_link.startswith(("http://", "https://")):
                entries.append(
                    f'{index}. <a href="{html.escape(article_link, quote=True)}">'
                    f"{article_title}</a>"
                )
            else:
                entries.append(f"{index}. {article_title}")

    body_section = (
        _escape_telegram_html_multiline(body) if body and not entries else ""
    )

    def assemble(list_text: str, body_text: Optional[str] = None) -> str:
        use_body = body_section if body_text is None else body_text
        parts = [header]
        if published_label:
            parts.append(published_section)
        if list_text:
            parts.append(list_text)
        if use_body:
            parts.append(use_body)
        if footer:
            parts.append(footer_section)
        if link_section:
            parts.append(link_section)
        return "\n\n".join(parts)

    if not entries:
        message = assemble("")
        if len(message) > limit and body_section:
            overhead = len(message) - len(body_section)
            budget = limit - overhead - 2
            if budget >= 40:
                return assemble("", f"{body_section[:budget].rstrip()}…")
        return message if len(message) <= limit else message[:limit]

    # Shrink the list until everything, including the "+N more" marker, fits.
    for shown in range(len(entries), 0, -1):
        list_text = "\n".join(entries[:shown])
        hidden = len(entries) - shown
        if hidden > 0:
            list_text += f"\n…+{hidden} more"
        message = assemble(list_text)
        if len(message) <= limit:
            return message

    # Even one entry did not fit alongside the header: drop the list.
    return assemble("")


def resolve_telegram_payload(
    title: str,
    body: Optional[str] = None,
    link: Optional[str] = None,
    *,
    articles: Optional[list[dict[str, Any]]] = None,
    footer: Optional[str] = None,
    published_label: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    button_text: str = "Open article",
) -> dict[str, Any]:
    """
    Decide the Telegram message format for a notification.

    Returns {"as_photo", "text", "thumbnail_url", "button_url"}. A photo is
    used only when a real thumbnail exists AND the full message fits a photo
    caption; otherwise the caller gets a text message. https links ride on an
    inline button (button_url); other links stay in the text.
    """
    button_url = link if link and link.startswith("https://") else None
    compose = dict(
        articles=articles,
        footer=footer,
        published_label=published_label,
        button_url=button_url,
        button_text=button_text,
    )

    text = build_telegram_message(title, body, link, **compose)

    thumbnail = usable_thumbnail(thumbnail_url)
    if thumbnail:
        caption = build_telegram_message(
            title, body, link, **compose, limit=TELEGRAM_CAPTION_LIMIT
        )
        if caption == text:
            return {
                "as_photo": True,
                "text": caption,
                "thumbnail_url": thumbnail,
                "button_url": button_url,
            }

    return {
        "as_photo": False,
        "text": text,
        "thumbnail_url": None,
        "button_url": button_url,
    }


def compose_batch_alert(
    source_name: str,
    articles: list[dict[str, Any]],
    app_link: Optional[str],
) -> dict[str, Any]:
    """
    batch_alert style: digest of the articles a feed poll just stored.

    `articles` items need title/link; published (formatted label),
    published_dt (datetime) and thumbnail are optional. When every article
    carries published_dt the list is sorted newest-first; otherwise the
    caller's order is kept.
    """
    if articles and all(a.get("published_dt") for a in articles):
        articles = sorted(
            articles, key=lambda a: a["published_dt"], reverse=True
        )

    count = len(articles)
    title = f"{source_name}: {count} new article{'s' if count != 1 else ''}"

    in_app_lines: list[str] = []
    for index, article in enumerate(articles, start=1):
        line = f"{index}. {_single_line(article.get('title'))[:200]}"
        candidate = "\n".join(in_app_lines + [line])
        remaining = count - index
        suffix = f"\n…+{remaining} more" if remaining > 0 else ""
        if len(candidate) + len(suffix) > IN_APP_BODY_LIMIT and in_app_lines:
            in_app_lines.append(f"…+{count - len(in_app_lines)} more")
            break
        in_app_lines.append(line)
    in_app_body = "\n".join(in_app_lines)

    newest = articles[0] if articles else {}
    thumbnail_url = next(
        (
            url
            for url in (a.get("thumbnail") for a in articles)
            if usable_thumbnail(url)
        ),
        None,
    )

    return {
        "kind": "batch_alert",
        "title": title,
        "body": in_app_body,
        "push_body": f"Latest: {_single_line(newest.get('title'))}",
        "telegram": {
            "articles": [
                {"title": a.get("title"), "link": a.get("link")}
                for a in articles[:25]
            ],
            "published_label": newest.get("published"),
            "thumbnail_url": thumbnail_url,
            "button_text": "Open in newsy",
        },
        "app_link": app_link,
    }


def compose_filter_match(
    title: str,
    filter_names: str,
    excerpt: str,
    source: str,
    link: Optional[str],
) -> dict[str, Any]:
    """
    filter_match style: a keyword/AI filter with auto-notify matched.
    Section breaks are real newlines so every channel can render them.
    """
    body = (
        f"Matched filters: {_single_line(filter_names)}\n\n"
        f"{(excerpt or '').replace(chr(13), '')}\n\n"
        f"Source: {_single_line(source)}"
    )
    return {
        "kind": "filter_match",
        "title": f"🎯 {_single_line(title)}",
        "body": body,
        "push_body": None,
        "telegram": {"button_text": "Read article"},
        "app_link": link,
    }


def compose_system_message(
    title: str, body: Optional[str], link: Optional[str]
) -> dict[str, Any]:
    """system style: connectivity checks and similar one-off messages."""
    return {
        "kind": "system",
        "title": _single_line(title),
        "body": body or "",
        "push_body": None,
        "telegram": {"button_text": "Open newsy"},
        "app_link": link,
    }


def build_sample_payloads(app_link: Optional[str]) -> dict[str, dict[str, Any]]:
    """
    Demo content for each style, used by the sample endpoint/button.

    The batch sample carries a working thumbnail and four short articles so
    it exercises the photo-caption path; swap in more articles to see the
    fit-aware text-message path.
    """
    batch = compose_batch_alert(
        "TechCrunch (sample)",
        [
            {
                "title": "Apple unveils the M5 MacBook Pro with OLED display",
                "link": "https://techcrunch.com/",
                "published": "Today at 09:14 PM (IST)",
                "published_dt": 4,
                "thumbnail": "https://picsum.photos/seed/newsy/800/400",
            },
            {
                "title": "Google ships Gemini 4 to Workspace users",
                "link": "https://techcrunch.com/",
                "published": "Today at 08:02 PM (IST)",
                "published_dt": 3,
            },
            {
                "title": "SpaceX delays the next Starship launch by a week",
                "link": "https://techcrunch.com/",
                "published": "Today at 07:45 PM (IST)",
                "published_dt": 2,
            },
            {
                "title": "Nvidia's Rubin roadmap: what we know so far",
                "link": "https://techcrunch.com/",
                "published": "Today at 06:30 PM (IST)",
                "published_dt": 1,
            },
        ],
        app_link,
    )
    batch["title"] = f"Sample alert: {batch['title']}"

    filter_match = compose_filter_match(
        "India's semiconductor mission crosses a milestone",
        "semiconductors, India policy",
        "This is a demo excerpt. Matched article content appears here with "
        "its formatting preserved, so longer excerpts stay readable.",
        "The Hindu (sample)",
        "https://www.thehindu.com/",
    )
    filter_match["title"] = f"Sample alert: {filter_match['title']}"

    system = compose_system_message(
        "Sample alert: newsy Telegram is connected",
        "This is how short system messages look.",
        app_link,
    )

    return {"batch_alert": batch, "filter_match": filter_match, "system": system}
