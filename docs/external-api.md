# Dedicated External API

The dedicated external API exposes your Newsy feeds to external applications over **read-only REST** and **SSE (Server-Sent Events)** using personal API tokens.

It is designed for integrations that need to:

- fetch categories, feeds, and articles
- request on-demand full article extraction when needed
- keep a local mirror of new items
- subscribe to near-real-time article and notification events
- avoid using browser session cookies outside the UI

---

## Purpose

Use the dedicated external API when you want an external system—such as a trading bot, analytics worker, alerting daemon, or dashboard—to read Newsy data safely with a scoped credential.

Key properties:

- separate endpoint family under `/api/external`
- authenticated with **Bearer API tokens**
- supports both:
  - **REST** for snapshots/backfills
  - **SSE** for incremental streaming
- intended for **read-mostly** consumers

---

## Enable it in the UI

In the web UI:

1. Open the sidebar/settings area.
2. Go to the **API** tab.
3. Find **Dedicated external API**.
4. Turn on:
   - **Dedicated external API**
   - optionally **Server-Sent Events**
5. Click **Save API settings**.

Notes:

- External clients cannot use the dedicated API until it is enabled.
- If SSE is disabled, REST still works, but `/api/external/stream` returns `403`.

---

## Generate API tokens

Generate tokens in the same **API** UI section.

Recommended practice:

- create **one token per external application**
- give each token a descriptive name, for example:
  - `trading-bot-prod`
  - `research-pipeline`
  - `market-alerts-staging`
- set an expiry when possible

Important:

- tokens are shown **only once** when created
- copy and store them immediately in your secret manager
- revoke unused tokens from the UI

Token prefix: `nsy_`

---

## Authentication

Use the token as a Bearer token:

```http
Authorization: Bearer nsy_...
```

Example:

```bash
curl -H "Authorization: Bearer $NEWSY_TOKEN" \
  "$NEWSY_BASE_URL/api/external/articles?limit=25"
```

### Auth rules

- API tokens can access **only** `/api/external/*`
- API tokens cannot manage other API tokens
- normal UI/session auth is still required to:
  - enable/disable the feature
  - create/revoke tokens
  - read token metadata in the settings UI

---

## Base URL

Use your public Newsy base URL plus the external API paths.

Example:

```text
https://newsy.example.com/api/external
```

If you want stable externally visible URLs in the UI, set `PUBLIC_URL` on the server.

---

## REST endpoints

## `GET /api/external/categories`

Returns category metadata and counts.

### Response shape

```json
{
  "items": [
    {
      "id": 1,
      "name": "Markets",
      "priority": 10,
      "is_default": false,
      "feed_count": 8,
      "article_count": 1240,
      "unread_count": 91
    }
  ]
}
```

---

## `GET /api/external/feeds`

Returns feeds with category and count metadata.

### Response shape

```json
{
  "items": [
    {
      "id": 12,
      "name": "Reuters Markets",
      "url": "https://example.com/rss",
      "is_active": true,
      "priority": 20,
      "retention_days": 30,
      "polling_interval": 300,
      "fetch_full_content": false,
      "article_count": 540,
      "unread_count": 21,
      "category": {
        "id": 1,
        "name": "Markets"
      }
    }
  ]
}
```

---

## `GET /api/external/articles`

Returns paginated articles.

### Query parameters

- `category` — filter by category name
- `feed_url` — filter by feed URL
- `q` — case-insensitive text search across title, description, content
- `since` — ISO 8601 timestamp
- `starred` — `true|false`
- `include_content` — `true|false`
- `limit` — `1..200`, default `50`
- `offset` — `>=0`, default `0`

### Response shape

```json
{
  "items": [
    {
      "id": 9876,
      "title": "Fed signals slower balance sheet runoff",
      "link": "https://example.com/article",
      "description": "Summary...",
      "thumbnail": null,
      "published": "Wed, 16 Apr 2026 10:32:00 GMT",
      "published_at": "2026-04-16T10:32:00+00:00",
      "category": "Markets",
      "source": "Reuters",
      "starred": false,
      "read": false,
      "has_full_content": true,
      "feed": {
        "id": 12,
        "name": "Reuters Markets",
        "url": "https://example.com/rss"
      }
    }
  ],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 1204,
    "has_more": true
  }
}
```

---

## `GET /api/external/articles/{article_id}`

Returns one article with full content.

### Response shape

```json
{
  "item": {
    "id": 9876,
    "title": "Fed signals slower balance sheet runoff",
    "link": "https://example.com/article",
    "description": "Summary...",
    "thumbnail": null,
    "published": "Wed, 16 Apr 2026 10:32:00 GMT",
    "published_at": "2026-04-16T10:32:00+00:00",
      "category": "Markets",
      "source": "Reuters",
      "starred": false,
      "read": false,
      "has_full_content": true,
      "feed": {
        "id": 12,
        "name": "Reuters Markets",
      "url": "https://example.com/rss"
    },
    "content": "<full article content>"
  }
}
```

### `has_full_content`

Use `has_full_content` to know whether Newsy already has extracted full article content stored for that item.

- `true` — full content is already available in `content`
- `false` — the article may only have summary or partial content, and you can call the on-demand extraction endpoint

---

## `POST /api/external/articles/{article_id}/extract`

Runs on-demand readability extraction for an existing article and stores the result back in Newsy.

This is useful when:

- `has_full_content` is `false`
- a trading system wants deeper analysis only for selected articles
- you want a fallback path instead of enabling full extraction for every feed

### Request body

```json
{
  "force_refresh": false
}
```

- `force_refresh=false` — return cached extracted content if already available
- `force_refresh=true` — re-fetch and re-extract even if content already exists

### Response shape

```json
{
  "item": {
    "id": 9876,
    "title": "Fed signals slower balance sheet runoff",
    "link": "https://example.com/article",
    "description": "Summary...",
    "thumbnail": null,
    "published": "Wed, 16 Apr 2026 10:32:00 GMT",
    "published_at": "2026-04-16T10:32:00+00:00",
    "category": "Markets",
    "source": "Reuters",
    "starred": false,
    "read": false,
    "has_full_content": true,
    "feed": {
      "id": 12,
      "name": "Reuters Markets",
      "url": "https://example.com/rss"
    },
    "content": "<full article content>"
  },
  "extraction": {
    "performed": true,
    "cached": false,
    "force_refresh": false
  }
}
```

If extraction fails, the endpoint returns `422`.

---

## SSE endpoint

## `GET /api/external/stream`

Streams incremental events as `text/event-stream`.

### Query parameters

- `category` — filter by category name
- `feed_url` — filter by feed URL
- `since` — ISO 8601 timestamp
- `include_notifications` — `true|false`, default `true`

### Resume support

The stream accepts the last cursor in either:

- `Last-Event-ID` header
- `last_event_id` query parameter

Cursor format:

```text
a{article_id}-n{notification_id}
```

Example:

```text
a12345-n678
```

---

## Example curl usage

For a ready-to-run Python integration example, see:

```text
examples/python_external_api_client.py
```

## Fetch categories

```bash
curl -sS \
  -H "Authorization: Bearer $NEWSY_TOKEN" \
  "$NEWSY_BASE_URL/api/external/categories"
```

## Fetch feeds

```bash
curl -sS \
  -H "Authorization: Bearer $NEWSY_TOKEN" \
  "$NEWSY_BASE_URL/api/external/feeds"
```

## Fetch latest 25 articles

```bash
curl -sS \
  -H "Authorization: Bearer $NEWSY_TOKEN" \
  "$NEWSY_BASE_URL/api/external/articles?limit=25"
```

## Fetch only one category since a timestamp

```bash
curl -sS \
  -H "Authorization: Bearer $NEWSY_TOKEN" \
  "$NEWSY_BASE_URL/api/external/articles?category=Markets&since=2026-04-16T00:00:00Z"
```

## Fetch starred articles with content

```bash
curl -sS \
  -H "Authorization: Bearer $NEWSY_TOKEN" \
  "$NEWSY_BASE_URL/api/external/articles?starred=true&include_content=true&limit=50"
```

## Fetch one article

```bash
curl -sS \
  -H "Authorization: Bearer $NEWSY_TOKEN" \
  "$NEWSY_BASE_URL/api/external/articles/9876"
```

## Extract full content on demand

```bash
curl -sS \
  -X POST \
  -H "Authorization: Bearer $NEWSY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"force_refresh":false}' \
  "$NEWSY_BASE_URL/api/external/articles/9876/extract"
```

## Open SSE stream

```bash
curl -N \
  -H "Authorization: Bearer $NEWSY_TOKEN" \
  "$NEWSY_BASE_URL/api/external/stream"
```

## Resume SSE stream from a saved cursor

```bash
curl -N \
  -H "Authorization: Bearer $NEWSY_TOKEN" \
  -H "Last-Event-ID: a12345-n678" \
  "$NEWSY_BASE_URL/api/external/stream"
```

---

## Event format

Each SSE event uses the standard fields:

```text
id: a12345-n678
event: article.created
data: {"id":12345,"title":"..."}
```

### Event types

#### `ready`

Sent immediately after connection.

Example:

```text
event: ready
data: {"connected_at":"2026-04-16T10:40:00+00:00","article_cursor":0,"notification_cursor":0}
```

#### `article.created`

Sent for each new matching article.

Payload matches the article list item shape.

#### `notification.created`

Sent for each new matching notification.

Example payload:

```json
{
  "id": 678,
  "channel": "telegram",
  "kind": "article_match",
  "title": "Alert title",
  "body": "Alert body",
  "link": "https://example.com/article",
  "article_id": 12345,
  "sent_at": "2026-04-16T10:41:12+00:00"
}
```

#### `heartbeat`

Sent periodically when no new items are emitted.

Example payload:

```json
{
  "connected": true,
  "server_time": "2026-04-16T10:41:15+00:00"
}
```

#### `stream.closed`

Sent before the server closes the stream.

Reasons include:

- `authentication_expired`
- `stream_disabled`

---

## Security notes

- Treat API tokens like passwords.
- Prefer **HTTPS only** for all external API traffic.
- Use **one token per consumer** so you can revoke access without affecting other systems.
- Set token expiry for non-permanent integrations.
- Rotate tokens on a schedule or after operator changes.
- Store tokens in a secret manager, not in source control.
- Copy tokens immediately after creation; they are not shown again.
- If a token is suspected to be leaked, revoke it and create a replacement.
- Disable the dedicated external API entirely when not needed.
- Disable SSE if your integration only needs periodic REST polling.

---

## Integration patterns for read-mostly trading systems

## 1) Snapshot + stream tail

Best default pattern.

1. Call `GET /api/external/articles` to backfill recent state.
2. Save the highest article/notification cursor you processed.
3. Open `/api/external/stream`.
4. On reconnect, send the saved `Last-Event-ID`.
5. If an important article has `has_full_content=false`, call `POST /api/external/articles/{article_id}/extract`.

Use this for:

- market news ingestion
- signal enrichment
- dashboard mirrors
- event-driven alerting

Why it works well:

- REST gives a reliable starting snapshot
- SSE gives low-latency incremental updates
- reconnect is simple and stateless

---

## 2) Category-partitioned consumers

Run one consumer per trading domain.

Examples:

- `Markets`
- `Macro`
- `Crypto`
- `Earnings`

Use:

- `category=...` on `/articles`
- `category=...` on `/stream`

Why it helps:

- isolates pipelines by strategy
- reduces downstream filtering cost
- simplifies queue ownership and alert routing

---

## 3) Feed-pinned low-noise ingestion

If only a few feeds are strategy-critical, filter by `feed_url`.

Use this for:

- premium wire feeds
- exchange notices
- central-bank or regulator feeds
- house-curated event feeds

Pattern:

- bootstrap with `GET /api/external/articles?feed_url=...`
- tail with `GET /api/external/stream?feed_url=...`

---

## 4) Local mirror cache

Maintain a local database keyed by `article.id`.

Recommended fields to persist:

- `id`
- `published_at`
- `category`
- `feed.url`
- `title`
- `link`
- `source`
- ingestion timestamp
- last seen stream cursor

Why this is useful:

- lets trading logic read from a local store
- avoids repeated full scans of the API
- makes replay and audit easier

---

## 5) Backfill after downtime

When your consumer restarts after an outage:

1. read your saved cursor
2. reconnect with `Last-Event-ID`
3. if needed, also run a REST catch-up using `since=<last_processed_timestamp>`

Use both cursor-based resume and time-based backfill for safer recovery.

---

## 6) Notification-aware execution filters

If your trading workflow already depends on Newsy notifications, keep `include_notifications=true` on the stream and route:

- `article.created` to ingestion/storage
- `notification.created` to execution or operator alert paths

This works well when notifications represent a more selective signal layer than raw articles.

---

## Recommended operational approach

For most read-mostly trading integrations:

- enable dedicated external API
- create a dedicated token per environment
- do an initial REST sync
- keep a long-lived SSE connection open
- persist the latest SSE cursor
- reconnect automatically with `Last-Event-ID`
- periodically reconcile with REST to detect missed data

This gives a simple, robust ingestion model with low latency and straightforward recovery.
