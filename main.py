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
from newspaper import Article
from bs4 import BeautifulSoup

from dotenv import load_dotenv

from fastapi import FastAPI, Request, Form, HTTPException, File, UploadFile, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache

import asyncpg
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
from datetime import datetime, timedelta

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

from config import Config  # Import our centralized config

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
    "Twitter Feed": [
         {
             "name": "Twitter Feed",
             "url": Config.NITTER_URL
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

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://0.0.0.0:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")


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
async def get_db_connection():
    return await asyncpg.connect(
        database=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        host=Config.DB_HOST,
        port=Config.DB_PORT
    )

async def init_db():
    conn = await get_db_connection()
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        priority INTEGER DEFAULT 0,
        is_default BOOLEAN DEFAULT false
    );
    """)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS feeds (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        url TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL,
        "isActive" BOOLEAN DEFAULT true,
        priority INTEGER DEFAULT 0,
        retention_days INTEGER
    );
    """)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS "YouTube-articles" (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        link TEXT UNIQUE NOT NULL,
        description TEXT,
        thumbnail TEXT,
        published TEXT,
        published_datetime TIMESTAMPTZ,
        category TEXT,
        content TEXT,
        source TEXT,
        feed_id INTEGER REFERENCES feeds(id) ON DELETE CASCADE
    );
    """)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS "FeedState" (
         feed_url TEXT PRIMARY KEY,
         last_update TIMESTAMPTZ
    );
    """)
    
    # Check if feeds table is empty to perform initial population
    if await conn.fetchval("SELECT COUNT(*) FROM feeds") == 0:
        logging.info("Feeds table is empty. Populating with default data from feeds.json.")
        try:
            with open('feeds.json', 'r') as f:
                feed_data = json.load(f)
            
            category_priority = 0
            for category, feeds_list in feed_data.items():
                # Insert category if it doesn't exist
                await conn.execute(
                    "INSERT INTO categories (name, priority) VALUES ($1, $2) ON CONFLICT (name) DO NOTHING",
                    category, category_priority
                )
                category_priority += 1

                feed_priority = 0
                for feed in feeds_list:
                    await conn.execute(
                        """
                        INSERT INTO feeds (name, url, category, "isActive", priority)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (url) DO NOTHING;
                        """,
                        feed['name'], feed['url'], category, feed.get('isActive', True), feed_priority
                    )
                    feed_priority += 1
            logging.info("Default feeds and categories populated successfully.")
        except Exception as e:
            logging.error(f"Could not populate default data from feeds.json: {e}")

    await conn.close()


# --- Helper Function to Ensure Datetime is Timezone-Aware ---
def ensure_aware(dt, tz=IST):
    """
    Ensures that the datetime 'dt' is timezone-aware.
    If 'dt' is naive, it localizes it using the provided timezone (default IST).
    """
    if dt is None:
        return None
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return tz.localize(dt)
    return dt

# --- Feed State Functions ---
async def get_feed_last_update(feed_url: str):
    """
    Retrieves the last update timestamp for the given feed.
    Ensures that the returned datetime is timezone-aware.
    """
    conn = await get_db_connection()
    row = await conn.fetchrow('SELECT last_update FROM "FeedState" WHERE feed_url = $1', feed_url)
    await conn.close()
    if row and row['last_update']:
        return ensure_aware(row['last_update'], IST)
    else:
        return None

async def update_feed_last_update(feed_url: str, new_update: datetime):
    """
    Updates (or inserts) the last update timestamp for the given feed.
    """
    new_update = ensure_aware(new_update, IST)
    conn = await get_db_connection()
    await conn.execute(
        'INSERT INTO "FeedState" (feed_url, last_update) VALUES ($1, $2) ON CONFLICT (feed_url) DO UPDATE SET last_update = EXCLUDED.last_update',
        feed_url, new_update
    )
    await conn.close()




# --- HTML to Markdown Conversion Helper ---
def convert_html_to_markdown(html_content: str) -> str:
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        for p in soup.find_all('p'):
            p.insert_before("\n\n")
            p.append("\n\n")
        for br in soup.find_all('br'):
            br.replace_with("\n")
        cleaned_html = str(soup)
        
        converter = html2text.HTML2Text()
        converter.ignore_images = False
        converter.ignore_links = False
        converter.bypass_tables = False
        converter.body_width = 0
        
        markdown_text = converter.handle(cleaned_html)
        markdown_text = "\n".join(line.rstrip() for line in markdown_text.splitlines())
        markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text)
        return markdown_text.strip()
    except Exception as e:
        logging.exception("Error converting HTML to Markdown: %s", e)
        return html_content
    




NTFY_BASE_URL = os.environ["NTFY_BASE_URL"]



def sanitize_text(text):
    # Normalize the text (NFKD) and then encode/decode to strip out non-Latin-1 characters.
    normalized = unicodedata.normalize('NFKD', text)
    return normalized.encode('latin1', 'ignore').decode('latin1')

async def send_ntfy_notification(title: str, link: str, description: str, category: str, source: str):
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
from newspaper import Article

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
        threshold = last_update if last_update else datetime.now(IST) - timedelta(days=2)
        new_last_update = threshold

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

            if await conn.fetchval('SELECT id FROM "YouTube-articles" WHERE link = $1', link):
                continue

            try:
                art = await run_in_threadpool(lambda: Article(link, keep_article_html=True))
                await run_in_threadpool(art.download)
                await run_in_threadpool(art.parse)
                article_content = art.article_html or art.text
            except Exception:
                logging.exception("Error extracting content for %s", link)
                article_content = None

            await conn.execute(
                'INSERT INTO "YouTube-articles" '
                '(title, link, description, thumbnail, published, published_datetime, category, content, source, feed_id) '
                'VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)',
                title, link, description, thumbnail_url,
                 published_formatted, pub_dt, category, article_content, source_name, feed_id
            )

            await send_ntfy_notification(title, link, description, category, source_name)

        await conn.close()

        if new_last_update > threshold:
            await update_feed_last_update(rss_url, new_last_update)
            logging.info("Updated feed state for %s → %s", rss_url, new_last_update)

    except Exception as e:
        logging.exception("Error parsing/storing feed for URL: %s | Error: %s", rss_url, e)


async def fetch_all_feeds_db():
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
        await conn.close()
        end_time = datetime.now(IST)
        logging.info("Feed update completed at %s", end_time)


async def get_articles_for_category_db(category: str, days: int = 2):
     threshold = datetime.now(IST) - timedelta(days=days)
     conn = await get_db_connection()
     
     query = """
         SELECT a.title, a.link, a.description, a.thumbnail, a.published, a.published_datetime, a.category, a.content, a.source 
         FROM "YouTube-articles" a
         JOIN feeds f ON a.feed_id = f.id
         WHERE a.category = $1 
         AND a.published_datetime >= $2
         AND f."isActive" = true
         ORDER BY a.published_datetime DESC
     """
     params = [category, threshold]
     
     rows = await conn.fetch(query, *params)
     
     articles = []
     for row in rows:
         pub_dt = row['published_datetime']
         pub_dt_str = pub_dt.isoformat() if pub_dt else None
         
         articles.append({
             "title": row['title'],
             "link": row['link'],
             "description": row['description'],
             "thumbnail": row['thumbnail'],
             "published": row['published'],
             "published_datetime": pub_dt_str,
             "category": row['category'],
             "content": row['content'],
             "source": row['source'] or "Unknown"
         })
     await conn.close()
     return articles




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
                    'DELETE FROM "YouTube-articles" WHERE feed_id = $1 AND published_datetime < $2',
                    feed['id'], cutoff_date
                )
                deleted_count = int(result.split(' ')[1])
                if deleted_count > 0:
                    logging.info(f"Deleted {deleted_count} old articles for feed ID {feed['id']} (older than {retention_days} days).")

    except Exception as e:
        logging.exception("Error during scheduled article cleanup: %s", e)
    finally:
        await conn.close()
        logging.info("Finished scheduled cleanup of old articles.")


scheduler = AsyncIOScheduler()
@app.on_event("startup")
async def startup_event():
    FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")
    await init_db()
    
    # Run the first feed fetch in the background immediately on startup
    asyncio.create_task(fetch_all_feeds_db())
    
    scheduler.add_job(fetch_all_feeds_db, 'interval', minutes=1)
    scheduler.add_job(cleanup_old_articles, 'cron', hour=0)  # Run daily at midnight
    scheduler.start()

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
    """Get the current feed configuration from the database, ordered by priority."""
    conn = await get_db_connection()
    
    ordered_categories_rows = await conn.fetch('SELECT name FROM categories ORDER BY priority')
    ordered_categories = [row['name'] for row in ordered_categories_rows]
    
    all_feeds_rows = await conn.fetch('SELECT id, name, url, category, "isActive", priority, retention_days FROM feeds')
    
    feeds_by_category = {}
    for row in all_feeds_rows:
        category = row['category']
        if category not in feeds_by_category:
            feeds_by_category[category] = []
        feeds_by_category[category].append({
            "id": row['id'],
            "name": row['name'],
            "url": row['url'],
            "isActive": row['isActive'],
            "priority": row['priority'],
            "retention_days": row['retention_days']
        })
        
    for category in feeds_by_category:
        feeds_by_category[category].sort(key=lambda x: x['priority'])
        
    feeds_config = {}
    for category_name in ordered_categories:
        if category_name in feeds_by_category:
            feeds_config[category_name] = feeds_by_category[category_name]

    await conn.close()
    return JSONResponse(content=feeds_config)

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
            return JSONResponse({"message": "Feed configuration updated successfully"})

        except Exception as e:
            logging.exception("Error updating feed configuration in DB: %s", str(e))
            return JSONResponse({"error": "Failed to update configuration in database"}, status_code=500)
        finally:
            await conn.close()

    except Exception as e:
        logging.exception("Error processing request for feed configuration update: %s", str(e))
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/feeds")
async def feeds(days: int = Query(2, description="Number of days back to fetch articles for.", ge=1, le=30)):
    conn = await get_db_connection()
    
    try:
        ordered_categories_rows = await conn.fetch("SELECT name FROM categories ORDER BY priority")
        ordered_categories = [row['name'] for row in ordered_categories_rows]
            
        categories_list = []
        for category in ordered_categories:
            articles = await get_articles_for_category_db(category, days=days)
            if articles:
                categories_list.append({"category": category, "feed_items": articles})
                
        return JSONResponse(content=categories_list)
        
    finally:
        await conn.close()

@app.post("/api/add-feed")
async def add_feed(request: Request):
    """Add a custom RSS feed to the database"""
    try:
        body = await request.json()
        url = body.get("url", "").strip()
        category_name = body.get("category", "").strip()
        name = body.get("name", "").strip()
        retention_days = body.get("retention_days") # Can be None
        
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
                INSERT INTO feeds (name, url, category, "isActive", priority, retention_days)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (url) DO NOTHING;
                """,
                feed_name, url, category_name, True, max_priority + 1, retention_days
            )
            if result == 'INSERT 0 0':
                return JSONResponse({"error": "Feed with this URL already exists"}, status_code=400)

            feed_id = await conn.fetchval("SELECT id FROM feeds WHERE url = $1", url)
            await parse_and_store_rss_feed(feed_id, url, category_name, feed_name)
            
            return JSONResponse({"message": "Feed added successfully", "category": category_name, "url": url})

        except asyncpg.PostgresError as e:
            logging.exception("Database error adding feed: %s", str(e))
            return JSONResponse({"error": "Database error"}, status_code=500)
        finally:
            await conn.close()

    except Exception as e:
        logging.exception("Error adding feed: %s", str(e))
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/article-full-text")
async def article_full_text(url: str):
    try:
        conn = await get_db_connection()
        content = await conn.fetchval('SELECT content FROM "YouTube-articles" WHERE link = $1', url)
        await conn.close()
        if content:
            rendered_html = markdown2.markdown(content)
            return JSONResponse({"content": rendered_html})
        else:
            a = await run_in_threadpool(lambda: Article(url, keep_article_html=True))
            await run_in_threadpool(a.download)
            await run_in_threadpool(a.parse)
            content_html = a.article_html.strip() if a.article_html else ""
            if not content_html:
                content_html = "<p>" + a.text.replace("\n", "</p><p>") + "</p>"
            return JSONResponse({"content": content_html})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/article-full-html")
async def article_full_html(url: str):
    try:
        a = await run_in_threadpool(lambda: Article(url, keep_article_html=True))
        await run_in_threadpool(a.download)
        await run_in_threadpool(a.parse)
        content_html = a.article_html.strip() if a.article_html else ""
        if not content_html:
            content_html = "<p>" + a.text.replace("\n", "</p><p>") + "</p>"
        return JSONResponse({"html": content_html})
    except Exception as e:
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

        if not all([name, url, category]):
            raise HTTPException(status_code=400, detail="Name, URL, and category are required.")

        conn = await get_db_connection()
        await conn.execute(
            'UPDATE feeds SET name = $1, url = $2, category = $3, priority = $4, retention_days = $5 WHERE id = $6',
            name, url, category, priority, retention_days, feed_id
        )
        await conn.close()
        return JSONResponse({"message": "Feed updated successfully."})
    except Exception as e:
        logging.error(f"Error updating feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/feed/{feed_id}")
async def delete_feed(feed_id: int):
    """Delete a feed."""
    try:
        conn = await get_db_connection()
        await conn.execute('DELETE FROM feeds WHERE id = $1', (feed_id,))
        await conn.close()
        return JSONResponse({"message": "Feed deleted successfully."})
    except Exception as e:
        logging.error(f"Error deleting feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/categories")
async def get_categories():
    """Get all categories, ordered by priority."""
    conn = await get_db_connection()
    rows = await conn.fetch("SELECT id, name, priority, is_default FROM categories ORDER BY priority")
    categories = [{"id": row['id'], "name": row['name'], "priority": row['priority'], "is_default": row['is_default']} for row in rows]
    await conn.close()
    return JSONResponse(content=categories)

@app.put("/api/categories/order")
async def update_category_order(request: Request):
    """Update the priority order of categories."""
    try:
        categories_order = await request.json() # Expects a list of category IDs in the new order
        conn = await get_db_connection()
        for index, category_id in enumerate(categories_order):
            await conn.execute("UPDATE categories SET priority = $1 WHERE id = $2", index, category_id)
        await conn.close()
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
        await conn.close()
        return JSONResponse({"message": "Default category updated."})
    except Exception as e:
        logging.error(f"Error setting default category: {e}")
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
        
        await conn.close()
        return JSONResponse({"message": f"Category '{category_name}' and its feeds have been deleted."})
    except Exception as e:
        logging.error(f"Error deleting category: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/feeds/column", response_class=HTMLResponse)
async def feeds_column(request: Request):
    conn = await get_db_connection()
    categories_rows = await conn.fetch("SELECT name FROM categories ORDER BY priority")
    categories = [row['name'] for row in categories_rows]
    await conn.close()

    categories_list = []
    for category in categories:
        articles = await get_articles_for_category_db(category, days=2)
        categories_list.append({"category": category, "feed_items": articles})
    return templates.TemplateResponse("feeds-split.html", {"request": request, "categories": categories_list})

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

#######trends###########################################################################################

@app.get("/api/trends")
async def trends(source: str = "reddit"):
    if source == "twitter":
        channels = []
    else:
        feeds = RSS_FEED_URLS.get(source, next(iter(RSS_FEED_URLS.values())))
        channels = []
        for feed in feeds:
            items = await parse_rss_feed(feed["url"], feed["name"])
            channels.append({"name": feed["name"], "feed_items": items})
    
    response_data = {"source": source, "channels": channels}
    if source == "twitter":
        response_data["nitter_url"] = Config.NITTER_URL
        
    return JSONResponse(content=response_data)
