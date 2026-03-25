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
            command_timeout=60,
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

        # Feeds table - includes display_order, retention_days, polling_interval, scalability columns, fetch_full_content
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
                polling_interval INTEGER DEFAULT 60,
                next_check_at TIMESTAMPTZ DEFAULT NOW(),
                etag_header TEXT,
                last_modified_header TEXT,
                fetch_full_content BOOLEAN DEFAULT false
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

        # Users table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                email TEXT,
                password_hash TEXT,
                role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user')),
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_login_at TIMESTAMPTZ
            );
        """)
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_lower
            ON users ((LOWER(username)));
        """)
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower
            ON users ((LOWER(email)))
            WHERE email IS NOT NULL;
        """)
        logger.info("Users table initialized")

        # Refresh sessions for rotated login sessions
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS refresh_sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                refresh_token_hash TEXT NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                revoked_at TIMESTAMPTZ,
                ip_address TEXT,
                user_agent TEXT,
                device_label TEXT
            );
        """)
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_refresh_sessions_token_hash
            ON refresh_sessions (refresh_token_hash);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_refresh_sessions_user_id
            ON refresh_sessions (user_id);
        """)
        logger.info("Refresh sessions table initialized")

        # OAuth/identity extension point for future providers
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS auth_identities (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                provider_key TEXT NOT NULL,
                provider_subject TEXT NOT NULL,
                provider_email TEXT,
                provider_username TEXT,
                raw_profile_json JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(provider_key, provider_subject)
            );
        """)
        logger.info("Auth identities table initialized")

        # Per-user app preferences
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
                default_view TEXT NOT NULL DEFAULT 'card' CHECK (default_view IN ('card', 'headline', 'column')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        logger.info("User preferences table initialized")

        # User article status (read/unread tracking)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_article_status (
                article_link TEXT PRIMARY KEY,
                is_read BOOLEAN DEFAULT true NOT NULL,
                read_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("User article status table initialized")

        # Per-user read/unread tracking
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_article_state (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                article_link TEXT NOT NULL,
                is_read BOOLEAN NOT NULL DEFAULT true,
                read_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, article_link)
            );
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_article_state_user_id
            ON user_article_state (user_id);
        """)
        logger.info("User article state table initialized")

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
            logger.info(
                "Added telegram_enabled and telegram_chat_id columns to categories table"
            )
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

        # Add scalability columns to feeds if they don't exist
        try:
            await conn.execute("""
                ALTER TABLE feeds 
                ADD COLUMN IF NOT EXISTS next_check_at TIMESTAMPTZ DEFAULT NOW();
            """)
            await conn.execute("""
                ALTER TABLE feeds 
                ADD COLUMN IF NOT EXISTS checked_at TIMESTAMPTZ DEFAULT NOW();
            """)
            await conn.execute("""
                ALTER TABLE feeds 
                ADD COLUMN IF NOT EXISTS etag_header TEXT;
            """)
            await conn.execute("""
                ALTER TABLE feeds 
                ADD COLUMN IF NOT EXISTS last_modified_header TEXT;
            """)
            await conn.execute("""
                ALTER TABLE feeds 
                ADD COLUMN IF NOT EXISTS parsing_error_count INTEGER DEFAULT 0;
            """)
            await conn.execute("""
                ALTER TABLE feeds 
                ADD COLUMN IF NOT EXISTS parsing_error_msg TEXT DEFAULT '';
            """)
            logger.info(
                "Added scalability columns (next_check_at, checked_at, etag_header, last_modified_header, parsing_error_count, parsing_error_msg) to feeds table"
            )
        except Exception as e:
            logger.debug(f"Scalability columns might already exist: {e}")

        # Add fetch_full_content column to feeds if it doesn't exist
        try:
            await conn.execute("""
                ALTER TABLE feeds 
                ADD COLUMN IF NOT EXISTS fetch_full_content BOOLEAN DEFAULT false;
            """)
            logger.info("Added fetch_full_content column to feeds table")
        except Exception as e:
            logger.debug(f"fetch_full_content column might already exist: {e}")

        # Add per-user ownership and id-based relation columns for user isolation
        migration_statements = [
            "ALTER TABLE categories ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE",
            "ALTER TABLE feeds ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE",
            "ALTER TABLE feeds ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE",
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL",
            "ALTER TABLE report_schedules ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE",
            "ALTER TABLE report_schedules ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE",
            "ALTER TABLE article_ai_matches ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE",
            "ALTER TABLE article_filters ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE",
            "ALTER TABLE article_filter_matches ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE",
            "ALTER TABLE user_article_state ADD COLUMN IF NOT EXISTS article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE",
            "ALTER TABLE user_article_state ADD COLUMN IF NOT EXISTS is_saved BOOLEAN NOT NULL DEFAULT false",
            "ALTER TABLE user_article_state ADD COLUMN IF NOT EXISTS saved_at TIMESTAMPTZ",
        ]
        for statement in migration_statements:
            try:
                await conn.execute(statement)
            except Exception as e:
                logger.debug(
                    f"Ownership migration statement failed or already applied: {statement} | {e}"
                )

        # Per-user notification history (channel configuration stays on categories for now)
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_notifications (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
                channel TEXT NOT NULL,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT,
                link TEXT,
                is_read BOOLEAN NOT NULL DEFAULT false,
                sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_notifications_user_id
            ON user_notifications (user_id, sent_at DESC)
            """
        )

        # Relax old global uniqueness so multiple users can own equivalent content.
        for drop_statement in [
            "ALTER TABLE categories DROP CONSTRAINT IF EXISTS categories_name_key",
            "ALTER TABLE feeds DROP CONSTRAINT IF EXISTS feeds_url_key",
            "ALTER TABLE articles DROP CONSTRAINT IF EXISTS articles_link_key",
            "ALTER TABLE report_schedules DROP CONSTRAINT IF EXISTS report_schedules_category_schedule_type_key",
        ]:
            try:
                await conn.execute(drop_statement)
            except Exception as e:
                logger.debug(
                    f"Could not drop legacy constraint: {drop_statement} | {e}"
                )

        index_statements = [
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_user_name_lower ON categories (user_id, LOWER(name)) WHERE user_id IS NOT NULL",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_feeds_user_url ON feeds (user_id, url) WHERE user_id IS NOT NULL",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_user_link ON articles (user_id, link) WHERE user_id IS NOT NULL",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_report_schedules_user_category_type ON report_schedules (user_id, category_id, schedule_type) WHERE user_id IS NOT NULL AND category_id IS NOT NULL",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_article_state_user_article_id ON user_article_state (user_id, article_id) WHERE article_id IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_categories_user_id ON categories (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_feeds_user_id ON feeds (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_feeds_category_id ON feeds (category_id)",
            "CREATE INDEX IF NOT EXISTS idx_articles_user_id ON articles (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_articles_category_id ON articles (category_id)",
            "CREATE INDEX IF NOT EXISTS idx_report_schedules_user_id ON report_schedules (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_article_ai_matches_user_id ON article_ai_matches (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_article_filters_user_id ON article_filters (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_article_filter_matches_user_id ON article_filter_matches (user_id)",
        ]
        for statement in index_statements:
            try:
                await conn.execute(statement)
            except Exception as e:
                logger.debug(
                    f"Ownership index creation failed or already applied: {statement} | {e}"
                )

        # Initialize default timezone setting if not exists
        timezone_exists = await conn.fetchval(
            "SELECT COUNT(*) FROM user_settings WHERE key = 'timezone'"
        )
        if timezone_exists == 0:
            await conn.execute(
                "INSERT INTO user_settings (key, value) VALUES ($1, $2)",
                "timezone",
                "Asia/Kolkata",
            )
            logger.info("Default timezone setting initialized")

        # Backfill legacy global content to a single owner user if needed.
        await migrate_legacy_user_owned_data(conn)

        logger.info("Database initialization completed successfully")

    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        await release_db_connection(conn)


async def populate_default_feeds_for_user(conn, user_id: int):
    """
    Populate feeds and categories from feeds.json for a specific user.
    This is used after the first account is created.
    """
    try:
        feed_count = await conn.fetchval(
            "SELECT COUNT(*) FROM feeds WHERE user_id = $1",
            user_id,
        )
        if feed_count == 0:
            logger.info(
                "User feed set is empty. Populating with default data from feeds.json."
            )

            try:
                with open("feeds.json", "r") as f:
                    feed_data = json.load(f)

                category_priority = 0
                for category, feeds_list in feed_data.items():
                    category_id = await conn.fetchval(
                        "SELECT id FROM categories WHERE user_id = $1 AND LOWER(name) = LOWER($2)",
                        user_id,
                        category,
                    )
                    if category_id is None:
                        category_id = await conn.fetchval(
                            """
                            INSERT INTO categories (user_id, name, priority)
                            VALUES ($1, $2, $3)
                            RETURNING id
                            """,
                            user_id,
                            category,
                            category_priority,
                        )
                    else:
                        await conn.execute(
                            "UPDATE categories SET priority = $1 WHERE id = $2",
                            category_priority,
                            category_id,
                        )
                    category_priority += 1

                    feed_priority = 0
                    for feed in feeds_list:
                        await conn.execute(
                            """
                            INSERT INTO feeds (user_id, category_id, name, url, category, "isActive", priority, display_order)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            ON CONFLICT (user_id, url)
                            WHERE user_id IS NOT NULL
                            DO NOTHING;
                            """,
                            user_id,
                            category_id,
                            feed["name"],
                            feed["url"],
                            category,
                            feed.get("isActive", True),
                            feed_priority,
                            feed_priority,
                        )
                        feed_priority += 1

                logger.info("Default feeds and categories populated successfully.")
            except FileNotFoundError:
                logger.warning(
                    "feeds.json not found. Skipping default feed population."
                )
            except Exception as e:
                logger.error(f"Could not populate default data from feeds.json: {e}")
    except Exception as e:
        logger.error(f"Error checking feed count: {e}")


async def get_legacy_owner_user_id(conn):
    return await conn.fetchval(
        """
        SELECT id
        FROM users
        ORDER BY CASE WHEN role = 'admin' THEN 0 ELSE 1 END, created_at ASC, id ASC
        LIMIT 1
        """
    )


async def migrate_legacy_user_owned_data(conn):
    owner_user_id = await get_legacy_owner_user_id(conn)
    if not owner_user_id:
        return

    await conn.execute(
        "UPDATE categories SET user_id = $1 WHERE user_id IS NULL", owner_user_id
    )
    await conn.execute(
        """
        UPDATE feeds f
        SET user_id = COALESCE(f.user_id, c.user_id, $1),
            category_id = COALESCE(f.category_id, c.id)
        FROM categories c
        WHERE c.user_id = $1
          AND f.category = c.name
          AND (f.user_id IS NULL OR f.category_id IS NULL)
        """,
        owner_user_id,
    )
    await conn.execute(
        "UPDATE feeds SET user_id = $1 WHERE user_id IS NULL",
        owner_user_id,
    )
    await conn.execute(
        """
        UPDATE articles a
        SET user_id = COALESCE(a.user_id, f.user_id, $1),
            category_id = COALESCE(a.category_id, f.category_id)
        FROM feeds f
        WHERE a.feed_id = f.id
          AND (a.user_id IS NULL OR a.category_id IS NULL)
        """,
        owner_user_id,
    )
    await conn.execute(
        """
        UPDATE articles a
        SET category_id = COALESCE(a.category_id, c.id)
        FROM categories c
        WHERE a.user_id = c.user_id
          AND a.category = c.name
          AND a.category_id IS NULL
        """
    )
    await conn.execute(
        "UPDATE articles SET user_id = $1 WHERE user_id IS NULL",
        owner_user_id,
    )
    await conn.execute(
        """
        UPDATE report_schedules rs
        SET user_id = COALESCE(rs.user_id, $1),
            category_id = COALESCE(rs.category_id, c.id)
        FROM categories c
        WHERE c.user_id = $1
          AND rs.category = c.name
          AND (rs.user_id IS NULL OR rs.category_id IS NULL)
        """,
        owner_user_id,
    )
    await conn.execute(
        "UPDATE report_schedules SET user_id = $1 WHERE user_id IS NULL",
        owner_user_id,
    )
    await conn.execute(
        "UPDATE article_filters SET user_id = $1 WHERE user_id IS NULL",
        owner_user_id,
    )
    await conn.execute(
        """
        UPDATE article_ai_matches aam
        SET user_id = COALESCE(aam.user_id, a.user_id)
        FROM articles a
        WHERE aam.article_id = a.id
          AND aam.user_id IS NULL
        """
    )
    await conn.execute(
        """
        UPDATE article_filter_matches afm
        SET user_id = COALESCE(afm.user_id, a.user_id, f.user_id)
        FROM articles a, article_filters f
        WHERE afm.article_id = a.id
          AND afm.filter_id = f.id
          AND afm.user_id IS NULL
        """
    )
    await conn.execute(
        """
        UPDATE user_article_state uas
        SET article_id = a.id
        FROM articles a
        WHERE uas.article_id IS NULL
          AND uas.user_id = a.user_id
          AND uas.article_link = a.link
        """,
    )
    await conn.execute(
        """
        INSERT INTO user_article_state (user_id, article_id, article_link, is_read, read_at, is_saved, saved_at)
        SELECT $1, a.id, a.link, false, NULL, true, NOW()
        FROM articles a
        WHERE a.user_id = $1
          AND COALESCE(a.starred, false) = true
        ON CONFLICT (user_id, article_link)
        DO UPDATE SET article_id = EXCLUDED.article_id, is_saved = true, saved_at = NOW()
        """,
        owner_user_id,
    )


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
            'SELECT last_update FROM "FeedState" WHERE feed_url = $1', feed_url
        )
        if row and row["last_update"]:
            return ensure_aware(row["last_update"], IST)
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
            """
            INSERT INTO "FeedState" (feed_url, last_update)
            VALUES ($1, $2)
            ON CONFLICT (feed_url) DO UPDATE SET last_update = $2
            """,
            feed_url,
            new_update,
        )
    finally:
        await release_db_connection(conn)
