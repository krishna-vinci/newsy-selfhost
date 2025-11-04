import os
import logging
import re
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import pytz

import feedparser
import requests
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

import psycopg2
from apscheduler.schedulers.background import BackgroundScheduler
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
    # "reddit": [
    #     {
    #         "name": "r/Indiaspeaks",
    #         "url": f"http://{Config.RSSBRIDGE_HOST}/?action=display&bridge=RedditBridge&context=single&r=IndiaSpeaks&f=&score=50&d=hot&search=&frontend=https%3A%2F%2Fold.reddit.com&format=Atom"
    #     },
    #     {
    #         "name": "worldnews",
    #         "url": f"http://{Config.RSSBRIDGE_HOST}/?action=display&bridge=RedditBridge&context=single&r=selfhosted&f=&score=&d=top&search=&frontend=https%3A%2F%2Fold.reddit.com&format=Atom"
    #     },
    # ],
    "youtube": [
        {
            "name": "Prof K Nageshwar",
            "url": f"{Config.RSSBRIDGE_HOST}/?action=display&bridge=YoutubeBridge&context=By+channel+id&c=UCm40kSg56qfys19NtzgXAAg&duration_min=2&duration_max=&format=Atom"
        },
        {
            "name": "Prasadtech",
            "url": f"{Config.RSSBRIDGE_HOST}/?action=display&bridge=YoutubeBridge&context=By+channel+id&c=UCb-xXZ7ltTvrh9C6DgB9H-Q&duration_min=2&duration_max=&format=Atom"
        },
    ],
    # "twitter": [
    #     {
    #         "name": "Twitter Feed",
    #         "url": Config.NITTER_URL
    #     }
    # ]
}

FEED_CATEGORIES = {
    "World Tech": [
        {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index/"},
        {"name": "Wired", "url": "https://www.wired.com/feed/rss"},
        {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
        {"name": "IEEE Spectrum", "url": "https://spectrum.ieee.org/rss/fulltext"},
        {"name": "TechRadar", "url": "https://www.techradar.com/rss"}
    ],

    "India Tech": [
        {"name": "Medianama", "url": "https://www.medianama.com/feed/"},
        {"name": "Business Standard – Tech", "url": "https://www.business-standard.com/rss/technology-108.rss"}
    ],

    "World News": [
        {"name": "Reuters World", "url": "https://www.reutersagency.com/feed/?best-topics=world"},
        {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"}
    ],

    "India News": [
        {"name": "The Hindu", "url": "https://www.thehindu.com/news/?service=rss"},
        {"name": "Indian Express Explained", "url": "https://indianexpress.com/section/explained/feed/"}
    ],

    "World Commentary": [
        {"name": "Foreign Affairs", "url": "https://www.foreignaffairs.com/rss.xml"},
        {"name": "The Atlantic – Ideas", "url": "https://www.theatlantic.com/feed/channel/ideas/"},
        {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/feed/"},
        {"name": "The Economist", "url": "https://www.economist.com/latest/rss.xml"}
    ],

    "India Commentary": [
        {"name": "The Print – Opinion", "url": "https://theprint.in/category/opinion/feed/"},
        {"name": "Scroll.in – Featured", "url": "https://scroll.in/feed"}
    ]
}




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
def get_db_connection():
    conn_str = f"dbname={Config.DB_NAME} user={Config.DB_USER} password={Config.DB_PASSWORD} host={Config.DB_HOST} port={Config.DB_PORT}"
    return psycopg2.connect(conn_str)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS "YouTube-articles" (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        link TEXT UNIQUE NOT NULL,
        description TEXT,
        thumbnail TEXT,
        published TEXT,
        published_datetime TIMESTAMP,
        category TEXT,
        content TEXT,
        source TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS "FeedState" (
         feed_url TEXT PRIMARY KEY,
         last_update TIMESTAMP
    );
    """)
    conn.commit()
    cur.close()
    conn.close()


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
def get_feed_last_update(feed_url: str):
    """
    Retrieves the last update timestamp for the given feed.
    Ensures that the returned datetime is timezone-aware.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT last_update FROM "FeedState" WHERE feed_url = %s', (feed_url,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return ensure_aware(row[0], IST)
    else:
        return None

def update_feed_last_update(feed_url: str, new_update: datetime):
    """
    Updates (or inserts) the last update timestamp for the given feed.
    """
    new_update = ensure_aware(new_update, IST)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO "FeedState" (feed_url, last_update) VALUES (%s, %s) ON CONFLICT (feed_url) DO UPDATE SET last_update = EXCLUDED.last_update',
        (feed_url, new_update)
    )
    conn.commit()
    cur.close()
    conn.close()




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

def send_ntfy_notification(title: str, link: str, description: str, category: str, source: str):
    title = sanitize_text(title)
    topic = f"feeds-{category.lower().replace(' ', '-')}"
    ntfy_url = f"{NTFY_BASE_URL}/{topic}"

    headers = {
        "Title": title,
        "Click": link,
    }

    payload = f"{description[:160]}... (via {source})"

    try:
        response = requests.post(ntfy_url, headers=headers, data=payload.encode('utf-8'))
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
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
import requests
import feedparser
from dateutil import parser as date_parser
from newspaper import Article

# Indian Standard Time
IST = pytz.timezone("Asia/Kolkata")

def format_datetime(dt_input):
    """
    Accepts either:
      • a timezone-aware datetime, or
      • a date-string parsable by dateutil
    Returns:
      - "Today at HH:MM AM/PM"
      - "Yesterday at HH:MM AM/PM"
      - "Mon DD, YYYY - HH:MM AM/PM"
      - or "No Date"
    """
    # datetime path
    if isinstance(dt_input, datetime):
        dt = dt_input if dt_input.tzinfo else IST.localize(dt_input)
    else:
        # string path
        try:
            dt = date_parser.parse(dt_input)
            dt = dt if dt.tzinfo else IST.localize(dt)
        except Exception:
            return "No Date"

    now = datetime.now(IST)
    yesterday = now - timedelta(days=1)

    if dt.date() == now.date():
        return dt.strftime("Today at %I:%M %p")
    elif dt.date() == yesterday.date():
        return dt.strftime("Yesterday at %I:%M %p")
    else:
        return dt.strftime("%b %d, %Y - %I:%M %p")


def parse_and_store_rss_feed(rss_url: str, category: str, source_name: str = "Unknown"):
    logging.debug("Parsing feed URL: %s for category: %s", rss_url, category)
    try:
        # 1) fetch + parse
        resp = requests.get(rss_url, headers={'User-Agent':'Mozilla/5.0'}, timeout=10)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)

        # 2) threshold (unchanged)
        last_update = get_feed_last_update(rss_url)
        threshold = last_update if last_update else datetime.now(IST) - timedelta(days=2)
        new_last_update = threshold

        conn = get_db_connection()
        cur = conn.cursor()

        for entry in feed.entries:
            title       = getattr(entry, "title", "Untitled")
            link        = getattr(entry, "link", "#")
            description = getattr(entry, "summary", "No description available.")

            # 3) thumbnail (unchanged)
            thumbnail_url = DEFAULT_THUMBNAIL
            if "media_thumbnail" in entry:
                thumbnail_url = entry.media_thumbnail[0].get("url")
            elif "media_content" in entry:
                thumbnail_url = entry.media_content[0].get("url")

            # 4) FORMAT FOR DISPLAY (exactly as before)
            raw_published = getattr(entry, "published", None) or getattr(entry, "updated", None)
            published_formatted = format_datetime(raw_published)

            # 5) DETERMINE pub_dt for STORAGE & THRESHOLD
            struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
            if struct:
                # struct_time is UTC
                dt_utc = datetime.fromtimestamp(time.mktime(struct), tz=pytz.utc)
                pub_dt = dt_utc.astimezone(IST)
            else:
                # fallback to parsing raw string
                try:
                    pub_dt = date_parser.parse(raw_published) if raw_published else None
                    pub_dt = pub_dt if pub_dt and pub_dt.tzinfo else (IST.localize(pub_dt) if pub_dt else None)
                except Exception:
                    pub_dt = None

            # 6) skip old or undated entries
            if not pub_dt or pub_dt <= threshold:
                continue

            # 7) track newest time
            if pub_dt > new_last_update:
                new_last_update = pub_dt

            # 8) dedupe
            cur.execute('SELECT id FROM "YouTube-articles" WHERE link = %s', (link,))
            if cur.fetchone():
                continue

            # 9) fetch full content
            try:
                art = Article(link, keep_article_html=True)
                art.download(); art.parse()
                article_content = art.article_html or art.text
            except Exception:
                logging.exception("Error extracting content for %s", link)
                article_content = None

            # 10) insert
            cur.execute(
                'INSERT INTO "YouTube-articles" '
                '(title, link, description, thumbnail, published, published_datetime, category, content, source) '
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)',
                (title, link, description, thumbnail_url,
                 published_formatted, pub_dt, category, article_content, source_name)
            )
            conn.commit()

            # 11) notify
            send_ntfy_notification(title, link, description, category, source_name)

        cur.close()
        conn.close()

        # 12) update feed‐state
        if new_last_update > threshold:
            update_feed_last_update(rss_url, new_last_update)
            logging.info("Updated feed state for %s → %s", rss_url, new_last_update)

    except Exception as e:
        logging.exception("Error parsing/storing feed for URL: %s | Error: %s", rss_url, e)


def fetch_all_feeds_db():
    start_time = datetime.now(IST)
    logging.info("Feed update started at %s", start_time)
    for category, feeds in FEED_CATEGORIES.items():
        for feed in feeds:
            logging.info("Processing feed: '%s' for category: '%s'", feed.get("name"), category)
            try:
                parse_and_store_rss_feed(feed["url"], category, source_name=feed.get("name", "Unknown"))
            except Exception as e:
                logging.exception("Error processing feed '%s' for category '%s': %s", feed.get("name"), category, e)
    end_time = datetime.now(IST)
    logging.info("Feed update completed at %s", end_time)


if __name__ == "__main__":
    fetch_all_feeds_db()

def get_articles_for_category_db(category: str, days: int = 2):
     threshold = datetime.now(IST) - timedelta(days=days)
     conn = get_db_connection()
     cur = conn.cursor()
     cur.execute(
         'SELECT title, link, description, thumbnail, published, published_datetime, category, content, source FROM "YouTube-articles" WHERE category = %s AND published_datetime >= %s ORDER BY published_datetime DESC',
         (category, threshold)
     )
     rows = cur.fetchall()
     articles = []
     for row in rows:
         # Convert datetime to ISO format string for JSON serialization
         pub_dt = row[5]
         pub_dt_str = pub_dt.isoformat() if pub_dt else None
         
         articles.append({
             "title": row[0],
             "link": row[1],
             "description": row[2],
             "thumbnail": row[3],
             "published": row[4],
             "published_datetime": pub_dt_str,
             "category": row[6],
             "content": row[7],
             "source": row[8] or "Unknown"
         })
     cur.close()
     conn.close()
     return articles




scheduler = BackgroundScheduler()
@app.on_event("startup")
async def startup_event():
    FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")
    init_db()
    fetch_all_feeds_db()
    scheduler.add_job(fetch_all_feeds_db, 'interval', minutes=1)
    scheduler.start()

def parse_rss_feed(rss_url: str):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(rss_url, headers=headers, timeout=10)
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
        published = format_datetime(raw_published)
        items.append({
            "title": title,
            "link": link,
            "description": description,
            "thumbnail": thumbnail_url,
            "published": published
        })
    return items

@app.get("/api/feeds")
async def feeds():
    categories_list = []
    for category in FEED_CATEGORIES.keys():
        articles = get_articles_for_category_db(category, days=2)
        categories_list.append({"category": category, "feed_items": articles})
    return JSONResponse(content=categories_list)

@app.get("/article-full-text")
async def article_full_text(url: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT content FROM "YouTube-articles" WHERE link = %s', (url,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row[0]:
            rendered_html = markdown2.markdown(row[0])
            return JSONResponse({"content": rendered_html})
        else:
            a = Article(url, keep_article_html=True)
            a.download()
            a.parse()
            content_html = a.article_html.strip() if a.article_html else ""
            if not content_html:
                content_html = "<p>" + a.text.replace("\n", "</p><p>") + "</p>"
            return JSONResponse({"content": content_html})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/article-full-html")
async def article_full_html(url: str):
    try:
        a = Article(url, keep_article_html=True)
        a.download()
        a.parse()
        content_html = a.article_html.strip() if a.article_html else ""
        if not content_html:
            content_html = "<p>" + a.text.replace("\n", "</p><p>") + "</p>"
        return JSONResponse({"html": content_html})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/feeds/column", response_class=HTMLResponse)
async def feeds_column(request: Request):
    categories_list = []
    for category in FEED_CATEGORIES.keys():
        articles = get_articles_for_category_db(category, days=2)
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
        # Use first available feed list as fallback if source not found
        feeds = RSS_FEED_URLS.get(source, next(iter(RSS_FEED_URLS.values())))
        channels = []
        for feed in feeds:
            items = parse_rss_feed(feed["url"])
            channels.append({"name": feed["name"], "feed_items": items})
    
    response_data = {"source": source, "channels": channels}
    if source == "twitter":
        response_data["nitter_url"] = Config.NITTER_URL
        
    return JSONResponse(content=response_data)
