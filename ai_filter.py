"""
AI Content Filtering Module for RSS Newsapp

This module provides AI-powered content filtering using OpenAI-compatible APIs.
Articles can be filtered based on custom prompts defined per category.
"""

import logging
import hashlib
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

from openai import AsyncOpenAI
import asyncpg

from config import Config

logger = logging.getLogger(__name__)

# Initialize AsyncOpenAI client with custom base_url support
client = None


def get_openai_client() -> AsyncOpenAI:
    """Get or create AsyncOpenAI client"""
    global client
    if client is None:
        if not Config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not configured")

        client = AsyncOpenAI(
            api_key=Config.OPENAI_API_KEY, base_url=Config.OPENAI_BASE_URL
        )
        logger.info(
            f"AsyncOpenAI client initialized with base_url: {Config.OPENAI_BASE_URL}"
        )

    return client


def generate_prompt_hash(prompt: str) -> str:
    """Generate a hash for the prompt to detect changes"""
    return hashlib.sha256(prompt.encode()).hexdigest()


async def filter_article(title: str, description: str, prompt: str) -> bool:
    """
    Use AI to determine if an article matches the given prompt.
    Uses only title and description to minimize API costs.

    Args:
        title: Article title
        description: Article description/summary
        prompt: User-defined filtering prompt

    Returns:
        True if article matches the prompt, False otherwise
    """
    try:
        ai_client = get_openai_client()

        # Construct the filtering message
        system_message = """You are a content filter for RSS news articles. 
Your task is to determine if an article matches the user's interests based on their prompt.
Respond with ONLY 'YES' if the article matches, or 'NO' if it doesn't.
Do not provide any explanation or additional text."""

        user_message = f"""User's Interest Prompt: {prompt}

Article Title: {title}

Article Description: {description[:500] if description else "No description available"}

Does this article match the user's interests? Answer YES or NO only."""

        # Call OpenAI API
        response = await ai_client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            max_tokens=Config.OPENAI_MAX_TOKENS,
            temperature=Config.OPENAI_TEMPERATURE,
        )

        # Parse response
        answer = response.choices[0].message.content.strip().upper()
        matches = answer == "YES"

        logger.debug(
            f"AI Filter - Title: {title[:50]}... | Match: {matches} | Response: {answer}"
        )
        return matches

    except Exception as e:
        logger.error(f"Error in AI filtering: {e}")
        # On error, don't filter out the article (fail open)
        return True


async def process_article_for_category(
    article_id: int, user_id: int, category_id: int, conn: asyncpg.Connection
) -> bool:
    """
    Process a single article for a specific category's AI filter.

    Args:
        article_id: Article ID to process
        category_id: Category ID with AI filter
        conn: Database connection

    Returns:
        True if article matches and was saved, False otherwise
    """
    try:
        # Get category AI settings
        category = await conn.fetchrow(
            "SELECT ai_prompt, ai_enabled FROM categories WHERE id = $1 AND user_id = $2",
            category_id,
            user_id,
        )

        if not category or not category["ai_enabled"] or not category["ai_prompt"]:
            logger.debug(f"Category {category_id} doesn't have AI filtering enabled")
            return False

        prompt = category["ai_prompt"]
        prompt_hash = generate_prompt_hash(prompt)

        # Check if already processed with same prompt
        existing = await conn.fetchrow(
            "SELECT id FROM article_ai_matches WHERE article_id = $1 AND category_id = $2 AND user_id = $3 AND prompt_hash = $4",
            article_id,
            category_id,
            user_id,
            prompt_hash,
        )

        if existing:
            logger.debug(
                f"Article {article_id} already processed for category {category_id}"
            )
            return True

        # Get article details
        article = await conn.fetchrow(
            "SELECT title, description, content FROM articles WHERE id = $1 AND user_id = $2",
            article_id,
            user_id,
        )

        if not article:
            logger.warning(f"Article {article_id} not found")
            return False

        # Prepare content for filtering (using only title and description to minimize API costs)
        title = article["title"] or ""
        description = article["description"] or ""

        # Filter with AI
        matches = await filter_article(title, description, prompt)

        if matches:
            # Save match to database
            await conn.execute(
                """
                INSERT INTO article_ai_matches (article_id, category_id, user_id, prompt_hash)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (article_id, category_id) 
                DO UPDATE SET user_id = EXCLUDED.user_id, prompt_hash = EXCLUDED.prompt_hash, matched_at = CURRENT_TIMESTAMP
                """,
                article_id,
                category_id,
                user_id,
                prompt_hash,
            )
            logger.info(
                f"Article {article_id} matched AI filter for category {category_id}"
            )
            return True
        else:
            # Remove match if it exists (in case of prompt change)
            await conn.execute(
                "DELETE FROM article_ai_matches WHERE article_id = $1 AND category_id = $2 AND user_id = $3",
                article_id,
                category_id,
                user_id,
            )
            logger.debug(
                f"Article {article_id} did not match AI filter for category {category_id}"
            )
            return False

    except Exception as e:
        logger.error(
            f"Error processing article {article_id} for category {category_id}: {e}"
        )
        return False


async def process_new_article(
    article_id: int, user_id: int, category_id: int | None, conn: asyncpg.Connection
):
    """
    Process a newly added article for AI filtering.
    Called automatically when new articles are saved.

    Args:
        article_id: New article ID
        category_name: Article's category name
        conn: Database connection
    """
    try:
        if not category_id:
            return

        await process_article_for_category(article_id, user_id, category_id, conn)

    except Exception as e:
        logger.error(f"Error in process_new_article for article {article_id}: {e}")


async def reprocess_category_articles(
    user_id: int, category_id: int, conn: asyncpg.Connection
) -> Dict[str, int]:
    """
    Reprocess all articles in a category's AI filter.
    Called when prompt is changed or manually triggered.

    Args:
        category_id: Category ID to reprocess
        conn: Database connection

    Returns:
        Dictionary with stats: total, matched, filtered
    """
    try:
        # Get category details
        category = await conn.fetchrow(
            "SELECT name, ai_prompt, ai_enabled FROM categories WHERE id = $1 AND user_id = $2",
            category_id,
            user_id,
        )

        if not category:
            raise ValueError(f"Category {category_id} not found")

        if not category["ai_enabled"] or not category["ai_prompt"]:
            logger.info(f"AI filtering not enabled for category {category_id}")
            return {"total": 0, "matched": 0, "filtered": 0}

        category_name = category["name"]

        # Clear existing matches for this category
        await conn.execute(
            "DELETE FROM article_ai_matches WHERE category_id = $1 AND user_id = $2",
            category_id,
            user_id,
        )
        logger.info(f"Cleared existing AI matches for category {category_id}")

        # Get all articles in this category
        articles = await conn.fetch(
            "SELECT id FROM articles WHERE user_id = $1 AND category_id = $2 ORDER BY id DESC",
            user_id,
            category_id,
        )

        total = len(articles)
        matched = 0

        logger.info(f"Reprocessing {total} articles for category {category_id}")

        # Process each article with rate limiting
        for article in articles:
            article_id = article["id"]
            result = await process_article_for_category(
                article_id, user_id, category_id, conn
            )
            if result:
                matched += 1

            # Rate limiting: 0.1 second delay between articles
            await asyncio.sleep(0.1)

        filtered = total - matched

        logger.info(
            f"Reprocessing complete for category {category_id}: {total} total, {matched} matched, {filtered} filtered"
        )

        return {"total": total, "matched": matched, "filtered": filtered}

    except Exception as e:
        logger.error(f"Error reprocessing category {category_id}: {e}")
        raise
