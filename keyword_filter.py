"""
Keyword and Topic-Based Filtering Module for RSS Newsapp

This module provides intelligent content filtering using keywords and AI-powered topics.
Articles matching filters can be automatically starred and trigger notifications.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
import asyncpg

from ai_filter import get_openai_client, filter_article
from config import Config
import database

logger = logging.getLogger(__name__)


async def check_keyword_match(text: str, keyword: str) -> bool:
    """
    Check if keyword matches in text (case-insensitive).
    
    Args:
        text: Combined text (title + description)
        keyword: Keyword to search for
    
    Returns:
        True if keyword found, False otherwise
    """
    if not text or not keyword:
        return False
    
    return keyword.lower() in text.lower()


async def check_topic_match(title: str, description: str, topic: str) -> bool:
    """
    Use AI to determine if an article is relevant to a topic.
    
    Args:
        title: Article title
        description: Article description
        topic: Topic description (e.g., "impact of quantum computing on cybersecurity")
    
    Returns:
        True if article is relevant to topic, False otherwise
    """
    try:
        # Reuse the filter_article function from ai_filter.py
        # with topic as the prompt
        prompt = f"Articles about: {topic}"
        return await filter_article(title, description, prompt)
    except Exception as e:
        logger.error(f"Error checking topic match: {e}")
        return False


async def get_active_filters(conn: asyncpg.Connection, category_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get all active filters, optionally filtered by category.
    
    Args:
        conn: Database connection
        category_name: Optional category name to filter by
    
    Returns:
        List of filter dictionaries
    """
    try:
        if category_name:
            # Get category-specific filters and global filters
            query = """
                SELECT f.id, f.name, f.category_id, f.filter_type, f.filter_value, 
                       f.auto_star, f.auto_notify, f.enabled
                FROM article_filters f
                LEFT JOIN categories c ON f.category_id = c.id
                WHERE f.enabled = true 
                AND (c.name = $1 OR f.category_id IS NULL)
            """
            filters = await conn.fetch(query, category_name)
        else:
            # Get all active filters
            query = """
                SELECT id, name, category_id, filter_type, filter_value, 
                       auto_star, auto_notify, enabled
                FROM article_filters
                WHERE enabled = true
            """
            filters = await conn.fetch(query)
        
        return [dict(f) for f in filters]
    except Exception as e:
        logger.error(f"Error getting active filters: {e}")
        return []


async def check_article_against_filters(
    article_id: int,
    title: str,
    description: str,
    category_name: str,
    conn: asyncpg.Connection
) -> List[Dict[str, Any]]:
    """
    Check an article against all active filters and return matching filters.
    
    Args:
        article_id: Article ID
        title: Article title
        description: Article description
        category_name: Article category
        conn: Database connection
    
    Returns:
        List of matching filter dictionaries
    """
    try:
        # Get active filters for this category
        filters = await get_active_filters(conn, category_name)
        
        if not filters:
            logger.debug(f"No active filters found for category: {category_name}")
            return []
        
        matching_filters = []
        combined_text = f"{title} {description}"
        
        for filter_dict in filters:
            matched = False
            
            if filter_dict['filter_type'] == 'keyword':
                # Simple keyword matching
                matched = await check_keyword_match(combined_text, filter_dict['filter_value'])
                logger.debug(f"Keyword filter '{filter_dict['name']}' matched: {matched}")
            
            elif filter_dict['filter_type'] == 'topic':
                # AI-powered topic matching
                matched = await check_topic_match(title, description, filter_dict['filter_value'])
                logger.debug(f"Topic filter '{filter_dict['name']}' matched: {matched}")
            
            if matched:
                matching_filters.append(filter_dict)
                
                # Record the match in database
                try:
                    await conn.execute("""
                        INSERT INTO article_filter_matches (article_id, filter_id)
                        VALUES ($1, $2)
                        ON CONFLICT (article_id, filter_id) DO NOTHING
                    """, article_id, filter_dict['id'])
                except Exception as e:
                    logger.warning(f"Error recording filter match: {e}")
        
        return matching_filters
        
    except Exception as e:
        logger.error(f"Error checking article against filters: {e}")
        return []


async def process_article_filters(
    article_id: int,
    title: str,
    link: str,
    description: str,
    content: Optional[str],
    category_name: str,
    source: str,
    conn: asyncpg.Connection
) -> None:
    """
    Process an article through all filters and take appropriate actions.
    
    This function:
    1. Checks article against all active filters
    2. Auto-stars if any filter matches with auto_star=true
    3. Sends full content notification if any filter matches with auto_notify=true
    
    Args:
        article_id: Article ID
        title: Article title
        link: Article link
        description: Article description
        content: Full article content (HTML)
        category_name: Article category
        source: Article source
        conn: Database connection
    """
    try:
        # Check article against filters
        matching_filters = await check_article_against_filters(
            article_id, title, description, category_name, conn
        )
        
        if not matching_filters:
            logger.debug(f"Article {article_id} did not match any filters")
            return
        
        logger.info(f"Article {article_id} matched {len(matching_filters)} filter(s)")
        
        # Check if any filter requires auto-starring
        auto_star_filter = next((f for f in matching_filters if f['auto_star']), None)
        if auto_star_filter:
            try:
                await conn.execute(
                    "UPDATE articles SET starred = true, auto_starred_by = $1 WHERE id = $2",
                    auto_star_filter['id'], article_id
                )
                logger.info(f"Auto-starred article {article_id} by filter '{auto_star_filter['name']}'")
            except Exception as e:
                logger.error(f"Error auto-starring article {article_id}: {e}")
        
        # Check if any filter requires notification
        notify_filters = [f for f in matching_filters if f['auto_notify']]
        if notify_filters:
            # Send notification with full content
            await send_filter_notification(
                title, link, description, content, category_name, 
                source, notify_filters
            )
    
    except Exception as e:
        logger.error(f"Error processing article filters for article {article_id}: {e}")


async def send_filter_notification(
    title: str,
    link: str,
    description: str,
    content: Optional[str],
    category: str,
    source: str,
    matching_filters: List[Dict[str, Any]]
) -> None:
    """
    Send ntfy notification with full article content when filters match.
    
    Args:
        title: Article title
        link: Article link
        description: Article description
        content: Full article content (HTML)
        category: Article category
        source: Article source
        matching_filters: List of matching filters
    """
    try:
        import httpx
        from main import sanitize_text
        
        NTFY_BASE_URL = "https://ntfy.sh"
        
        # Check if ntfy is enabled for this category
        from database import get_db_connection
        conn = await get_db_connection()
        ntfy_enabled = await conn.fetchval(
            "SELECT ntfy_enabled FROM categories WHERE name = $1", 
            category
        )
        await database.release_db_connection(conn)
        
        if ntfy_enabled is False:
            logger.debug(f"Ntfy notifications disabled for category: {category}")
            return
        
        # Prepare notification content
        filter_names = ", ".join([f['name'] for f in matching_filters])
        title_text = sanitize_text(f"🎯 {title}")
        topic = f"feeds-{category.lower().replace(' ', '-')}"
        ntfy_url = f"{NTFY_BASE_URL}/{topic}"
        
        headers = {
            "Title": title_text,
            "Click": link,
            "Priority": "high",  # High priority for filtered articles
            "Tags": "star"
        }
        
        # Include full content in notification body
        # Strip HTML tags for notification
        import re
        if content:
            # Basic HTML tag removal
            clean_content = re.sub('<[^<]+?>', '', content)
            clean_content = clean_content.strip()[:1000]  # Limit to 1000 chars
        else:
            clean_content = description
        
        payload = f"""🎯 Matched Filter: {filter_names}

{clean_content}

Source: {source}"""
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    ntfy_url, 
                    headers=headers, 
                    content=payload.encode('utf-8')
                )
                response.raise_for_status()
                logger.info(f"Sent filter notification for article: {title[:50]}...")
        except httpx.HTTPStatusError as e:
            logger.exception(f"Failed to send filter notification: {e}")
    
    except Exception as e:
        logger.error(f"Error sending filter notification: {e}")


async def get_filter_statistics(
    conn: asyncpg.Connection, 
    category_id: Optional[int] = None,
    days: int = 30
) -> Dict[str, Any]:
    """
    Get statistics about filter matches.
    
    Args:
        conn: Database connection
        category_id: Optional category ID to filter by
        days: Number of days to look back
    
    Returns:
        Dictionary with filter statistics
    """
    try:
        from datetime import datetime, timedelta
        import pytz
        
        IST = pytz.timezone("Asia/Kolkata")
        threshold = datetime.now(IST) - timedelta(days=days)
        
        if category_id:
            query = """
                SELECT 
                    f.id,
                    f.name,
                    f.filter_type,
                    f.filter_value,
                    COUNT(DISTINCT afm.article_id) as match_count,
                    COUNT(DISTINCT CASE WHEN a.starred = true THEN afm.article_id END) as starred_count
                FROM article_filters f
                LEFT JOIN article_filter_matches afm ON f.id = afm.filter_id
                LEFT JOIN articles a ON afm.article_id = a.id
                WHERE f.category_id = $1 AND (afm.matched_at >= $2 OR afm.matched_at IS NULL)
                GROUP BY f.id, f.name, f.filter_type, f.filter_value
                ORDER BY match_count DESC
            """
            stats = await conn.fetch(query, category_id, threshold)
        else:
            query = """
                SELECT 
                    f.id,
                    f.name,
                    f.filter_type,
                    f.filter_value,
                    c.name as category_name,
                    COUNT(DISTINCT afm.article_id) as match_count,
                    COUNT(DISTINCT CASE WHEN a.starred = true THEN afm.article_id END) as starred_count
                FROM article_filters f
                LEFT JOIN categories c ON f.category_id = c.id
                LEFT JOIN article_filter_matches afm ON f.id = afm.filter_id
                LEFT JOIN articles a ON afm.article_id = a.id
                WHERE afm.matched_at >= $1 OR afm.matched_at IS NULL
                GROUP BY f.id, f.name, f.filter_type, f.filter_value, c.name
                ORDER BY match_count DESC
            """
            stats = await conn.fetch(query, threshold)
        
        return {
            "filters": [dict(s) for s in stats],
            "total_filters": len(stats),
            "days": days
        }
    
    except Exception as e:
        logger.error(f"Error getting filter statistics: {e}")
        return {"filters": [], "total_filters": 0, "days": days}
