#!/usr/bin/env python3
"""Minimal Newsy external API client.

Features:
- fetches a recent article snapshot
- triggers on-demand extraction when full content is missing
- tails the SSE stream
- stores the last SSE cursor locally for resume support

Environment variables:
- NEWSY_BASE_URL=http://127.0.0.1:8765
- NEWSY_TOKEN=nsy_...
- NEWSY_STATE_FILE=.newsy_external_state.json
- NEWSY_CATEGORY=Markets            # optional
- NEWSY_FEED_URL=https://.../rss    # optional
- NEWSY_INCLUDE_NOTIFICATIONS=true  # optional
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = os.getenv("NEWSY_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
TOKEN = os.getenv("NEWSY_TOKEN")
STATE_FILE = os.getenv("NEWSY_STATE_FILE", ".newsy_external_state.json")
CATEGORY = os.getenv("NEWSY_CATEGORY")
FEED_URL = os.getenv("NEWSY_FEED_URL")
INCLUDE_NOTIFICATIONS = os.getenv("NEWSY_INCLUDE_NOTIFICATIONS", "true").lower() == "true"


def require_env() -> None:
    if not TOKEN:
        print("Set NEWSY_TOKEN before running this script.", file=sys.stderr)
        raise SystemExit(1)


def load_state() -> dict[str, Any]:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}
    except Exception as exc:
        print(f"Warning: failed to read state file: {exc}", file=sys.stderr)
        return {}


def save_state(state: dict[str, Any]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)


def build_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def api_request(path: str, *, method: str = "GET", data: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: int = 30) -> Any:
    payload = None
    req_headers = build_headers(headers)
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    request = Request(f"{BASE_URL}{path}", data=payload, headers=req_headers, method=method)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def build_article_query(limit: int = 10) -> str:
    query: dict[str, Any] = {"limit": limit, "include_content": "true"}
    if CATEGORY:
        query["category"] = CATEGORY
    if FEED_URL:
        query["feed_url"] = FEED_URL
    return urlencode(query)


def fetch_recent_articles(limit: int = 10) -> list[dict[str, Any]]:
    payload = api_request(f"/api/external/articles?{build_article_query(limit=limit)}")
    return payload.get("items", [])


def ensure_full_content(article: dict[str, Any]) -> dict[str, Any]:
    if article.get("has_full_content"):
        return article

    print(f"[extract] article {article['id']} missing full content, extracting on demand")
    try:
        payload = api_request(
            f"/api/external/articles/{article['id']}/extract",
            method="POST",
            data={"force_refresh": False},
        )
        return payload["item"]
    except HTTPError as exc:
        if exc.code == 422:
            print(
                f"[extract] article {article['id']} could not be extracted on demand; continuing with partial data"
            )
            return article
        raise


def print_article(article: dict[str, Any]) -> None:
    title = article.get("title", "<untitled>")
    content_len = len(article.get("content") or "")
    print(
        f"[article] id={article.get('id')} category={article.get('category')} full={article.get('has_full_content')} content_len={content_len} title={title}"
    )


def stream_events() -> None:
    state = load_state()
    last_event_id = state.get("last_event_id")

    query: dict[str, Any] = {"include_notifications": str(INCLUDE_NOTIFICATIONS).lower()}
    if CATEGORY:
        query["category"] = CATEGORY
    if FEED_URL:
        query["feed_url"] = FEED_URL

    path = f"/api/external/stream?{urlencode(query)}"
    headers = {"Accept": "text/event-stream"}
    if last_event_id:
        headers["Last-Event-ID"] = last_event_id

    request = Request(f"{BASE_URL}{path}", headers=build_headers(headers), method="GET")
    with urlopen(request, timeout=60) as response:
        event_id = None
        event_name = None
        data_lines: list[str] = []

        while True:
            raw_line = response.readline()
            if not raw_line:
                raise RuntimeError("SSE stream ended")

            line = raw_line.decode("utf-8").rstrip("\n")
            if not line:
                if data_lines:
                    payload = json.loads("\n".join(data_lines))
                    if event_id:
                        state["last_event_id"] = event_id
                        save_state(state)
                    handle_event(event_name, payload)
                event_id = None
                event_name = None
                data_lines = []
                continue

            if line.startswith("id: "):
                event_id = line[4:]
            elif line.startswith("event: "):
                event_name = line[7:]
            elif line.startswith("data: "):
                data_lines.append(line[6:])


def handle_event(event_name: str | None, payload: dict[str, Any]) -> None:
    if event_name == "ready":
        print(f"[stream] connected cursor={payload}")
        return

    if event_name == "heartbeat":
        print(f"[stream] heartbeat {payload.get('server_time')}")
        return

    if event_name == "stream.closed":
        raise RuntimeError(f"Stream closed by server: {payload}")

    if event_name == "article.created":
        print_article(payload)
        return

    if event_name == "notification.created":
        print(
            f"[notification] id={payload.get('id')} kind={payload.get('kind')} title={payload.get('title')}"
        )
        return

    print(f"[stream] {event_name}: {payload}")


def main() -> None:
    require_env()

    print(f"Connecting to {BASE_URL}")
    articles = fetch_recent_articles(limit=5)
    print(f"Fetched {len(articles)} recent articles")

    for article in articles:
        enriched = ensure_full_content(article)
        print_article(enriched)

    print("Opening SSE stream... press Ctrl+C to stop")
    while True:
        try:
            stream_events()
        except KeyboardInterrupt:
            raise
        except (HTTPError, URLError, RuntimeError) as exc:
            print(f"[stream] reconnecting after error: {exc}", file=sys.stderr)
            time.sleep(3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
