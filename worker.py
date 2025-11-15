"""
Worker module for RSS feed processing with HTTP caching
Processes feed jobs from Redis queue using RQ
"""

import os
import logging
import time
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import pytz

import feedparser
import httpx
from readability import Document
from dotenv import load_dotenv
import asyncpg
import asyncio

from config import Config
import database
import ai_filter
import keyword_filter
import cache
from youtube_embed import convert_links_to_embeds

load_dotenv()

# Indian Standard Time
IST = pytz.timezone("Asia/Kolkata")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default thumbnail
DEFAULT_THUMBNAIL = "https://via.placeholder.com/400x300.png?text=No+Image"

# Ntfy configuration
NTFY_BASE_URL = os.getenv("NTFY_BASE_URL", "https://ntfy.sh")


def sanitize_text(text):
    """Remove special characters that might cause issues in notifications."""
    if not text:
        return ""
    # Remove or replace problematic characters
    sanitized = text.replace('\n', ' ').replace('\r', '')
    # Remove excessive whitespace
    sanitized = ' '.join(sanitized.split())
    return sanitized


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


async def extract_article_content_with_readability(url: str) -> str:
    """
    Extract article content using readability-lxml.
    
    Args:
        url: Article URL to extract content from
        
    Returns:
        Cleaned HTML content or None on error
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
            return None
        
        return content_html.strip()
        
    except httpx.TimeoutException:
        logger.warning(f"Timeout extracting content from {url}")
        return None
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP error {e.response.status_code} extracting content from {url}")
        return None
    except Exception as e:
        logger.warning(f"Error extracting content with readability for {url}: {e}")
        return None


async def send_ntfy_notification(title: str, link: str, description: str, category: str, source: str):
    """Send ntfy notification for new articles."""
    # Check if ntfy is enabled for this category
    try:
        conn = await database.get_db_connection()
        ntfy_enabled = await conn.fetchval("SELECT ntfy_enabled FROM categories WHERE name = $1", category)
        await database.release_db_connection(conn)
        
        if ntfy_enabled is False:
            logger.debug(f"Ntfy notifications disabled for category: {category}")
            return
    except Exception as e:
        logger.warning(f"Could not check ntfy status for category {category}: {e}")
        return
    
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
        logger.error(f"Failed to send ntfy notification: {e}")
    except Exception as e:
        logger.error(f"Failed to send ntfy notification: {e}")


async def send_telegram_notification(title: str, link: str, description: str, category: str, source: str, thumbnail: str = None):
    """Send notification to Telegram for new articles."""
    # Check if telegram is enabled for this category and get chat_id
    try:
        conn = await database.get_db_connection()
        row = await conn.fetchrow(
            "SELECT telegram_enabled, telegram_chat_id FROM categories WHERE name = $1", 
            category
        )
        await database.release_db_connection(conn)
        
        if not row or row['telegram_enabled'] is False:
            logger.debug(f"Telegram notifications disabled for category: {category}")
            return
        
        chat_id = row['telegram_chat_id']
        if not chat_id:
            logger.debug(f"No Telegram chat ID configured for category: {category}")
            return
            
    except Exception as e:
        logger.warning(f"Could not check telegram status for category {category}: {e}")
        return
    
    # Get bot token from config
    bot_token = Config.TELEGRAM_BOT_TOKEN
    
    if not bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not configured")
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
            logger.debug(f"Telegram notification sent for article: {title}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to send Telegram notification: {e.response.text}")
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")


async def get_feed_last_update(feed_url: str):
    """Get last update timestamp for a feed."""
    return await database.get_feed_last_update(feed_url)


async def update_feed_last_update(feed_url: str, new_update: datetime):
    """Update last update timestamp for a feed."""
    await database.update_feed_last_update(feed_url, new_update)


async def fetch_feed_with_caching(feed_id: int, url: str, etag: str = None, last_modified: str = None):
    """
    Fetch feed with HTTP caching support.
    
    Returns:
        tuple: (content, status_code, new_etag, new_last_modified)
    """
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # Add caching headers if available
    if etag:
        headers['If-None-Match'] = etag
    if last_modified:
        headers['If-Modified-Since'] = last_modified
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=30, follow_redirects=True)
            
            # Check if content hasn't changed (304 Not Modified)
            if resp.status_code == 304:
                logger.info(f"Feed {feed_id} not modified (304), skipping processing")
                return None, 304, etag, last_modified
            
            resp.raise_for_status()
            
            # Extract new caching headers
            new_etag = resp.headers.get('ETag')
            new_last_modified = resp.headers.get('Last-Modified')
            
            return resp.content, resp.status_code, new_etag, new_last_modified
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching feed {feed_id} from {url}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error fetching feed {feed_id} from {url}: {e}")
        raise


async def parse_and_store_rss_feed(feed_id: int, rss_url: str, category: str, source_name: str, 
                                   etag: str = None, last_modified: str = None, fetch_full_content: bool = False):
    """
    Parse and store RSS feed articles with HTTP caching support.
    
    Args:
        fetch_full_content: If True, extract full article content using readability. If False, only store feed summary.
    
    Returns:
        tuple: (new_etag, new_last_modified, articles_added)
    """
    logger.info(f"Processing feed: {source_name} (ID: {feed_id}), full_content={fetch_full_content}")
    
    try:
        # Fetch feed with caching
        content, status_code, new_etag, new_last_modified = await fetch_feed_with_caching(
            feed_id, rss_url, etag, last_modified
        )
        
        # If 304, feed hasn't changed
        if status_code == 304:
            return new_etag, new_last_modified, 0
        
        # Parse feed
        feed = feedparser.parse(content)
        
        last_update = await get_feed_last_update(rss_url)
        threshold = last_update if last_update else datetime.now(IST) - timedelta(days=10)
        new_last_update = last_update or threshold
        
        conn = await database.get_db_connection()
        articles_added = 0
        new_articles = []  # For batched notifications
        
        try:
            for entry in feed.entries:
                title = getattr(entry, "title", "Untitled")
                link = getattr(entry, "link", "#")
                description = getattr(entry, "summary", "No description available.")
                
                # Extract thumbnail
                thumbnail_url = DEFAULT_THUMBNAIL
                if "media_thumbnail" in entry:
                    thumbnail_url = entry.media_thumbnail[0].get("url")
                elif "media_content" in entry:
                    thumbnail_url = entry.media_content[0].get("url")
                
                # Parse published date
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
                
                # Skip old articles
                if not pub_dt or pub_dt <= threshold:
                    continue
                
                if pub_dt > new_last_update:
                    new_last_update = pub_dt
                
                # Check if article already exists
                if await conn.fetchval('SELECT id FROM articles WHERE link = $1', link):
                    continue
                
                # Conditionally extract full article content based on fetch_full_content flag
                article_content = None
                if fetch_full_content:
                    try:
                        article_content = await extract_article_content_with_readability(link)
                        if article_content:
                            logger.debug(f"Extracted full content for: {title}")
                        else:
                            logger.warning(f"No content extracted for {link}")
                    except Exception as e:
                        logger.warning(f"Error extracting content for {link}: {e}")
                        article_content = None
                if description:
                    description = convert_links_to_embeds(description)
                if article_content:
                    article_content = convert_links_to_embeds(article_content)
                
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
                logger.info(f"Added article: {title}")
                
                # Add to new articles list for batched notification
                new_articles.append({
                    'title': title,
                    'link': link,
                    'description': description,
                    'thumbnail': thumbnail_url
                })
                
                # Process with AI filter if enabled for this category
                try:
                    await ai_filter.process_new_article(article_id, category, conn)
                except Exception as e:
                    logger.warning(f"AI filter processing failed for article {article_id}: {e}")
                
                # Process with keyword/topic filters
                try:
                    await keyword_filter.process_article_filters(
                        article_id, title, link, description, article_content, 
                        category, source_name, conn
                    )
                except Exception as e:
                    logger.warning(f"Keyword filter processing failed for article {article_id}: {e}")
            
            # Send batched notifications after processing all articles
            if new_articles:
                try:
                    # Send single consolidated notification
                    batch_title = f"{source_name}: {len(new_articles)} new article{'s' if len(new_articles) > 1 else ''}"
                    batch_description = f"Latest: {new_articles[0]['title']}"
                    batch_link = new_articles[0]['link']
                    
                    await send_ntfy_notification(batch_title, batch_link, batch_description, category, source_name)
                    await send_telegram_notification(batch_title, batch_link, batch_description, category, source_name, new_articles[0]['thumbnail'])
                    logger.info(f"Sent batched notification for {len(new_articles)} articles from {source_name}")
                except Exception as e:
                    logger.error(f"Error sending batched notifications: {e}")
            
            # Update feed state
            if new_last_update > threshold:
                await update_feed_last_update(rss_url, new_last_update)
                logger.info(f"Updated feed state for {source_name}")
                
                # Invalidate feed caches
                cache.invalidate_feeds_cache()
        
        finally:
            await database.release_db_connection(conn)
        
        logger.info(f"Completed processing feed {source_name}: {articles_added} new articles")
        return new_etag, new_last_modified, articles_added
        
    except Exception as e:
        logger.exception(f"Error processing feed {source_name} (ID: {feed_id}): {e}")
        raise


def process_feed_job(feed_id: int, name: str, url: str, category: str, 
                     polling_interval: int, etag: str = None, last_modified: str = None, fetch_full_content: bool = False):
    """
    RQ job function to process a single feed.
    This is the main entry point called by RQ workers.
    
    Args:
        feed_id: Feed database ID
        name: Feed name
        url: Feed URL
        category: Feed category
        polling_interval: Polling interval in minutes
        etag: Current ETag header value
        last_modified: Current Last-Modified header value
        fetch_full_content: Whether to extract full article content
    """
    logger.info(f"Starting job for feed: {name} (ID: {feed_id})")
    start_time = datetime.now(IST)
    
    try:
        # Run async function in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Initialize database pool
            loop.run_until_complete(database.init_db_pool())
            
            # Process feed
            new_etag, new_last_modified, articles_added = loop.run_until_complete(
                parse_and_store_rss_feed(feed_id, url, category, name, etag, last_modified, fetch_full_content)
            )
            
            # Update feed metadata in database
            conn = loop.run_until_complete(database.get_db_connection())
            try:
                # Calculate next check time
                next_check = datetime.now(IST) + timedelta(minutes=polling_interval)
                
                # Update feed with new caching headers and next check time
                await_result = loop.run_until_complete(conn.execute(
                    """
                    UPDATE feeds 
                    SET etag_header = $1, last_modified_header = $2, next_check_at = $3
                    WHERE id = $4
                    """,
                    new_etag, new_last_modified, next_check, feed_id
                ))
                
                logger.info(f"Updated feed {feed_id} metadata: next_check_at={next_check}")
                
            finally:
                loop.run_until_complete(database.release_db_connection(conn))
            
            end_time = datetime.now(IST)
            duration = (end_time - start_time).total_seconds()
            logger.info(f"Completed job for feed {name}: {articles_added} articles in {duration:.2f}s")
            
            return {
                'feed_id': feed_id,
                'feed_name': name,
                'articles_added': articles_added,
                'duration': duration,
                'cached': articles_added == 0 and new_etag == etag
            }
            
        finally:
            loop.run_until_complete(database.close_db_pool())
            loop.close()
            
    except Exception as e:
        logger.exception(f"Job failed for feed {name} (ID: {feed_id}): {e}")
        raise


if __name__ == "__main__":
    # This allows testing the worker directly
    print("RSS Feed Worker - Use 'rq worker' to start processing jobs")
