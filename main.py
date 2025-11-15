import os
import logging
import re
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import pytz
import json
from pathlib import Path

import feedparser
import httpx
import markdown2
import html2text
from readability import Document
from markdown_it import MarkdownIt

from dotenv import load_dotenv

from fastapi import FastAPI, Request, Form, HTTPException, File, UploadFile, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
import redis.asyncio as aioredis
from rapidfuzz import fuzz, process

import asyncpg
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
from datetime import datetime, timedelta
from rq import Queue
from redis import Redis

import logging
import asyncio
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import openai
import asyncio
from fastapi import FastAPI
import time
import unicodedata
import csv
import io
import subprocess
import xml.etree.ElementTree as ET
from typing import List
from pydantic import BaseModel

from config import Config  # Import our centralized config
import reports  # Import reports module
import backup_restore  # Import backup/restore/export module
import database  # Import database module
import ai_filter  # Import AI filtering module
import keyword_filter  # Import keyword/topic filtering module
import cache  # Import cache module
import internal_api  # Import internal API for Go scheduler
from youtube_embed import convert_links_to_embeds

load_dotenv()  # Load environment variables

# --- Global Configuration & Feed Variables ---
RSS_FEED_URLS = {
    "reddit": [
        {
            "name": "r/Indiaspeaks",
            "url": f"http://{Config.RSSBRIDGE_HOST}/?action=display&bridge=RedditBridge&context=single&r=IndiaSpeaks&f=&score=50&d=hot&search=&frontend=https%3A%2F%2Fold.reddit.com&format=Atom"
        },
        {
            "name": "worldnews",
            "url": f"http://{Config.RSSBRIDGE_HOST}/?action=display&bridge=RedditBridge&context=single&r=selfhosted&f=&score=&d=top&search=&frontend=https%3A%2F%2Fold.reddit.com&format=Atom"
        },
     ],
    "youtube": [
        {
            "name": "Prof K Nageshwar",
            "url": f"{Config.RSSBRIDGE_HOST}/?action=display&bridge=YoutubeBridge&context=By+channel+id&c=UCm40kSg56qfys19NtzgXAAg&duration_min=10&duration_max=&format=Atom"
        },
        {
            "name": "Prasadtech",
            "url": f"{Config.RSSBRIDGE_HOST}/?action=display&bridge=YoutubeBridge&context=By+channel+id&c=UCb-xXZ7ltTvrh9C6DgB9H-Q&duration_min=2&duration_max=&format=Atom"
        },
    ],
    "twitter": [
        {
            "name": "Twitter Feed",
            "url": "https://rss.xcancel.com/POTUS/rss"
        }
    ],
    "google": [
        {
            "name": "Google Trends",
            "url": "https://trends.google.com/trending/rss?geo=IN"
        }
    ]
}

# The feeds.json file is no longer the source of truth. The database is.
# The file is now only used to populate the database on the first run.




DEFAULT_THUMBNAIL = "/static/default-thumbnail.jpg"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
# Indian Standard Time
IST = pytz.timezone("Asia/Kolkata")

# --- FastAPI App & Templates ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")

# Include reports router
app.include_router(reports.router)

# Include backup/restore/export router
app.include_router(backup_restore.router)

# Include internal API router for Go scheduler
app.include_router(internal_api.router)


def truncate_words(text, max_words=100):
    if not text:
        return text
    words = text.split()
    if len(words) > max_words:
        return " ".join(words[:max_words]) + "..."
    return text

# Register the filter with your Jinja2Templates
templates.env.filters["truncate_words"] = truncate_words


# --- Database Setup ---
# Database functions moved to database.py module
get_db_connection = database.get_db_connection
init_db = database.init_db
ensure_aware = database.ensure_aware
get_feed_last_update = database.get_feed_last_update
update_feed_last_update = database.update_feed_last_update


# --- HTML Cleaning and Formatting Helper ---
def format_article_content(html_content: str) -> str:
    """
    Cleans, standardizes, and formats HTML content for consistent display.
    """
    try:
        # First, convert incoming HTML to Markdown to strip out proprietary classes,
        # styles, and other unnecessary tags.
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.ignore_images = False
        converter.body_width = 0  # No wrapping
        markdown_content = converter.handle(html_content)

        # Aggressively create paragraph breaks. Replace any sequence of one or more
        # newlines with a double newline. This ensures that the Markdown renderer
        # creates proper <p> tags.
        markdown_content_with_breaks = re.sub(r'\n+', '\n\n', markdown_content)

        # Now, convert the clean Markdown back to clean, semantic HTML using markdown2.
        clean_html = markdown2.markdown(markdown_content_with_breaks)
        
        return clean_html
    except Exception as e:
        logging.exception("Error formatting article content: %s", e)
        return f"<p>Error processing article content: {e}</p>"
    




NTFY_BASE_URL = os.environ["NTFY_BASE_URL"]



def sanitize_text(text):
    # Normalize the text (NFKD) and then encode/decode to strip out non-Latin-1 characters.
    normalized = unicodedata.normalize('NFKD', text)
    return normalized.encode('latin1', 'ignore').decode('latin1')


async def extract_article_content_with_readability(url: str) -> str:
    """
    Extract article content using readability-lxml.
    
    Args:
        url: Article URL to extract content from
        
    Returns:
        Cleaned HTML content or error message
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'},
                timeout=10.0,
                follow_redirects=True
            )
            response.raise_for_status()
        
        # Use readability to extract main content
        # Pass response.text (string) instead of response.content (bytes) to avoid regex errors
        doc = Document(response.text)
        # keep_all_images=True ensures all inline images in the main article body are preserved
        content_html = doc.summary(keep_all_images=True)
        
        if not content_html or content_html.strip() == "":
            return "<p>No content could be extracted.</p>"
        
        return content_html.strip()
        
    except httpx.TimeoutException:
        logging.error(f"Timeout extracting content from {url}")
        return "<p>Request timed out while fetching article.</p>"
    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP error {e.response.status_code} extracting content from {url}")
        return f"<p>Failed to fetch article (HTTP {e.response.status_code}).</p>"
    except Exception as e:
        logging.exception(f"Error extracting content with readability for {url}: {e}")
        return f"<p>Error extracting content: {str(e)}</p>"

async def send_ntfy_notification(title: str, link: str, description: str, category: str, source: str):
    # Check if ntfy is enabled for this category
    try:
        conn = await get_db_connection()
        ntfy_enabled = await conn.fetchval("SELECT ntfy_enabled FROM categories WHERE name = $1", category)
        await database.release_db_connection(conn)
        
        if ntfy_enabled is False:
            logging.debug(f"Ntfy notifications disabled for category: {category}")
            return
    except Exception as e:
        logging.warning(f"Could not check ntfy status for category {category}: {e}")
        # Continue with sending notification if we can't check status
    
    title = sanitize_text(title)
    topic = f"feeds-{category.lower().replace(' ', '-')}"
    ntfy_url = f"{NTFY_BASE_URL}/{topic}"

    headers = {
        "Title": title,
        "Click": link,
    }

    payload = f"{description[:160]}... (via {source})"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(ntfy_url, headers=headers, content=payload.encode('utf-8'))
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logging.exception("Failed to send notification: %s", e)




# ---- ntfy end ----- #


async def send_telegram_notification(title: str, link: str, description: str, category: str, source: str, thumbnail: str = None):
    """Send notification to Telegram for new articles."""
    # Check if telegram is enabled for this category and get chat_id
    try:
        conn = await get_db_connection()
        row = await conn.fetchrow(
            "SELECT telegram_enabled, telegram_chat_id FROM categories WHERE name = $1", 
            category
        )
        await database.release_db_connection(conn)
        
        if not row or row['telegram_enabled'] is False:
            logging.debug(f"Telegram notifications disabled for category: {category}")
            return
        
        chat_id = row['telegram_chat_id']
        if not chat_id:
            logging.debug(f"No Telegram chat ID configured for category: {category}")
            return
            
    except Exception as e:
        logging.warning(f"Could not check telegram status for category {category}: {e}")
        return
    
    # Get bot token from config
    from config import Config
    bot_token = Config.TELEGRAM_BOT_TOKEN
    
    if not bot_token:
        logging.warning("TELEGRAM_BOT_TOKEN not configured")
        return
    
    # Format the message with Markdown
    title = sanitize_text(title)
    description = sanitize_text(description)
    
    # Escape special characters for Telegram MarkdownV2
    def escape_markdown(text):
        """Escape special characters for Telegram MarkdownV2."""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    escaped_title = escape_markdown(title)
    escaped_description = escape_markdown(description[:300])  # Limit description length
    escaped_source = escape_markdown(source)
    escaped_link = link  # URLs don't need escaping in markdown links
    
    message = f"*{escaped_title}*\n\n{escaped_description}\n\n_via {escaped_source}_\n\n[Read Full Article]({escaped_link})"
    
    # Send the notification
    telegram_api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": False
    }
    
    # If thumbnail is available, send as photo with caption instead
    if thumbnail:
        telegram_api_url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": thumbnail,
            "caption": message,
            "parse_mode": "MarkdownV2"
        }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(telegram_api_url, json=payload)
            response.raise_for_status()
            logging.debug(f"Telegram notification sent for article: {title}")
    except httpx.HTTPStatusError as e:
        logging.error(f"Failed to send Telegram notification: {e.response.text}")
    except Exception as e:
        logging.error(f"Failed to send Telegram notification: {e}")


# ---- telegram end ----- #







def format_datetime(dt_string):
    try:
        dt = date_parser.parse(dt_string)
        dt = dt.astimezone(IST)
        now = datetime.now(IST)
        yesterday = now - timedelta(days=1)
        if dt.date() == now.date():
            return dt.strftime("Today at %I:%M %p")
        elif dt.date() == yesterday.date():
            return dt.strftime("Yesterday at %I:%M %p")
        else:
            return dt.strftime("%b %d, %Y - %I:%M %p")
    except Exception:
        return "No Date"


import time
from datetime import datetime, timedelta
import pytz
import logging
import httpx
import feedparser
from dateutil import parser as date_parser

# Indian Standard Time
IST = pytz.timezone("Asia/Kolkata")

def format_datetime(dt_input, source_name=None):
    """
    Intelligently format datetime while preserving source timezone context.
    
    Accepts either:
      • a timezone-aware datetime, or
      • a date-string parsable by dateutil
    
    Args:
      dt_input: datetime object or string
      source_name: optional source name to determine if timezone conversion is needed
    
    Returns:
      - "Today at HH:MM AM/PM (TZ)"
      - "Yesterday at HH:MM AM/PM (TZ)"
      - "Mon DD, YYYY - HH:MM AM/PM (TZ)"
      - or "No Date"
    """
    # datetime path
    if isinstance(dt_input, datetime):
        dt = dt_input if dt_input.tzinfo else IST.localize(dt_input)
    else:
        # string path
        try:
            dt = date_parser.parse(dt_input)
            # Preserve original timezone if present, otherwise assume IST
            dt = dt if dt.tzinfo else IST.localize(dt)
        except Exception:
            return "No Date"

    # Determine if source is Indian
    is_indian_source = False
    if source_name:
        indian_sources = {
            "Medianama", "Business Standard", "The Hindu", "Indian Express",
            "The Print", "Scroll.in", "Prof K Nageshwar", "Prasadtech"
        }
        is_indian_source = any(ind_src in source_name for ind_src in indian_sources)
    
    # Get current time in source's timezone for comparison
    if is_indian_source:
        # Indian sources: compare in IST
        now = datetime.now(IST)
        dt_display = dt.astimezone(IST) if dt.tzinfo else dt
    else:
        # International sources: compare in source timezone, but show IST offset
        now = datetime.now(IST)
        dt_display = dt.astimezone(IST) if dt.tzinfo else dt
    
    yesterday = now - timedelta(days=1)
    
    # Format with timezone indicator
    tz_abbr = dt_display.strftime("%Z")
    
    if dt_display.date() == now.date():
        return dt_display.strftime("Today at %I:%M %p") + f" ({tz_abbr})"
    elif dt_display.date() == yesterday.date():
        return dt_display.strftime("Yesterday at %I:%M %p") + f" ({tz_abbr})"
    else:
        return dt_display.strftime("%b %d, %Y - %I:%M %p") + f" ({tz_abbr})"


async def parse_and_store_rss_feed(feed_id: int, rss_url: str, category: str, source_name: str = "Unknown"):
    logging.debug("Parsing feed URL: %s for category: %s", rss_url, category)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(rss_url, headers={'User-Agent':'Mozilla/5.0'}, timeout=10)
            resp.raise_for_status()
        feed = feedparser.parse(resp.content)

        last_update = await get_feed_last_update(rss_url)
        # If it's the first fetch, go back 3 days, otherwise use the last update time.
        threshold = last_update if last_update else datetime.now(IST) - timedelta(days=3)
        new_last_update = last_update or threshold

        conn = await get_db_connection()

        for entry in feed.entries:
            title       = getattr(entry, "title", "Untitled")
            link        = getattr(entry, "link", "#")
            description = getattr(entry, "summary", "No description available.")

            thumbnail_url = DEFAULT_THUMBNAIL
            if "media_thumbnail" in entry:
                thumbnail_url = entry.media_thumbnail[0].get("url")
            elif "media_content" in entry:
                thumbnail_url = entry.media_content[0].get("url")

            raw_published = getattr(entry, "published", None) or getattr(entry, "updated", None)
            published_formatted = format_datetime(raw_published, source_name)

            struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
            if struct:
                dt_utc = datetime.fromtimestamp(time.mktime(struct), tz=pytz.utc)
                pub_dt = dt_utc.astimezone(IST)
            else:
                try:
                    pub_dt = date_parser.parse(raw_published) if raw_published else None
                    pub_dt = pub_dt if pub_dt and pub_dt.tzinfo else (IST.localize(pub_dt) if pub_dt else None)
                except Exception:
                    pub_dt = None

            if not pub_dt or pub_dt <= threshold:
                continue

            if pub_dt > new_last_update:
                new_last_update = pub_dt

            if await conn.fetchval('SELECT id FROM articles WHERE link = $1', link):
                continue

            try:
                article_content = await extract_article_content_with_readability(link)
            except Exception:
                logging.exception("Error extracting content for %s", link)
                article_content = None

            # Insert article and get its ID
            article_id = await conn.fetchval(
                'INSERT INTO articles '
                '(title, link, description, thumbnail, published, published_datetime, category, content, source, feed_id, feed_url) '
                'VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) '
                'RETURNING id',
                title, link, description, thumbnail_url,
                 published_formatted, pub_dt, category, article_content, source_name, feed_id, rss_url
            )

            # Process with AI filter if enabled for this category (only for NEW articles)
            try:
                await ai_filter.process_new_article(article_id, category, conn)
            except Exception as e:
                logging.warning(f"AI filter processing failed for article {article_id}: {e}")
            
            # Process with keyword/topic filters (auto-star and notify if matched)
            try:
                await keyword_filter.process_article_filters(
                    article_id, title, link, description, article_content, 
                    category, source_name, conn
                )
            except Exception as e:
                logging.warning(f"Keyword filter processing failed for article {article_id}: {e}")

            await send_ntfy_notification(title, link, description, category, source_name)
            await send_telegram_notification(title, link, description, category, source_name, thumbnail_url)

        await database.release_db_connection(conn)

        if new_last_update > threshold:
            await update_feed_last_update(rss_url, new_last_update)
            logging.info("Updated feed state for %s → %s", rss_url, new_last_update)
            
            # Invalidate feed caches after new articles are added
            cache.invalidate_feeds_cache()

    except Exception as e:
        logging.exception("Error parsing/storing feed for URL: %s | Error: %s", rss_url, e)


async def parse_and_store_rss_feed_initial(feed_id: int, rss_url: str, category: str, source_name: str = "Unknown"):
    """
    Initial synchronous feed fetch - stores only basic article data (no full-text extraction).
    This is fast and provides immediate feedback when adding a new feed.
    """
    logging.debug("Initial parsing of feed URL: %s for category: %s", rss_url, category)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(rss_url, headers={'User-Agent':'Mozilla/5.0'}, timeout=10)
            resp.raise_for_status()
        feed = feedparser.parse(resp.content)

        # For initial fetch, go back 10 days
        threshold = datetime.now(IST) - timedelta(days=10)
        new_last_update = threshold

        conn = await get_db_connection()
        articles_added = 0

        try:
            for entry in feed.entries:
                title       = getattr(entry, "title", "Untitled")
                link        = getattr(entry, "link", "#")
                description = getattr(entry, "summary", "No description available.")

                thumbnail_url = DEFAULT_THUMBNAIL
                if "media_thumbnail" in entry:
                    thumbnail_url = entry.media_thumbnail[0].get("url")
                elif "media_content" in entry:
                    thumbnail_url = entry.media_content[0].get("url")

                raw_published = getattr(entry, "published", None) or getattr(entry, "updated", None)
                published_formatted = format_datetime(raw_published, source_name)

                struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
                if struct:
                    dt_utc = datetime.fromtimestamp(time.mktime(struct), tz=pytz.utc)
                    pub_dt = dt_utc.astimezone(IST)
                else:
                    try:
                        pub_dt = date_parser.parse(raw_published) if raw_published else None
                        pub_dt = pub_dt if pub_dt and pub_dt.tzinfo else (IST.localize(pub_dt) if pub_dt else None)
                    except Exception:
                        pub_dt = None

                if not pub_dt or pub_dt <= threshold:
                    continue

                if pub_dt > new_last_update:
                    new_last_update = pub_dt

                if await conn.fetchval('SELECT id FROM articles WHERE link = $1', link):
                    continue

                # NO FULL-TEXT EXTRACTION - just store the summary from the feed
                article_content = None

                # Insert article and get its ID
                article_id = await conn.fetchval(
                    'INSERT INTO articles '
                    '(title, link, description, thumbnail, published, published_datetime, category, content, source, feed_id, feed_url) '
                    'VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) '
                    'RETURNING id',
                    title, link, description, thumbnail_url,
                     published_formatted, pub_dt, category, article_content, source_name, feed_id, rss_url
                )
                articles_added += 1

                # Process with AI filter if enabled for this category (only for NEW articles)
                try:
                    await ai_filter.process_new_article(article_id, category, conn)
                except Exception as e:
                    logging.warning(f"AI filter processing failed for article {article_id}: {e}")
                
                # Process with keyword/topic filters (auto-star and notify if matched)
                try:
                    await keyword_filter.process_article_filters(
                        article_id, title, link, description, article_content, 
                        category, source_name, conn
                    )
                except Exception as e:
                    logging.warning(f"Keyword filter processing failed for article {article_id}: {e}")

                # Note: Notifications are NOT sent during initial fetch to avoid spam
                # They will be sent by the worker during subsequent updates

        finally:
            await database.release_db_connection(conn)

        if new_last_update > threshold:
            await update_feed_last_update(rss_url, new_last_update)
            logging.info("Updated feed state for %s → %s", rss_url, new_last_update)
            
            # Invalidate feed caches after new articles are added
            cache.invalidate_feeds_cache()

        logging.info(f"Initial fetch completed for {source_name}: {articles_added} articles added")
        return articles_added

    except Exception as e:
        logging.exception("Error in initial fetch for URL: %s | Error: %s", rss_url, e)
        raise


async def fetch_single_feed(feed_id: int, name: str, url: str, category: str):
    """Fetch a single feed by its ID"""
    start_time = datetime.now(IST)
    logging.info("Feed update started for '%s' at %s", name, start_time)
    
    try:
        await parse_and_store_rss_feed(feed_id, url, category, source_name=name)
    except Exception as e:
        logging.error(f"Error fetching feed '{name}': {e}")
    finally:
        end_time = datetime.now(IST)
        logging.info("Feed update completed for '%s' at %s", name, end_time)


async def fetch_all_feeds_db():
    """Fetch all active feeds (used for initial startup)"""
    start_time = datetime.now(IST)
    logging.info("Feed update started at %s", start_time)
    
    conn = await get_db_connection()
    
    try:
        active_feeds = await conn.fetch('SELECT id, name, url, category FROM feeds WHERE "isActive" = true')
        
        tasks = []
        for feed in active_feeds:
            feed_id, name, url, category = feed['id'], feed['name'], feed['url'], feed['category']
            logging.info("Processing feed: '%s' for category: '%s'", name, category)
            tasks.append(parse_and_store_rss_feed(feed_id, url, category, source_name=name))
        
        await asyncio.gather(*tasks)
    
    finally:
        await database.release_db_connection(conn)
        end_time = datetime.now(IST)
        logging.info("Feed update completed at %s", end_time)


# ===== OLD SCHEDULING FUNCTIONS (DEPRECATED - Kept for reference/rollback) =====
# async def schedule_all_feeds():
#     """Schedule individual jobs for each active feed based on their polling_interval"""
#     conn = await get_db_connection()
#     
#     try:
#         active_feeds = await conn.fetch('SELECT id, name, url, category, polling_interval FROM feeds WHERE "isActive" = true')
#         
#         for feed in active_feeds:
#             feed_id = feed['id']
#             name = feed['name']
#             url = feed['url']
#             category = feed['category']
#             polling_interval = feed['polling_interval'] or 1  # Default to 1 minute if None
#             
#             # Create unique job ID for this feed
#             job_id = f"feed_{feed_id}"
#             
#             # Remove existing job if it exists
#             if scheduler.get_job(job_id):
#                 scheduler.remove_job(job_id)
#             
#             # Schedule the feed with its custom interval
#             scheduler.add_job(
#                 fetch_single_feed,
#                 'interval',
#                 minutes=polling_interval,
#                 args=[feed_id, name, url, category],
#                 id=job_id,
#                 max_instances=1,
#                 coalesce=True,
#                 misfire_grace_time=300
#             )
#             
#             logging.info(f"Scheduled feed '{name}' (ID: {feed_id}) with {polling_interval} minute interval")
#     
#     finally:
#         await database.release_db_connection(conn)


async def get_total_articles_count(category: str = None, days: int = 2, starred_only: bool = False, search_query: str = None, feed_url: str = None):
    """Get total count of articles for pagination"""
    threshold = datetime.now(IST) - timedelta(days=days)
    conn = await get_db_connection()
    
    try:
        if search_query:
            # For search, we need to count search results
            # This is a simplified count - actual search might be more complex
            query = """
                SELECT COUNT(*) as total
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE a.published_datetime >= $1
                AND f."isActive" = true
                AND (a.title ILIKE $2 OR a.description ILIKE $2 OR a.content ILIKE $2)
            """
            params = [threshold, f"%{search_query}%"]
            
            if category:
                query = query.replace("AND (a.title", "AND a.category = $3 AND (a.title")
                params.append(category)
            
            if feed_url:
                query += f" AND f.url = ${len(params) + 1}"
                params.append(feed_url)
                
            if starred_only:
                query += " AND a.starred = true"
        else:
            # Standard count
            query = """
                SELECT COUNT(*) as total
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE a.published_datetime >= $1
                AND f."isActive" = true
            """
            params = [threshold]
            
            if category:
                query += " AND a.category = $2"
                params.append(category)
            
            if feed_url:
                query += f" AND f.url = ${len(params) + 1}"
                params.append(feed_url)
                
            if starred_only:
                query += " AND a.starred = true"
        
        result = await conn.fetchrow(query, *params)
        return result['total'] if result else 0
    finally:
        await database.release_db_connection(conn)


async def get_user_timezone():
    """Get user's preferred timezone from settings."""
    conn = await get_db_connection()
    timezone_str = await conn.fetchval("SELECT value FROM user_settings WHERE key = 'timezone'")
    await database.release_db_connection(conn)
    return pytz.timezone(timezone_str) if timezone_str else IST

async def convert_article_timezone(article: dict, target_tz):
    """Convert article's published datetime to target timezone and update published string."""
    if article.get('published_datetime'):
        try:
            # Parse the datetime (should be in UTC from database)
            pub_dt = datetime.fromisoformat(article['published_datetime'].replace('Z', '+00:00'))
            
            # Convert to target timezone
            pub_dt_converted = pub_dt.astimezone(target_tz)
            
            # Update the published_datetime ISO string
            article['published_datetime'] = pub_dt_converted.isoformat()
            
            # Update the human-readable published string
            now = datetime.now(target_tz)
            yesterday = now - timedelta(days=1)
            tz_abbr = pub_dt_converted.strftime("%Z")
            
            if pub_dt_converted.date() == now.date():
                article['published'] = pub_dt_converted.strftime("Today at %I:%M %p") + f" ({tz_abbr})"
            elif pub_dt_converted.date() == yesterday.date():
                article['published'] = pub_dt_converted.strftime("Yesterday at %I:%M %p") + f" ({tz_abbr})"
            else:
                article['published'] = pub_dt_converted.strftime("%b %d, %Y - %I:%M %p") + f" ({tz_abbr})"
        except Exception as e:
            logging.warning(f"Error converting timezone for article: {e}")
    
    return article

async def get_articles_for_category_db(category: str, days: int = 2, starred_only: bool = False, limit: int = None, offset: int = None, target_tz=None, view: str = "standard"):
     threshold = datetime.now(IST) - timedelta(days=days)
     conn = await get_db_connection()
     
     # Base query depends on view type
     if view == "ai":
         # AI view: only show articles that passed AI filter
         query = """
             SELECT a.title, a.link, a.description, a.thumbnail, a.published, a.published_datetime, a.category, a.content, a.source, a.starred 
             FROM articles a
             JOIN feeds f ON a.feed_id = f.id
             JOIN article_ai_matches aam ON a.id = aam.article_id
             JOIN categories c ON c.name = a.category
             WHERE a.category = $1 
             AND a.published_datetime >= $2
             AND f."isActive" = true
             AND aam.category_id = c.id
         """
     else:
         # Standard view: show all articles
         query = """
             SELECT a.title, a.link, a.description, a.thumbnail, a.published, a.published_datetime, a.category, a.content, a.source, a.starred 
             FROM articles a
             JOIN feeds f ON a.feed_id = f.id
             WHERE a.category = $1 
             AND a.published_datetime >= $2
             AND f."isActive" = true
         """
     
     params = [category, threshold]
     
     if starred_only:
         query += " AND a.starred = true"
     
     query += " ORDER BY a.published_datetime DESC"
     
     # Add pagination if limit is provided
     if limit is not None:
         query += f" LIMIT ${len(params) + 1}"
         params.append(limit)
         
         if offset is not None:
             query += f" OFFSET ${len(params) + 1}"
             params.append(offset)
     
     rows = await conn.fetch(query, *params)
     
     articles = []
     for row in rows:
         pub_dt = row['published_datetime']
         pub_dt_str = pub_dt.isoformat() if pub_dt else None
         
         article = {
             "title": row['title'],
             "link": row['link'],
             "description": row['description'],
             "thumbnail": row['thumbnail'],
             "published": row['published'],
             "published_datetime": pub_dt_str,
             "category": row['category'],
             "content": row['content'],
             "source": row['source'] or "Unknown",
             "starred": row['starred']
         }
         
         # Convert timezone if target_tz is provided
         if target_tz:
             article = await convert_article_timezone(article, target_tz)
         
         articles.append(article)
     await database.release_db_connection(conn)
     return articles


async def get_all_articles_paginated(days: int = 2, starred_only: bool = False, limit: int = 100, offset: int = 0, category: str = None, feed_url: str = None, target_tz=None, view: str = "standard"):
    """Get articles across all categories with pagination"""
    threshold = datetime.now(IST) - timedelta(days=days)
    conn = await get_db_connection()
    
    try:
        # Base query depends on view type
        if view == "ai" and category:
            # AI view: only show articles that passed AI filter
            query = """
                SELECT a.title, a.link, a.description, a.thumbnail, a.published, a.published_datetime, a.category, a.content, a.source, a.starred 
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                JOIN article_ai_matches aam ON a.id = aam.article_id
                JOIN categories c ON c.name = a.category
                WHERE a.published_datetime >= $1
                AND f."isActive" = true
                AND aam.category_id = c.id
            """
        else:
            # Standard view: show all articles
            query = """
                SELECT a.title, a.link, a.description, a.thumbnail, a.published, a.published_datetime, a.category, a.content, a.source, a.starred 
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE a.published_datetime >= $1
                AND f."isActive" = true
            """
        
        params = [threshold]
        
        if category:
            query += " AND a.category = $2"
            params.append(category)
        
        if feed_url:
            query += f" AND f.url = ${len(params) + 1}"
            params.append(feed_url)
        
        if starred_only:
            query += f" AND a.starred = true"
        
        query += " ORDER BY a.published_datetime DESC"
        query += f" LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}"
        params.extend([limit, offset])
        
        rows = await conn.fetch(query, *params)
        
        articles = []
        for row in rows:
            pub_dt = row['published_datetime']
            pub_dt_str = pub_dt.isoformat() if pub_dt else None
            
            article = {
                "title": row['title'],
                "link": row['link'],
                "description": row['description'],
                "thumbnail": row['thumbnail'],
                "published": row['published'],
                "published_datetime": pub_dt_str,
                "category": row['category'],
                "content": row['content'],
                "source": row['source'] or "Unknown",
                "starred": row['starred']
            }
            
            # Convert timezone if target_tz is provided
            if target_tz:
                article = await convert_article_timezone(article, target_tz)
            
            articles.append(article)
        
        return articles
    finally:
        await database.release_db_connection(conn)


async def cleanup_old_articles():
    """
    Clean up old articles based on the retention policy of each feed.
    """
    logging.info("Starting scheduled cleanup of old articles.")
    conn = await get_db_connection()
    try:
        feeds = await conn.fetch('SELECT id, retention_days FROM feeds')
        
        for feed in feeds:
            retention_days = feed['retention_days'] if feed['retention_days'] is not None else Config.DEFAULT_ARTICLE_RETENTION_DAYS
            
            if retention_days > 0:  # A value of 0 or less could mean 'keep forever'
                cutoff_date = datetime.now(IST) - timedelta(days=retention_days)
                
                result = await conn.execute(
                    'DELETE FROM articles WHERE feed_id = $1 AND published_datetime < $2',
                    feed['id'], cutoff_date
                )
                deleted_count = int(result.split(' ')[1])
                if deleted_count > 0:
                    logging.info(f"Deleted {deleted_count} old articles for feed ID {feed['id']} (older than {retention_days} days).")

    except Exception as e:
        logging.exception("Error during scheduled article cleanup: %s", e)
    finally:
        await database.release_db_connection(conn)
        logging.info("Finished scheduled cleanup of old articles.")


async def enqueue_due_feeds():
    """
    Batch scheduler job: Query for feeds due for refresh and enqueue them to Redis queue.
    This replaces the per-feed scheduling approach with a scalable batch model.
    Runs every 1 minute.
    """
    global feed_queue
    
    if not feed_queue:
        logging.warning("Feed queue not initialized, skipping enqueue")
        return
    
    try:
        logging.debug("Checking for due feeds...")
        conn = await database.get_db_connection()
        
        # Query for feeds that are due for refresh
        due_feeds = await conn.fetch("""
            SELECT id, name, url, category, polling_interval, etag_header, last_modified_header, fetch_full_content
            FROM feeds
            WHERE "isActive" = true 
            AND next_check_at <= NOW()
            ORDER BY next_check_at ASC
            LIMIT 100
        """)
        
        if not due_feeds:
            logging.debug("No feeds due for refresh")
            await database.release_db_connection(conn)
            return
        
        logging.info(f"Found {len(due_feeds)} feeds due for refresh")
        
        # Import worker function
        from worker import process_feed_job
        
        # Enqueue each due feed
        for feed in due_feeds:
            feed_id = feed['id']
            name = feed['name']
            url = feed['url']
            category = feed['category']
            polling_interval = feed['polling_interval'] or 60
            etag = feed['etag_header']
            last_modified = feed['last_modified_header']
            fetch_full_content = feed['fetch_full_content'] or False
            
            # Enqueue job to Redis
            job = feed_queue.enqueue(
                process_feed_job,
                feed_id=feed_id,
                name=name,
                url=url,
                category=category,
                polling_interval=polling_interval,
                etag=etag,
                last_modified=last_modified,
                fetch_full_content=fetch_full_content,
                job_timeout='10m',  # 10 minute timeout per feed
                job_id=f"feed_{feed_id}_{int(datetime.now().timestamp())}",  # Unique job ID
                failure_ttl=86400  # Keep failed jobs for 24 hours
            )
            
            # Immediately update next_check_at to prevent duplicate queueing
            next_check = datetime.now(IST) + timedelta(minutes=polling_interval)
            await conn.execute(
                "UPDATE feeds SET next_check_at = $1 WHERE id = $2",
                next_check, feed_id
            )
            
            logging.debug(f"Enqueued feed {name} (ID: {feed_id}), job ID: {job.id}")
        
        await database.release_db_connection(conn)
        logging.info(f"Successfully enqueued {len(due_feeds)} feeds")
        
    except Exception as e:
        logging.exception(f"Error in enqueue_due_feeds: {e}")


scheduler = AsyncIOScheduler(timezone=IST)

# Global Redis client for search index
redis_client = None

# RQ Redis connection and queue for feed processing
rq_redis = None
feed_queue = None

@app.on_event("startup")
async def startup_event():
    global redis_client, rq_redis, feed_queue
    
    # Initialize Redis client for caching
    redis_client = aioredis.from_url(
        f"redis://{Config.REDIS_HOST}:{Config.REDIS_PORT}/{Config.REDIS_DB}",
        encoding="utf-8",
        decode_responses=True
    )
    
    # Initialize FastAPI Cache with Redis backend
    FastAPICache.init(RedisBackend(redis_client), prefix="fastapi-cache")
    
    # Initialize RQ Redis connection for job queue
    rq_redis = Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        db=Config.REDIS_DB,
        decode_responses=False  # RQ handles encoding
    )
    feed_queue = Queue('feed-queue', connection=rq_redis)
    logging.info(f"RQ feed queue initialized: {len(feed_queue)} jobs pending")
    
    # Initialize database connection pool
    await database.init_db_pool()
    await init_db()
    
    # Initialize reports database
    await reports.init_reports_db()
    
    # Build initial search index
    asyncio.create_task(build_search_index())
    
    # ===== DISABLED: Go scheduler now handles feed enqueuing =====
    # Single batch scheduler job runs every minute to enqueue due feeds
    # scheduler.add_job(enqueue_due_feeds, 'interval', minutes=1, id='batch_feed_scheduler')
    # logging.info("Batch feed scheduler initialized (runs every 1 minute)")
    # asyncio.create_task(enqueue_due_feeds())  # Trigger initial feed enqueue
    logging.info("Feed scheduling is now handled by Go scheduler service")
    
    # Other scheduled jobs (kept in Python)
    scheduler.add_job(cleanup_old_articles, 'cron', hour=0)  # Run daily at midnight
    scheduler.add_job(build_search_index, 'interval', minutes=5)  # Update search index every 5 minutes
    scheduler.start()
    
    # Load and schedule reports
    await reports.load_and_schedule_reports(scheduler)

@app.on_event("shutdown")
async def shutdown_event():
    global redis_client, rq_redis
    if redis_client:
        await redis_client.close()
    if rq_redis:
        rq_redis.close()
    # Close database pool
    await database.close_db_pool()


# --- Queue Monitoring Endpoint ---
@app.get("/api/queue/status")
async def get_queue_status():
    """Monitor RQ job queue status for debugging and health checks."""
    global feed_queue
    
    if not feed_queue:
        return JSONResponse(
            status_code=503,
            content={"error": "Queue not initialized"}
        )
    
    try:
        from rq import Worker
        from rq.registry import (
            StartedJobRegistry,
            FinishedJobRegistry, 
            FailedJobRegistry,
            ScheduledJobRegistry
        )
        
        # Get queue stats
        queued_count = len(feed_queue)
        
        # Get worker count
        workers = Worker.all(connection=rq_redis)
        # Filter for active workers (check state instead of stopped attribute)
        active_workers = [w for w in workers if w.state in ['busy', 'idle']]
        
        # Get job registries
        started_registry = StartedJobRegistry('feed-queue', connection=rq_redis)
        finished_registry = FinishedJobRegistry('feed-queue', connection=rq_redis)
        failed_registry = FailedJobRegistry('feed-queue', connection=rq_redis)
        scheduled_registry = ScheduledJobRegistry('feed-queue', connection=rq_redis)
        
        # Get next feeds due for refresh
        conn = await database.get_db_connection()
        next_due_feeds = await conn.fetch("""
            SELECT id, name, next_check_at
            FROM feeds
            WHERE "isActive" = true AND next_check_at <= NOW() + INTERVAL '5 minutes'
            ORDER BY next_check_at ASC
            LIMIT 10
        """)
        await database.release_db_connection(conn)
        
        return {
            "queue": {
                "queued_jobs": queued_count,
                "started_jobs": len(started_registry),
                "finished_jobs": len(finished_registry),
                "failed_jobs": len(failed_registry),
                "scheduled_jobs": len(scheduled_registry)
            },
            "workers": {
                "total": len(workers),
                "active": len(active_workers),
                "worker_names": [w.name for w in active_workers]
            },
            "next_due_feeds": [
                {
                    "id": f['id'],
                    "name": f['name'],
                    "next_check_at": f['next_check_at'].isoformat() if f['next_check_at'] else None
                }
                for f in next_due_feeds
            ],
            "status": "healthy" if len(active_workers) > 0 else "warning"
        }
        
    except Exception as e:
        logging.exception(f"Error getting queue status: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# --- Search Index Functions ---
async def build_search_index():
    """
    Build a search index from all articles in the database and store in Redis.
    This runs as a background task after feed updates.
    """
    global redis_client
    if not redis_client:
        logging.warning("Redis client not initialized, skipping search index build")
        return
    
    try:
        logging.info("Building search index...")
        conn = await get_db_connection()
        
        # Fetch all recent articles (last 30 days by default)
        threshold = datetime.now(IST) - timedelta(days=Config.DEFAULT_ARTICLE_RETENTION_DAYS)
        articles = await conn.fetch("""
            SELECT a.id, a.title, a.description, a.category, a.source, a.link, 
                   a.thumbnail, a.published, a.published_datetime, a.starred
            FROM articles a
            JOIN feeds f ON a.feed_id = f.id
            WHERE a.published_datetime >= $1 AND f."isActive" = true
            ORDER BY a.published_datetime DESC
        """, threshold)
        
        # Build search index
        search_index = {}
        for article in articles:
            article_id = str(article['id'])
            search_index[article_id] = {
                'id': article_id,
                'title': article['title'] or '',
                'description': article['description'] or '',
                'category': article['category'] or '',
                'source': article['source'] or '',
                'link': article['link'] or '',
                'thumbnail': article['thumbnail'] or '',
                'published': article['published'] or '',
                'published_datetime': article['published_datetime'].isoformat() if article['published_datetime'] else None,
                'starred': article['starred'],
                # Combined searchable text for fuzzy matching
                'searchable_text': f"{article['title']} {article['description']} {article['source']}".lower()
            }
        
        # Store in Redis
        await redis_client.set('search_index', json.dumps(search_index))
        logging.info(f"Search index built successfully with {len(search_index)} articles")
        
        await database.release_db_connection(conn)
    except Exception as e:
        logging.exception(f"Error building search index: {e}")


async def search_articles(
    query: str,
    category: str = None,
    score_threshold: float = None
) -> list:
    """
    Search articles using fuzzy matching with rapidfuzz.
    
    Args:
        query: Search query string
        category: Optional category filter
        score_threshold: Minimum fuzzy match score (default from config)
    
    Returns:
        List of matching articles sorted by relevance
    """
    global redis_client
    if not redis_client:
        logging.warning("Redis client not initialized")
        return []
    
    if score_threshold is None:
        score_threshold = Config.SEARCH_SCORE_THRESHOLD
    
    try:
        # Fetch search index from Redis
        index_json = await redis_client.get('search_index')
        if not index_json:
            logging.warning("Search index not found in Redis, building now...")
            await build_search_index()
            index_json = await redis_client.get('search_index')
            if not index_json:
                return []
        
        search_index = json.loads(index_json)
        
        # Apply category filter if provided
        if category:
            search_index = {
                k: v for k, v in search_index.items() 
                if v['category'].lower() == category.lower()
            }
        
        # Perform fuzzy search
        query_lower = query.lower()
        candidates = {
            article_id: article['searchable_text'] 
            for article_id, article in search_index.items()
        }
        
        # Use rapidfuzz to find best matches
        results = process.extract(
            query_lower,
            candidates,
            scorer=fuzz.WRatio,
            limit=100,
            score_cutoff=score_threshold
        )
        
        # Build result list with article details
        matched_articles = []
        for text, score, article_id in results:
            article = search_index[article_id]
            matched_articles.append({
                'title': article['title'],
                'link': article['link'],
                'description': article['description'],
                'thumbnail': article['thumbnail'],
                'published': article['published'],
                'published_datetime': article['published_datetime'],
                'category': article['category'],
                'source': article['source'],
                'starred': article['starred'],
                'search_score': round(score, 2)
            })
        
        logging.info(f"Search for '{query}' returned {len(matched_articles)} results")
        return matched_articles
    
    except Exception as e:
        logging.exception(f"Error searching articles: {e}")
        return []


async def parse_rss_feed(rss_url: str, source_name: str = "Unknown"):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    async with httpx.AsyncClient() as client:
        response = await client.get(rss_url, headers=headers, timeout=10)
        response.raise_for_status()
    feed = feedparser.parse(response.content)
    items = []
    for entry in feed.entries:
        title = getattr(entry, "title", "Untitled")
        link = getattr(entry, "link", "#")
        description = getattr(entry, "summary", "No description available.")
        thumbnail_url = None
        if "media_thumbnail" in entry:
            thumbnail_url = entry.media_thumbnail[0].get("url")
        elif "media_content" in entry:
            thumbnail_url = entry.media_content[0].get("url")
        if not thumbnail_url and "<img" in description:
            start = description.find("<img")
            src_start = description.find('src="', start) + 5
            src_end = description.find('"', src_start)
            if src_start > 4 and src_end > src_start:
                thumbnail_url = description[src_start:src_end]
        if not thumbnail_url:
            thumbnail_url = DEFAULT_THUMBNAIL
        raw_published = getattr(entry, "published", "No date")
        published = format_datetime(raw_published, source_name)
        items.append({
            "title": title,
            "link": link,
            "description": description,
            "thumbnail": thumbnail_url,
            "published": published
        })
    return items

@app.get("/api/feeds/config")
async def get_feeds_config():
    """Get the current feed configuration from the database with unread counts, ordered by priority."""
    # Check cache first
    cache_key = cache.generate_cache_key("feeds_config")
    cached_result = cache.get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result
    
    conn = await get_db_connection()
    
    # Get threshold for last 7 days
    threshold = datetime.now(IST) - timedelta(days=7)
    
    ordered_categories_rows = await conn.fetch('SELECT name FROM categories ORDER BY priority')
    ordered_categories = [row['name'] for row in ordered_categories_rows]
    
    all_feeds_rows = await conn.fetch('SELECT id, name, url, category, "isActive", priority, retention_days, polling_interval, fetch_full_content FROM feeds')
    
    feeds_by_category = {}
    for row in all_feeds_rows:
        category = row['category']
        feed_id = row['id']
        
        # Get unread count for this feed using feed_id (works for all articles)
        unread_count = await conn.fetchval(
            '''
            SELECT COUNT(*) 
            FROM articles a
            LEFT JOIN user_article_status uas ON a.link = uas.article_link
            WHERE a.feed_id = $1
            AND a.published_datetime > $2
            AND (uas.is_read IS NULL OR uas.is_read = false)
            ''',
            feed_id, threshold
        )
        
        if category not in feeds_by_category:
            feeds_by_category[category] = []
        feeds_by_category[category].append({
            "id": row['id'],
            "name": row['name'],
            "url": row['url'],
            "isActive": row['isActive'],
            "priority": row['priority'],
            "retention_days": row['retention_days'],
            "polling_interval": row['polling_interval'],
            "fetch_full_content": row['fetch_full_content'],
            "unread_count": unread_count
        })
        
        logging.info(f"[Feeds] {row['name']}: unread={unread_count}")
        
    for category in feeds_by_category:
        feeds_by_category[category].sort(key=lambda x: x['priority'])
        
    feeds_config = {}
    for category_name in ordered_categories:
        # Include all categories, even if they have no feeds
        feeds_config[category_name] = feeds_by_category.get(category_name, [])

    await database.release_db_connection(conn)
    
    result = JSONResponse(content=feeds_config)
    cache.set_in_cache(cache_key, result)
    return result

@app.post("/api/feeds/config")
async def update_feeds_config(request: Request):
    """Update the isActive status of feeds in the database."""
    try:
        body = await request.json()
        
        if not isinstance(body, dict):
            return JSONResponse({"error": "Invalid configuration format"}, status_code=400)

        conn = await get_db_connection()

        try:
            updates = []
            for category, feeds_list in body.items():
                for feed in feeds_list:
                    updates.append((feed.get('isActive', True), feed.get('id')))
            
            await conn.executemany(
                'UPDATE feeds SET "isActive" = $1 WHERE id = $2',
                updates
            )
            
            # Invalidate feed caches after config update
            cache.invalidate_feeds_cache()
            
            return JSONResponse({"message": "Feed configuration updated successfully"})

        except Exception as e:
            logging.exception("Error updating feed configuration in DB: %s", str(e))
            return JSONResponse({"error": "Failed to update configuration in database"}, status_code=500)
        finally:
            await database.release_db_connection(conn)

    except Exception as e:
        logging.exception("Error processing request for feed configuration update: %s", str(e))
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/feeds")
async def feeds(
    days: int = Query(10, description="Number of days back to fetch articles for.", ge=1, le=30),
    q: str = Query(None, description="Search query for articles"),
    category: str = Query(None, description="Category filter for search"),
    feed_url: str = Query(None, description="Feed URL to filter by specific feed"),
    starred_only: bool = Query(False, description="Filter to show only starred articles"),
    limit: int = Query(None, description="Number of articles to return (for pagination)", ge=1, le=500),
    offset: int = Query(None, description="Number of articles to skip (for pagination)", ge=0),
    view: str = Query("standard", description="View type: 'standard' or 'ai' for AI-filtered articles")
):
    """
    Get feeds with optional search, starred filter, AI filtering, and pagination functionality.
    
    - If `q` is provided, performs a search (global or category-specific)
    - If `q` and `category` are provided, searches within that category only
    - If `starred_only` is true, filters to show only starred articles
    - If `view` is 'ai', shows only AI-filtered articles (requires category with AI enabled)
    - If `limit` and `offset` are provided, returns paginated results with metadata
    - If neither is provided, returns standard feed view grouped by category
    """
    
    # Check cache first
    cache_key = cache.generate_cache_key(
        "feeds", 
        days=days, 
        q=q, 
        category=category,
        feed_url=feed_url,
        starred_only=starred_only, 
        limit=limit, 
        offset=offset, 
        view=view
    )
    cached_result = cache.get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result
    
    # Get user's timezone preference
    user_tz = await get_user_timezone()
    
    # Paginated mode - returns flat list with metadata
    if limit is not None:
        offset = offset or 0
        
        # Get paginated articles
        articles = await get_all_articles_paginated(
            days=days,
            starred_only=starred_only,
            limit=limit,
            offset=offset,
            category=category,
            feed_url=feed_url,
            target_tz=user_tz,
            view=view
        )
        
        # Apply search filter if provided
        if q:
            search_results = await search_articles(q, category=category)
            if starred_only:
                search_results = [article for article in search_results if article.get('starred', False)]
            
            # Paginate search results
            articles = search_results[offset:offset + limit]
            total_count = len(search_results)
        else:
            # Get total count
            total_count = await get_total_articles_count(
                category=category,
                days=days,
                starred_only=starred_only,
                search_query=q,
                feed_url=feed_url
            )
        
        result = JSONResponse(content={
            "articles": articles,
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(articles)) < total_count
        })
        cache.set_in_cache(cache_key, result)
        return result
    
    # Handle search queries (non-paginated)
    if q:
        search_results = await search_articles(q, category=category)
        
        # Apply starred filter if requested
        if starred_only:
            search_results = [article for article in search_results if article.get('starred', False)]
        
        if category:
            # Return results for specific category
            result = JSONResponse(content=[{
                "category": category,
                "feed_items": search_results
            }])
            cache.set_in_cache(cache_key, result)
            return result
        else:
            # Group results by category for global search
            categories_dict = {}
            for article in search_results:
                cat = article['category']
                if cat not in categories_dict:
                    categories_dict[cat] = []
                categories_dict[cat].append(article)
            
            categories_list = [
                {"category": cat, "feed_items": articles}
                for cat, articles in categories_dict.items()
            ]
            
            result = JSONResponse(content=categories_list)
            cache.set_in_cache(cache_key, result)
            return result
    
    # Standard feed view (no search, no pagination) - grouped by category
    conn = await get_db_connection()
    
    try:
        ordered_categories_rows = await conn.fetch("SELECT name FROM categories ORDER BY priority")
        ordered_categories = [row['name'] for row in ordered_categories_rows]
            
        categories_list = []
        for cat in ordered_categories:
            articles = await get_articles_for_category_db(cat, days=days, starred_only=starred_only, target_tz=user_tz, view=view)
            if articles:
                categories_list.append({"category": cat, "feed_items": articles})
                
        result = JSONResponse(content=categories_list)
        cache.set_in_cache(cache_key, result)
        return result
        
    finally:
        await database.release_db_connection(conn)

@app.post("/api/article/star")
async def star_article(request: Request):
    """Star or unstar an article."""
    try:
        body = await request.json()
        link = body.get("link", "").strip()
        starred = body.get("starred", False)
        
        if not link:
            return JSONResponse({"error": "Article link is required"}, status_code=400)
        
        conn = await get_db_connection()
        
        try:
            # Update the starred status
            result = await conn.execute(
                'UPDATE articles SET starred = $1 WHERE link = $2',
                starred, link
            )
            
            # Check if the article was found and updated
            if result == 'UPDATE 0':
                return JSONResponse({"error": "Article not found"}, status_code=404)
            
            # Invalidate feed caches after starring/unstarring
            cache.invalidate_feeds_cache()
            
            return JSONResponse({
                "message": "Article starred status updated successfully",
                "link": link,
                "starred": starred
            })
        
        except asyncpg.PostgresError as e:
            logging.exception("Database error updating starred status: %s", str(e))
            return JSONResponse({"error": "Database error"}, status_code=500)
        finally:
            await database.release_db_connection(conn)
    
    except Exception as e:
        logging.exception("Error updating starred status: %s", str(e))
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/articles/updates")
async def get_articles_updates(since: str = Query(..., description="ISO 8601 timestamp to check for new articles since")):
    """
    Get count of new articles published since the provided timestamp.
    This endpoint is NOT cached to provide real-time updates.
    
    Returns:
        {
            "total": 15,
            "by_category": {
                "Tech": 5,
                "News": 10
            },
            "timestamp": "2025-01-01T12:00:00Z"
        }
    """
    try:
        # Parse the timestamp
        since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
        logging.info(f"[Updates] Checking for articles since: {since_dt}")
        
        conn = await get_db_connection()
        
        try:
            # Get total count of new articles
            total_count = await conn.fetchval(
                'SELECT COUNT(*) FROM articles WHERE published_datetime > $1',
                since_dt
            )
            
            logging.info(f"[Updates] Found {total_count} new articles")
            
            # Get count by category
            category_rows = await conn.fetch(
                '''
                SELECT category, COUNT(*) as count 
                FROM articles 
                WHERE published_datetime > $1 
                GROUP BY category
                ORDER BY category
                ''',
                since_dt
            )
            
            by_category = {row['category']: row['count'] for row in category_rows}
            
            response_data = {
                "total": total_count,
                "by_category": by_category,
                "timestamp": datetime.now(pytz.utc).isoformat()
            }
            
            logging.debug(f"[Updates] Response: {response_data}")
            
            return JSONResponse(content=response_data)
            
        finally:
            await database.release_db_connection(conn)
    
    except ValueError as e:
        logging.error(f"Invalid timestamp format: {e}")
        return JSONResponse({"error": "Invalid timestamp format. Use ISO 8601 format."}, status_code=400)
    except Exception as e:
        logging.exception(f"Error fetching article updates: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/articles/statuses")
async def get_articles_statuses(request: Request):
    """Fetch read status for a list of article links."""
    try:
        body = await request.json()
        links = body.get("links", [])
        
        if not links:
            return JSONResponse({})
        
        conn = await get_db_connection()
        
        try:
            # Fetch read statuses for the provided links
            rows = await conn.fetch(
                'SELECT article_link, is_read FROM user_article_status WHERE article_link = ANY($1)',
                links
            )
            
            # Build a dictionary of link -> is_read
            statuses = {row['article_link']: row['is_read'] for row in rows}
            
            return JSONResponse(statuses)
        
        except asyncpg.PostgresError as e:
            logging.exception("Database error fetching article statuses: %s", str(e))
            return JSONResponse({"error": "Database error"}, status_code=500)
        finally:
            await database.release_db_connection(conn)
    
    except Exception as e:
        logging.exception("Error fetching article statuses: %s", str(e))
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/articles/mark-as-read")
async def mark_articles_as_read(request: Request):
    """Mark one or more articles as read."""
    try:
        body = await request.json()
        links = body.get("links", [])
        
        if not links:
            return JSONResponse({"message": "No links provided"}, status_code=400)
        
        conn = await get_db_connection()
        
        try:
            # Insert or update read status for each link
            for link in links:
                await conn.execute(
                    '''
                    INSERT INTO user_article_status (article_link, is_read, read_at)
                    VALUES ($1, true, CURRENT_TIMESTAMP)
                    ON CONFLICT (article_link) 
                    DO UPDATE SET is_read = true, read_at = CURRENT_TIMESTAMP
                    ''',
                    link
                )
            
            return JSONResponse({
                "message": f"Marked {len(links)} article(s) as read",
                "count": len(links)
            })
        
        except asyncpg.PostgresError as e:
            logging.exception("Database error marking articles as read: %s", str(e))
            return JSONResponse({"error": "Database error"}, status_code=500)
        finally:
            await database.release_db_connection(conn)
    
    except Exception as e:
        logging.exception("Error marking articles as read: %s", str(e))
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/feed/mark-all-read")
async def mark_feed_articles_as_read(request: Request):
    """Mark all unread articles from a specific feed as read."""
    try:
        body = await request.json()
        feed_url = body.get("feed_url", "").strip()
        
        if not feed_url:
            return JSONResponse({"message": "Feed URL is required"}, status_code=400)
        
        conn = await get_db_connection()
        
        try:
            # Get feed_id from URL
            feed_id = await conn.fetchval("SELECT id FROM feeds WHERE url = $1", feed_url)
            if not feed_id:
                return JSONResponse({"message": "Feed not found"}, status_code=404)
            
            # Get threshold for last 7 days
            threshold = datetime.now(IST) - timedelta(days=7)
            
            # Get all article links from this feed that are unread (using feed_id)
            articles = await conn.fetch(
                '''
                SELECT a.link 
                FROM articles a
                LEFT JOIN user_article_status uas ON a.link = uas.article_link
                WHERE a.feed_id = $1 
                AND a.published_datetime > $2
                AND (uas.is_read IS NULL OR uas.is_read = false)
                ''',
                feed_id, threshold
            )
            
            # Mark all as read
            count = 0
            for article in articles:
                await conn.execute(
                    '''
                    INSERT INTO user_article_status (article_link, is_read, read_at)
                    VALUES ($1, true, CURRENT_TIMESTAMP)
                    ON CONFLICT (article_link) 
                    DO UPDATE SET is_read = true, read_at = CURRENT_TIMESTAMP
                    ''',
                    article['link']
                )
                count += 1
            
            # Invalidate cache
            cache.invalidate_feeds_cache()
            
            logging.info(f"[MarkAllRead] Marked {count} articles as read for feed: {feed_url}")
            
            return JSONResponse({
                "message": f"Marked {count} article(s) as read",
                "count": count
            })
        
        except asyncpg.PostgresError as e:
            logging.exception("Database error marking feed articles as read: %s", str(e))
            return JSONResponse({"error": "Database error"}, status_code=500)
        finally:
            await database.release_db_connection(conn)
    
    except Exception as e:
        logging.exception("Error marking feed articles as read: %s", str(e))
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/add-feed")
async def add_feed(request: Request):
    """Add a custom RSS feed to the database with synchronous initial fetch"""
    try:
        body = await request.json()
        url = body.get("url", "").strip()
        category_name = body.get("category", "").strip()
        name = body.get("name", "").strip()
        retention_days = body.get("retention_days") # Can be None
        polling_interval = body.get("polling_interval", 60) # Default to 60 minutes (1 hour)
        fetch_full_content = body.get("fetch_full_content", False) # Default to False for fast initial fetch
        
        if not url or not category_name:
            return JSONResponse({"error": "URL and category are required"}, status_code=400)
        
        if not url.startswith(("http://", "https://")):
            return JSONResponse({"error": "Invalid URL format"}, status_code=400)
        
        feed_name = name or url.split("/")[-1] or "Custom Feed"

        conn = await get_db_connection()
        
        try:
            await conn.execute("INSERT INTO categories (name) VALUES ($1) ON CONFLICT (name) DO NOTHING", category_name)
            
            max_priority = await conn.fetchval("SELECT COALESCE(MAX(priority), -1) FROM feeds WHERE category = $1", category_name)

            result = await conn.execute(
                """
                INSERT INTO feeds (name, url, category, "isActive", priority, retention_days, polling_interval, fetch_full_content)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (url) DO NOTHING;
                """,
                feed_name, url, category_name, True, max_priority + 1, retention_days, polling_interval, fetch_full_content
            )
            if result == 'INSERT 0 0':
                return JSONResponse({"error": "Feed with this URL already exists"}, status_code=400)

            feed_id = await conn.fetchval("SELECT id FROM feeds WHERE url = $1", url)
            
            # Set next_check_at for future updates by the batch scheduler
            next_check = datetime.now(IST) + timedelta(minutes=polling_interval)
            await conn.execute(
                "UPDATE feeds SET next_check_at = $1 WHERE id = $2",
                next_check, feed_id
            )
            
        except asyncpg.PostgresError as e:
            logging.exception("Database error adding feed: %s", str(e))
            await database.release_db_connection(conn)
            return JSONResponse({"error": "Database error"}, status_code=500)
        finally:
            await database.release_db_connection(conn)
        
        # Perform synchronous initial fetch (fast - no full-text extraction)
        try:
            articles_added = await parse_and_store_rss_feed_initial(feed_id, url, category_name, feed_name)
            
            # Invalidate feed caches after adding a new feed
            cache.invalidate_feeds_cache()
            
            return JSONResponse({
                "message": f"Feed added successfully with {articles_added} articles", 
                "category": category_name, 
                "url": url,
                "feed_id": feed_id,
                "articles_added": articles_added
            })
        except Exception as e:
            logging.exception("Error during initial feed fetch: %s", str(e))
            return JSONResponse({
                "error": f"Feed added but initial fetch failed: {str(e)}", 
                "category": category_name, 
                "url": url,
                "feed_id": feed_id
            }, status_code=500)

    except Exception as e:
        logging.exception("Error adding feed: %s", str(e))
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/article-full-text")
async def article_full_text(url: str):
    try:
        # Check cache first
        cache_key = cache.generate_cache_key("article_full_text", url=url)
        cached_result = cache.get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        youtube_only_html = convert_links_to_embeds(url)
        if "youtube-embed-placeholder" in youtube_only_html:
            result = JSONResponse({"content": youtube_only_html})
            cache.set_in_cache(cache_key, result)
            return result

        conn = await get_db_connection()
        content_html = await conn.fetchval('SELECT content FROM articles WHERE link = $1', url)
        await database.release_db_connection(conn)

        if not content_html:
            # Fallback to fetching live if not in DB using readability
            content_html = await extract_article_content_with_readability(url)

        if content_html:
            content_html = convert_links_to_embeds(content_html)
            if "youtube-embed-placeholder" in content_html:
                result = JSONResponse({"content": content_html})
            else:
                # Format the article content for consistent, readable display
                formatted_content = format_article_content(content_html)
                result = JSONResponse({"content": formatted_content})
        else:
            result = JSONResponse({"content": "<p>No content could be extracted.</p>"})
        
        # Cache the result
        cache.set_in_cache(cache_key, result)
        return result

    except Exception as e:
        logging.exception(f"Error fetching full text for {url}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/article-full-html")
async def article_full_html(url: str):
    """
    Fetch and return raw HTML content of an article using readability.
    This endpoint returns unformatted HTML for direct use.
    """
    try:
        content_html = await extract_article_content_with_readability(url)
        return JSONResponse({"html": content_html})
    except Exception as e:
        logging.exception(f"Error fetching full HTML for {url}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.put("/api/feed/{feed_id}")
async def update_feed(feed_id: int, request: Request):
    """Update a feed's details."""
    try:
        body = await request.json()
        name = body.get("name")
        url = body.get("url")
        category = body.get("category")
        priority = body.get("priority")
        retention_days = body.get("retention_days") # Can be None
        polling_interval = body.get("polling_interval", 60) # Default to 60 minutes (1 hour)
        fetch_full_content = body.get("fetch_full_content", False)

        if not all([name, url, category]):
            raise HTTPException(status_code=400, detail="Name, URL, and category are required.")

        conn = await get_db_connection()
        
        # Update feed details and reset next_check_at to trigger immediate refresh
        next_check = datetime.now(IST)
        await conn.execute(
            'UPDATE feeds SET name = $1, url = $2, category = $3, priority = $4, retention_days = $5, polling_interval = $6, fetch_full_content = $7, next_check_at = $8 WHERE id = $9',
            name, url, category, priority, retention_days, polling_interval, fetch_full_content, next_check, feed_id
        )
        await database.release_db_connection(conn)
        
        # The batch scheduler will pick up the feed automatically based on next_check_at
        # No need for APScheduler jobs anymore
        logging.info(f"Updated feed '{name}' (ID: {feed_id}) with {polling_interval} minute interval, will be picked up by batch scheduler")
        
        return JSONResponse({"message": "Feed updated successfully."})
    except Exception as e:
        logging.error(f"Error updating feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/feed/{feed_id}")
async def delete_feed(feed_id: int):
    """Delete a feed and its associated articles."""
    try:
        conn = await get_db_connection()
        
        # Delete articles first (explicit, though CASCADE should handle this)
        articles_deleted = await conn.execute('DELETE FROM articles WHERE feed_id = $1', feed_id)
        
        # Delete the feed
        await conn.execute('DELETE FROM feeds WHERE id = $1', feed_id)
        
        await database.release_db_connection(conn)
        
        # No need to remove APScheduler jobs anymore - using RQ worker system
        logging.info(f"Deleted feed ID: {feed_id} and its articles")
        
        # Invalidate feed caches after deleting a feed
        cache.invalidate_feeds_cache()
        
        return JSONResponse({"message": "Feed and associated articles deleted successfully."})
    except Exception as e:
        logging.error(f"Error deleting feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings")
async def get_settings():
    """Get all user settings."""
    conn = await get_db_connection()
    rows = await conn.fetch("SELECT key, value FROM user_settings")
    settings = {row['key']: row['value'] for row in rows}
    await database.release_db_connection(conn)
    return JSONResponse(content=settings)

@app.put("/api/settings")
async def update_settings(request: Request):
    """Update user settings."""
    try:
        body = await request.json()
        
        conn = await get_db_connection()
        
        for key, value in body.items():
            await conn.execute(
                "INSERT INTO user_settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = $2",
                key, value
            )
        
        await database.release_db_connection(conn)
        return JSONResponse({"message": "Settings updated successfully"})
    except Exception as e:
        logging.error(f"Error updating settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/categories")
async def get_categories():
    """Get all categories with article counts, ordered by priority."""
    # Check cache first
    cache_key = cache.generate_cache_key("categories")
    cached_result = cache.get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result
    
    conn = await get_db_connection()
    rows = await conn.fetch("SELECT id, name, priority, is_default, ntfy_enabled, telegram_enabled, telegram_chat_id, ai_prompt, ai_enabled FROM categories ORDER BY priority")
    
    # Get article counts for each category (last 7 days)
    threshold = datetime.now(IST) - timedelta(days=7)
    
    categories = []
    for row in rows:
        category_name = row['name']
        
        # Get total articles count
        total_count = await conn.fetchval(
            'SELECT COUNT(*) FROM articles WHERE category = $1 AND published_datetime > $2',
            category_name, threshold
        )
        
        # Get unread articles count (articles not in user_article_status or is_read = false)
        unread_count = await conn.fetchval(
            '''
            SELECT COUNT(*) 
            FROM articles a
            LEFT JOIN user_article_status uas ON a.link = uas.article_link
            WHERE a.category = $1 
            AND a.published_datetime > $2
            AND (uas.is_read IS NULL OR uas.is_read = false)
            ''',
            category_name, threshold
        )
        
        categories.append({
            "id": row['id'], 
            "name": row['name'], 
            "priority": row['priority'], 
            "is_default": row['is_default'], 
            "ntfy_enabled": row['ntfy_enabled'],
            "telegram_enabled": row['telegram_enabled'],
            "telegram_chat_id": row['telegram_chat_id'],
            "ai_prompt": row['ai_prompt'],
            "ai_enabled": row['ai_enabled'],
            "unread_count": unread_count,
            "total_count": total_count
        })
        
        logging.info(f"[Categories] {category_name}: unread={unread_count}, total={total_count}")
    
    await database.release_db_connection(conn)
    
    result = JSONResponse(content=categories)
    cache.set_in_cache(cache_key, result)
    return result

@app.put("/api/categories/order")
async def update_category_order(request: Request):
    """Update the priority order of categories."""
    try:
        categories_order = await request.json() # Expects a list of category IDs in the new order
        conn = await get_db_connection()
        for index, category_id in enumerate(categories_order):
            await conn.execute("UPDATE categories SET priority = $1 WHERE id = $2", index, category_id)
        await database.release_db_connection(conn)
        return JSONResponse({"message": "Category order updated."})
    except Exception as e:
        logging.error(f"Error updating category order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/category/{category_id}/default")
async def set_default_category(category_id: int):
    """Set a category as the default."""
    try:
        conn = await get_db_connection()
        await conn.execute("UPDATE categories SET is_default = false WHERE is_default = true")
        await conn.execute("UPDATE categories SET is_default = true WHERE id = $1", category_id)
        await database.release_db_connection(conn)
        return JSONResponse({"message": "Default category updated."})
    except Exception as e:
        logging.error(f"Error setting default category: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/category/{category_id}/ntfy")
async def toggle_category_ntfy(category_id: int, request: Request):
    """Toggle ntfy notifications for a category."""
    try:
        body = await request.json()
        ntfy_enabled = body.get("ntfy_enabled", True)
        
        conn = await get_db_connection()
        await conn.execute("UPDATE categories SET ntfy_enabled = $1 WHERE id = $2", ntfy_enabled, category_id)
        await database.release_db_connection(conn)
        
        return JSONResponse({"message": f"Ntfy notifications {'enabled' if ntfy_enabled else 'disabled'} for category."})
    except Exception as e:
        logging.error(f"Error toggling category ntfy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/category/{category_id}/telegram")
async def update_category_telegram(category_id: int, request: Request):
    """Update telegram notifications settings for a category."""
    try:
        body = await request.json()
        telegram_enabled = body.get("telegram_enabled", False)
        telegram_chat_id = body.get("telegram_chat_id", None)
        
        conn = await get_db_connection()
        await conn.execute(
            "UPDATE categories SET telegram_enabled = $1, telegram_chat_id = $2 WHERE id = $3", 
            telegram_enabled, telegram_chat_id, category_id
        )
        await database.release_db_connection(conn)
        
        return JSONResponse({"message": f"Telegram notifications {'enabled' if telegram_enabled else 'disabled'} for category."})
    except Exception as e:
        logging.error(f"Error updating category telegram settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/category/{category_id}/name")
async def update_category_name(category_id: int, request: Request):
    """Update a category's name."""
    try:
        body = await request.json()
        new_name = body.get("name", "").strip()
        
        if not new_name:
            return JSONResponse({"error": "Category name is required"}, status_code=400)
        
        conn = await get_db_connection()
        
        # Get old category name
        old_name_row = await conn.fetchrow("SELECT name FROM categories WHERE id = $1", category_id)
        if not old_name_row:
            await database.release_db_connection(conn)
            raise HTTPException(status_code=404, detail="Category not found")
        
        old_name = old_name_row['name']
        
        # Check if new name already exists (for a different category)
        existing = await conn.fetchval("SELECT id FROM categories WHERE name = $1 AND id != $2", new_name, category_id)
        if existing:
            await database.release_db_connection(conn)
            return JSONResponse({"error": "A category with this name already exists"}, status_code=400)
        
        # Update category name
        await conn.execute("UPDATE categories SET name = $1 WHERE id = $2", new_name, category_id)
        
        # Update all feeds and articles with this category
        await conn.execute("UPDATE feeds SET category = $1 WHERE category = $2", new_name, old_name)
        await conn.execute("UPDATE articles SET category = $1 WHERE category = $2", new_name, old_name)
        
        await database.release_db_connection(conn)
        
        return JSONResponse({"message": f"Category renamed from '{old_name}' to '{new_name}'"})
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating category name: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/category/{category_id}")
async def delete_category(category_id: int):
    """Delete a category and all its feeds."""
    try:
        conn = await get_db_connection()
        category_name_row = await conn.fetchrow("SELECT name FROM categories WHERE id = $1", category_id)
        if not category_name_row:
            raise HTTPException(status_code=404, detail="Category not found.")
        category_name = category_name_row['name']
        
        await conn.execute("DELETE FROM feeds WHERE category = $1", category_name)
        await conn.execute("DELETE FROM categories WHERE id = $1", category_id)
        
        await database.release_db_connection(conn)
        return JSONResponse({"message": f"Category '{category_name}' and its feeds have been deleted."})
    except Exception as e:
        logging.error(f"Error deleting category: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/category/{category_id}/ai-settings")
async def get_category_ai_settings(category_id: int):
    """Get AI filter settings for a category."""
    try:
        conn = await get_db_connection()
        category = await conn.fetchrow(
            "SELECT ai_prompt, ai_enabled FROM categories WHERE id = $1",
            category_id
        )
        await database.release_db_connection(conn)
        
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
        
        return JSONResponse(content={
            "ai_prompt": category['ai_prompt'],
            "ai_enabled": category['ai_enabled']
        })
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting AI settings for category {category_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/category/{category_id}/ai-settings")
async def update_category_ai_settings(category_id: int, request: Request):
    """Update AI filter settings for a category."""
    try:
        body = await request.json()
        ai_prompt = body.get("ai_prompt")
        ai_enabled = body.get("ai_enabled", False)
        
        conn = await get_db_connection()
        
        # Get old prompt to check if it changed
        old_category = await conn.fetchrow(
            "SELECT ai_prompt, ai_enabled FROM categories WHERE id = $1",
            category_id
        )
        
        if not old_category:
            await database.release_db_connection(conn)
            raise HTTPException(status_code=404, detail="Category not found")
        
        # Update settings
        await conn.execute(
            "UPDATE categories SET ai_prompt = $1, ai_enabled = $2 WHERE id = $3",
            ai_prompt, ai_enabled, category_id
        )
        
        await database.release_db_connection(conn)
        
        # Note: We don't automatically reprocess old articles to save costs
        # Users must manually click "Reprocess Articles" if they want to filter existing articles
        return JSONResponse(content={
            "success": True,
            "message": "AI filter settings updated. New articles will be filtered automatically."
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating AI settings for category {category_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/category/{category_id}/reprocess-ai-filter")
async def reprocess_category_ai_filter(category_id: int):
    """Manually trigger reprocessing of all articles for a category's AI filter."""
    try:
        conn = await get_db_connection()
        
        # Check if category exists
        category = await conn.fetchrow(
            "SELECT id, ai_enabled FROM categories WHERE id = $1",
            category_id
        )
        
        if not category:
            await database.release_db_connection(conn)
            raise HTTPException(status_code=404, detail="Category not found")
        
        if not category['ai_enabled']:
            await database.release_db_connection(conn)
            raise HTTPException(status_code=400, detail="AI filtering not enabled for this category")
        
        # Reprocess articles
        stats = await ai_filter.reprocess_category_articles(category_id, conn)
        
        await database.release_db_connection(conn)
        
        return JSONResponse(content={
            "success": True,
            "stats": stats
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error reprocessing category {category_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/feeds/column", response_class=HTMLResponse)
async def feeds_column(request: Request):
    conn = await get_db_connection()
    categories_rows = await conn.fetch("SELECT name FROM categories ORDER BY priority")
    categories = [row['name'] for row in categories_rows]
    await database.release_db_connection(conn)

    categories_list = []
    for category in categories:
        articles = await get_articles_for_category_db(category, days=10)
        categories_list.append({"category": category, "feed_items": articles})
    return templates.TemplateResponse("feeds-split.html", {"request": request, "categories": categories_list})

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})



# ===================== Keyword/Topic Filter Endpoints =====================

@app.get("/api/filters")
async def get_filters(category_id: int = None):
    """Get all filters, optionally filtered by category."""
    try:
        conn = await get_db_connection()
        
        if category_id:
            filters = await conn.fetch("""
                SELECT f.id, f.name, f.category_id, c.name as category_name,
                       f.filter_type, f.filter_value, f.auto_star, f.auto_notify, 
                       f.enabled, f.created_at
                FROM article_filters f
                LEFT JOIN categories c ON f.category_id = c.id
                WHERE f.category_id = $1 OR f.category_id IS NULL
                ORDER BY f.created_at DESC
            """, category_id)
        else:
            filters = await conn.fetch("""
                SELECT f.id, f.name, f.category_id, c.name as category_name,
                       f.filter_type, f.filter_value, f.auto_star, f.auto_notify, 
                       f.enabled, f.created_at
                FROM article_filters f
                LEFT JOIN categories c ON f.category_id = c.id
                ORDER BY f.created_at DESC
            """)
        
        await database.release_db_connection(conn)
        
        # Convert datetime objects to ISO strings for JSON serialization
        filters_list = []
        for f in filters:
            filter_dict = dict(f)
            if filter_dict.get('created_at'):
                filter_dict['created_at'] = filter_dict['created_at'].isoformat()
            if filter_dict.get('updated_at'):
                filter_dict['updated_at'] = filter_dict['updated_at'].isoformat()
            filters_list.append(filter_dict)
        
        return JSONResponse(content=filters_list)
    except Exception as e:
        logging.error(f"Error getting filters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/filters")
async def create_filter(request: Request):
    """Create a new keyword or topic filter."""
    try:
        body = await request.json()
        name = body.get("name", "").strip()
        category_id = body.get("category_id")  # Can be null for global filters
        filter_type = body.get("filter_type", "keyword")
        filter_value = body.get("filter_value", "").strip()
        auto_star = body.get("auto_star", True)
        auto_notify = body.get("auto_notify", True)
        enabled = body.get("enabled", True)
        
        if not name or not filter_value:
            return JSONResponse({"error": "Name and filter value are required"}, status_code=400)
        
        if filter_type not in ['keyword', 'topic']:
            return JSONResponse({"error": "Filter type must be 'keyword' or 'topic'"}, status_code=400)
        
        conn = await get_db_connection()
        
        # If category_id is provided, verify it exists
        if category_id:
            category_exists = await conn.fetchval("SELECT id FROM categories WHERE id = $1", category_id)
            if not category_exists:
                await database.release_db_connection(conn)
                return JSONResponse({"error": "Category not found"}, status_code=404)
        
        # Insert filter
        filter_id = await conn.fetchval("""
            INSERT INTO article_filters 
            (name, category_id, filter_type, filter_value, auto_star, auto_notify, enabled)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """, name, category_id, filter_type, filter_value, auto_star, auto_notify, enabled)
        
        await database.release_db_connection(conn)
        
        return JSONResponse(content={
            "message": "Filter created successfully",
            "filter_id": filter_id
        })
    except Exception as e:
        logging.error(f"Error creating filter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/filters/{filter_id}")
async def update_filter(filter_id: int, request: Request):
    """Update an existing filter."""
    try:
        body = await request.json()
        name = body.get("name", "").strip()
        filter_value = body.get("filter_value", "").strip()
        auto_star = body.get("auto_star", True)
        auto_notify = body.get("auto_notify", True)
        enabled = body.get("enabled", True)
        
        if not name or not filter_value:
            return JSONResponse({"error": "Name and filter value are required"}, status_code=400)
        
        conn = await get_db_connection()
        
        result = await conn.execute("""
            UPDATE article_filters 
            SET name = $1, filter_value = $2, auto_star = $3, auto_notify = $4, 
                enabled = $5, updated_at = CURRENT_TIMESTAMP
            WHERE id = $6
        """, name, filter_value, auto_star, auto_notify, enabled, filter_id)
        
        await database.release_db_connection(conn)
        
        if result == 'UPDATE 0':
            return JSONResponse({"error": "Filter not found"}, status_code=404)
        
        return JSONResponse(content={"message": "Filter updated successfully"})
    except Exception as e:
        logging.error(f"Error updating filter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/filters/{filter_id}")
async def delete_filter(filter_id: int):
    """Delete a filter."""
    try:
        conn = await get_db_connection()
        
        result = await conn.execute("DELETE FROM article_filters WHERE id = $1", filter_id)
        
        await database.release_db_connection(conn)
        
        if result == 'DELETE 0':
            return JSONResponse({"error": "Filter not found"}, status_code=404)
        
        return JSONResponse(content={"message": "Filter deleted successfully"})
    except Exception as e:
        logging.error(f"Error deleting filter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/filters/{filter_id}/statistics")
async def get_filter_statistics_endpoint(filter_id: int, days: int = 30):
    """Get statistics for a specific filter."""
    try:
        conn = await get_db_connection()
        
        from datetime import datetime, timedelta
        threshold = datetime.now(IST) - timedelta(days=days)
        
        stats = await conn.fetchrow("""
            SELECT 
                f.id,
                f.name,
                f.filter_type,
                f.filter_value,
                COUNT(DISTINCT afm.article_id) as total_matches,
                COUNT(DISTINCT CASE WHEN a.starred = true THEN afm.article_id END) as starred_matches
            FROM article_filters f
            LEFT JOIN article_filter_matches afm ON f.id = afm.filter_id AND afm.matched_at >= $1
            LEFT JOIN articles a ON afm.article_id = a.id
            WHERE f.id = $2
            GROUP BY f.id, f.name, f.filter_type, f.filter_value
        """, threshold, filter_id)
        
        await database.release_db_connection(conn)
        
        if not stats:
            return JSONResponse({"error": "Filter not found"}, status_code=404)
        
        return JSONResponse(content=dict(stats))
    except Exception as e:
        logging.error(f"Error getting filter statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/filters/statistics/all")
async def get_all_filters_statistics(category_id: int = None, days: int = 30):
    """Get statistics for all filters."""
    try:
        conn = await get_db_connection()
        stats = await keyword_filter.get_filter_statistics(conn, category_id, days)
        await database.release_db_connection(conn)
        
        return JSONResponse(content=stats)
    except Exception as e:
        logging.error(f"Error getting all filter statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== Article Summarization Endpoint =====================

@app.post("/api/article/summarize")
async def summarize_article(request: Request):
    """Generate an AI summary of an article."""
    try:
        body = await request.json()
        article_link = body.get("link", "").strip()
        
        if not article_link:
            return JSONResponse({"error": "Article link is required"}, status_code=400)
        
        # Get article content from database
        conn = await get_db_connection()
        article = await conn.fetchrow("""
            SELECT title, description, content FROM articles WHERE link = $1
        """, article_link)
        await database.release_db_connection(conn)
        
        if not article:
            return JSONResponse({"error": "Article not found"}, status_code=404)
        
        title = article['title'] or ""
        description = article['description'] or ""
        content = article['content'] or ""
        
        # Use AI to generate summary
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(
                api_key=Config.OPENAI_API_KEY,
                base_url=Config.OPENAI_BASE_URL
            )
            
            # Prepare content for summarization
            # Use content if available, otherwise use description
            text_to_summarize = content if content else description
            
            # Strip HTML tags for cleaner summarization
            import re
            clean_text = re.sub('<[^<]+?>', '', text_to_summarize)
            clean_text = clean_text[:3000]  # Limit to avoid token limits
            
            system_message = """You are a helpful assistant that creates concise, informative summaries of news articles. 
Your summaries should:
- Capture the key points and main ideas
- Be 3-5 sentences long
- Be clear and easy to understand
- Focus on facts and important details"""
            
            user_message = f"""Please summarize this article:

Title: {title}

Content: {clean_text}"""
            
            response = await client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=200,
                temperature=0.5
            )
            
            summary = response.choices[0].message.content.strip()
            
            return JSONResponse(content={
                "success": True,
                "summary": summary,
                "title": title
            })
            
        except Exception as e:
            logging.error(f"Error generating summary: {e}")
            return JSONResponse({"error": "Failed to generate summary"}, status_code=500)
    
    except Exception as e:
        logging.error(f"Error in summarize_article: {e}")
        raise HTTPException(status_code=500, detail=str(e))
