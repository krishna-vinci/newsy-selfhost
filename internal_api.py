"""
Internal API endpoints for Go scheduler service
These endpoints are called by the Go worker pool to process feeds
"""

import logging
import asyncio
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import pytz

from worker import parse_and_store_rss_feed
import database
import cache

IST = pytz.timezone("Asia/Kolkata")
logger = logging.getLogger(__name__)

router = APIRouter()


class ProcessFeedRequest(BaseModel):
    feed_id: int
    name: str
    url: str
    category: str
    polling_interval: int
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    fetch_full_content: bool = False


class ProcessFeedResponse(BaseModel):
    success: bool
    articles_added: int
    new_etag: Optional[str] = None
    new_last_modified: Optional[str] = None
    error: Optional[str] = None


@router.post("/internal/process-feed", response_model=ProcessFeedResponse)
async def process_feed(request: ProcessFeedRequest):
    """
    Internal endpoint called by Go scheduler workers to process a feed.
    This endpoint wraps the existing feed processing logic.
    """
    logger.info(f"Processing feed: {request.name} (ID: {request.feed_id})")

    try:
        # Call the existing async feed processing function
        new_etag, new_last_modified, articles_added = await parse_and_store_rss_feed(
            feed_id=request.feed_id,
            etag=request.etag,
            last_modified=request.last_modified,
            fetch_full_content=request.fetch_full_content,
        )

        # Update feed metadata in database
        conn = await database.get_db_connection()
        try:
            # Calculate next check time
            next_check = datetime.now(IST) + timedelta(minutes=request.polling_interval)

            # Update feed with new caching headers, next check time, and reset error count
            await conn.execute(
                """
                UPDATE feeds 
                SET etag_header = $1, 
                    last_modified_header = $2, 
                    next_check_at = $3,
                    checked_at = NOW(),
                    parsing_error_count = 0,
                    parsing_error_msg = ''
                WHERE id = $4
                """,
                new_etag,
                new_last_modified,
                next_check,
                request.feed_id,
            )

            logger.info(
                f"Updated feed {request.feed_id} metadata: next_check_at={next_check}, articles_added={articles_added}"
            )

        finally:
            await database.release_db_connection(conn)

        return ProcessFeedResponse(
            success=True,
            articles_added=articles_added,
            new_etag=new_etag,
            new_last_modified=new_last_modified,
        )

    except Exception as e:
        logger.exception(
            f"Error processing feed {request.name} (ID: {request.feed_id}): {e}"
        )

        # Update error count and message in database
        try:
            conn = await database.get_db_connection()
            try:
                # Calculate next check time (with backoff on error)
                next_check = datetime.now(IST) + timedelta(
                    minutes=request.polling_interval * 2
                )

                await conn.execute(
                    """
                    UPDATE feeds 
                    SET parsing_error_count = COALESCE(parsing_error_count, 0) + 1,
                        parsing_error_msg = $1,
                        next_check_at = $2,
                        checked_at = NOW()
                    WHERE id = $3
                    """,
                    str(e)[:500],
                    next_check,
                    request.feed_id,
                )
            finally:
                await database.release_db_connection(conn)
        except Exception as db_err:
            logger.error(
                f"Failed to update error count for feed {request.feed_id}: {db_err}"
            )

        return ProcessFeedResponse(success=False, articles_added=0, error=str(e))


@router.get("/internal/health")
async def internal_health():
    """Internal health check endpoint"""
    return {"status": "healthy", "service": "newsy-backend-internal"}
