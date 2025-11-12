"""
Database module for RSS Newsapp
Handles all database connections, schema initialization, and database utilities
"""

import logging
import json
from datetime import datetime
import pytz
import asyncpg

from config import Config

# Indian Standard Time
IST = pytz.timezone("Asia/Kolkata")

logger = logging.getLogger(__name__)

# Global connection pool
_db_pool = None

# --- Database Connection ---

async def init_db_pool():
    """Initialize database connection pool"""
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(
            database=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            min_size=5,
            max_size=50,  # Increased for high-volume feed processing
            command_timeout=60
        )
        logger.info("Database connection pool initialized")
    return _db_pool

async def close_db_pool():
    """Close database connection pool"""
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None
        logger.info("Database connection pool closed")

async def get_db_connection():
    """Get database connection from pool"""
    if _db_pool is None:
        await init_db_pool()
    # Use async with to properly acquire connection from pool
    return await _db_pool.acquire()

async def release_db_connection(conn):
    """Release database connection back to pool"""
    if _db_pool and conn:
        await _db_pool.release(conn)

# --- Database Initialization ---

async def init_db():
    """
    Initialize all database tables with complete schemas.
    For Docker deployments, all columns are included in CREATE TABLE statements.
    No separate ALTER TABLE migrations needed.
    """
    conn = await get_db_connection()
    
    try:
        # Categories table - includes ntfy_enabled, telegram_enabled, ai_prompt, ai_enabled
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                priority INTEGER DEFAULT 0,
                is_default BOOLEAN DEFAULT false,
                ntfy_enabled BOOLEAN DEFAULT true,
                telegram_enabled BOOLEAN DEFAULT false,
                telegram_chat_id TEXT DEFAULT NULL,
                ai_prompt TEXT DEFAULT NULL,
                ai_enabled BOOLEAN DEFAULT false
            );
        """)
        logger.info("Categories table initialized")
        
        # Feeds table - includes display_order, retention_days, polling_interval
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS feeds (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                "isActive" BOOLEAN DEFAULT true,
                priority INTEGER DEFAULT 0,
                retention_days INTEGER,
                display_order INTEGER DEFAULT 0,
                polling_interval INTEGER DEFAULT 60
            );
        """)
        logger.info("Feeds table initialized")
        
        # Articles table - includes starred, feed_id
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
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
                feed_id INTEGER REFERENCES feeds(id) ON DELETE CASCADE,
                starred BOOLEAN DEFAULT false,
                feed_url TEXT
            );
        """)
        logger.info("Articles table initialized")
        
        # Feed state tracking
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS "FeedState" (
                feed_url TEXT PRIMARY KEY,
                last_update TIMESTAMPTZ
            );
        """)
        logger.info("FeedState table initialized")
        
        # User settings
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        logger.info("User settings table initialized")
        
        # User article status (read/unread tracking)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_article_status (
                article_link TEXT PRIMARY KEY,
                is_read BOOLEAN DEFAULT true NOT NULL,
                read_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("User article status table initialized")
        
        # Report schedules table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS report_schedules (
                id SERIAL PRIMARY KEY,
                category TEXT NOT NULL,
                schedule_type TEXT NOT NULL CHECK (schedule_type IN ('daily', 'weekly')),
                schedule_hour INTEGER DEFAULT 0 CHECK (schedule_hour >= 0 AND schedule_hour < 24),
                schedule_minute INTEGER DEFAULT 0 CHECK (schedule_minute >= 0 AND schedule_minute < 60),
                enabled BOOLEAN DEFAULT true,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(category, schedule_type)
            );
        """)
        logger.info("Report schedules table initialized")
        
        # Article AI matches table (for AI content filtering)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS article_ai_matches (
                id SERIAL PRIMARY KEY,
                article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                matched_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                prompt_hash TEXT NOT NULL,
                UNIQUE(article_id, category_id)
            );
        """)
        logger.info("Article AI matches table initialized")
        
        # Create indexes for article_ai_matches
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_article_ai_matches_article 
            ON article_ai_matches(article_id);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_article_ai_matches_category 
            ON article_ai_matches(category_id);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_article_ai_matches_prompt_hash 
            ON article_ai_matches(prompt_hash);
        """)
        logger.info("Article AI matches indexes created")
        
        # Article filters table (for keyword/topic-based filtering)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS article_filters (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
                filter_type TEXT NOT NULL CHECK (filter_type IN ('keyword', 'topic')),
                filter_value TEXT NOT NULL,
                auto_star BOOLEAN DEFAULT true,
                auto_notify BOOLEAN DEFAULT true,
                enabled BOOLEAN DEFAULT true,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Article filters table initialized")
        
        # Create indexes for article_filters
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_article_filters_category 
            ON article_filters(category_id);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_article_filters_enabled 
            ON article_filters(enabled);
        """)
        logger.info("Article filters indexes created")
        
        # Article filter matches table (tracks which filters matched which articles)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS article_filter_matches (
                id SERIAL PRIMARY KEY,
                article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                filter_id INTEGER NOT NULL REFERENCES article_filters(id) ON DELETE CASCADE,
                matched_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(article_id, filter_id)
            );
        """)
        logger.info("Article filter matches table initialized")
        
        # Create indexes for article_filter_matches
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_article_filter_matches_article 
            ON article_filter_matches(article_id);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_article_filter_matches_filter 
            ON article_filter_matches(filter_id);
        """)
        logger.info("Article filter matches indexes created")
        
        # Add auto_starred_by column to articles if it doesn't exist
        try:
            await conn.execute("""
                ALTER TABLE articles 
                ADD COLUMN IF NOT EXISTS auto_starred_by INTEGER REFERENCES article_filters(id) ON DELETE SET NULL;
            """)
            logger.info("Added auto_starred_by column to articles table")
        except Exception as e:
            logger.debug(f"auto_starred_by column might already exist: {e}")
        
        # Add telegram_enabled and telegram_chat_id columns to categories if they don't exist
        try:
            await conn.execute("""
                ALTER TABLE categories 
                ADD COLUMN IF NOT EXISTS telegram_enabled BOOLEAN DEFAULT false;
            """)
            await conn.execute("""
                ALTER TABLE categories 
                ADD COLUMN IF NOT EXISTS telegram_chat_id TEXT DEFAULT NULL;
            """)
            logger.info("Added telegram_enabled and telegram_chat_id columns to categories table")
        except Exception as e:
            logger.debug(f"Telegram columns might already exist: {e}")
        
        # Add polling_interval column to feeds if it doesn't exist
        try:
            await conn.execute("""
                ALTER TABLE feeds 
                ADD COLUMN IF NOT EXISTS polling_interval INTEGER DEFAULT 60;
            """)
            logger.info("Added polling_interval column to feeds table")
        except Exception as e:
            logger.debug(f"polling_interval column might already exist: {e}")
        
        # Initialize default timezone setting if not exists
        timezone_exists = await conn.fetchval(
            "SELECT COUNT(*) FROM user_settings WHERE key = 'timezone'"
        )
        if timezone_exists == 0:
            await conn.execute(
                "INSERT INTO user_settings (key, value) VALUES ($1, $2)",
                'timezone', 'Asia/Kolkata'
            )
            logger.info("Default timezone setting initialized")
        
        # Populate feeds from feeds.json if table is empty
        await populate_default_feeds(conn)
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        await release_db_connection(conn)


async def populate_default_feeds(conn):
    """
    Populate feeds and categories from feeds.json if feeds table is empty.
    This runs only on first deployment.
    """
    try:
        feed_count = await conn.fetchval("SELECT COUNT(*) FROM feeds")
        if feed_count == 0:
            logger.info("Feeds table is empty. Populating with default data from feeds.json.")
            
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
                            INSERT INTO feeds (name, url, category, "isActive", priority, display_order)
                            VALUES ($1, $2, $3, $4, $5, $6)
                            ON CONFLICT (url) DO NOTHING;
                            """,
                            feed['name'], 
                            feed['url'], 
                            category, 
                            feed.get('isActive', True), 
                            feed_priority,
                            feed_priority
                        )
                        feed_priority += 1
                
                logger.info("Default feeds and categories populated successfully.")
            except FileNotFoundError:
                logger.warning("feeds.json not found. Skipping default feed population.")
            except Exception as e:
                logger.error(f"Could not populate default data from feeds.json: {e}")
    except Exception as e:
        logger.error(f"Error checking feed count: {e}")


# --- Helper Functions ---

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
    try:
        row = await conn.fetchrow(
            'SELECT last_update FROM "FeedState" WHERE feed_url = $1', 
            feed_url
        )
        if row and row['last_update']:
            return ensure_aware(row['last_update'], IST)
        return None
    finally:
        await release_db_connection(conn)


async def update_feed_last_update(feed_url: str, new_update: datetime):
    """
    Updates (or inserts) the last update timestamp for the given feed.
    """
    new_update = ensure_aware(new_update, IST)
    conn = await get_db_connection()
    try:
        await conn.execute(
            '''
            INSERT INTO "FeedState" (feed_url, last_update)
            VALUES ($1, $2)
            ON CONFLICT (feed_url) DO UPDATE SET last_update = $2
            ''',
            feed_url, new_update
        )
    finally:
        await release_db_connection(conn)
