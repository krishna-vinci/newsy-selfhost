"""
Reports module for RSS Newsapp
Handles markdown report generation, scheduling, and file management
"""

import os
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
import pytz

import asyncpg
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
import html2text
import markdown2

from backend.config import Config
from backend.database import get_db_connection, release_db_connection
from backend.auth import require_request_user

# Indian Standard Time
IST = pytz.timezone("Asia/Kolkata")

# Reports directory
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)


def get_user_reports_dir(user_id: int) -> Path:
    path = REPORTS_DIR / f"user_{user_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path


# Router for reports endpoints
router = APIRouter(prefix="/api/reports", tags=["reports"])

# Global scheduler reference (set during startup)
_scheduler = None

# --- Pydantic Models ---


class ReportSchedule(BaseModel):
    id: Optional[int] = None
    category: str = Field(..., min_length=1, max_length=100)
    schedule_type: str = Field(..., pattern="^(daily|weekly)$")
    schedule_hour: int = Field(default=0, ge=0, le=23)
    schedule_minute: int = Field(default=0, ge=0, le=59)
    enabled: bool = True


class ReportGenerateRequest(BaseModel):
    category: str = Field(..., min_length=1, max_length=100)


class ReportFile(BaseModel):
    filename: str
    category: str
    report_type: str
    generated_at: str
    file_size: int
    path: str


# --- Database Functions ---


async def init_reports_db():
    """
    Initialize reports database.
    Note: report_schedules table is now created in database.py with all columns.
    This function is kept for backward compatibility.
    """
    # Table creation is now handled in database.init_db()
    logging.info(
        "Reports database initialization - table created in main database.init_db()"
    )
    pass


# --- Core Report Generation Function ---


def sanitize_filename(name: str) -> str:
    """Sanitize string for safe filename usage"""
    # Remove any characters that aren't alphanumeric, dash, or underscore
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)
    return safe_name[:100]  # Limit length


def format_content_for_markdown(html_content: str) -> str:
    """
    Format HTML content for markdown reports with proper paragraph breaks.
    Uses the same method as the feeds page for consistency.
    """
    try:
        # Convert HTML to Markdown to strip proprietary classes and styles
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.ignore_images = False
        converter.body_width = 0  # No wrapping
        markdown_content = converter.handle(html_content)

        # First, normalize existing newlines
        markdown_content = re.sub(r"\n+", "\n\n", markdown_content)

        # Add paragraph breaks after sentences that end with punctuation followed by a capital letter
        # This handles cases where HTML doesn't have proper paragraph tags
        # Pattern: period/question/exclamation + optional quote + optional space + capital letter
        markdown_content = re.sub(
            r'([.!?]["\']?)\s*([A-Z])', r"\1\n\n\2", markdown_content
        )

        # Clean up any triple or more newlines back to double
        markdown_content = re.sub(r"\n{3,}", "\n\n", markdown_content)

        return markdown_content.strip()
    except Exception as e:
        logging.error(f"Error formatting content for markdown: {e}")
        return html_content  # Return original if formatting fails


async def generate_markdown_report(
    user_id: int,
    category_id: int,
    category: str,
    report_type: str = "starred",  # 'starred', 'daily', 'weekly'
    custom_days: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Generate a markdown report for articles

    Args:
        category: Category name to generate report for
        report_type: Type of report ('starred', 'daily', 'weekly')
        custom_days: Custom number of days to look back (overrides report_type)

    Returns:
        Dictionary with filepath, filename, and metadata
    """
    conn = await get_db_connection()

    try:
        # Validate category exists
        category_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM categories WHERE id = $1 AND user_id = $2)",
            category_id,
            user_id,
        )
        if not category_exists:
            raise ValueError(f"Category '{category}' does not exist")

        # Build query based on report type
        if report_type == "starred":
            query = """
                SELECT a.title, a.link, a.description, a.thumbnail, a.published, 
                       a.published_datetime, a.content, a.source
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                JOIN user_article_state uas ON uas.article_id = a.id AND uas.user_id = $1
                WHERE a.user_id = $1 AND a.category_id = $2 AND COALESCE(uas.is_saved, false) = true AND f."isActive" = true
                ORDER BY a.published_datetime DESC
            """
            params = [user_id, category_id]
        else:
            # Time-windowed reports
            if custom_days:
                days_back = custom_days
            elif report_type == "daily":
                days_back = 1
            elif report_type == "weekly":
                days_back = 7
            else:
                raise ValueError(f"Invalid report_type: {report_type}")

            threshold = datetime.now(IST) - timedelta(days=days_back)
            query = """
                SELECT a.title, a.link, a.description, a.thumbnail, a.published, 
                       a.published_datetime, a.content, a.source
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE a.user_id = $1
                AND a.category_id = $2
                AND a.published_datetime >= $3 
                AND f."isActive" = true
                ORDER BY a.published_datetime DESC
            """
            params = [user_id, category_id, threshold]

        # Fetch articles
        articles = await conn.fetch(query, *params)

        if not articles:
            raise ValueError(
                f"No articles found for category '{category}' with report type '{report_type}'"
            )

        # Generate markdown content
        markdown_content = _generate_markdown_content(
            category=category, report_type=report_type, articles=articles
        )

        # Create filename
        timestamp = datetime.now(IST).strftime("%Y-%m-%d_%H-%M-%S")
        safe_category = sanitize_filename(category)
        filename = f"report_{safe_category}_{report_type}_{timestamp}.md"
        filepath = get_user_reports_dir(user_id) / filename

        # Write to file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        logging.info(f"Generated report: {filename} ({len(articles)} articles)")

        return {
            "filename": filename,
            "filepath": str(filepath),
            "category": category,
            "report_type": report_type,
            "article_count": len(articles),
            "generated_at": timestamp,
        }

    finally:
        await release_db_connection(conn)


def _generate_markdown_content(
    category: str, report_type: str, articles: List[asyncpg.Record]
) -> str:
    """Generate markdown content from articles"""

    # Header
    timestamp = datetime.now(IST).strftime("%B %d, %Y at %I:%M %p IST")

    if report_type == "starred":
        title = f"Starred Articles Report - {category}"
        subtitle = "Your saved articles"
    elif report_type == "daily":
        title = f"Daily Report - {category}"
        subtitle = "Articles from the last 24 hours"
    elif report_type == "weekly":
        title = f"Weekly Report - {category}"
        subtitle = "Articles from the last 7 days"
    else:
        title = f"Report - {category}"
        subtitle = ""

    lines = [
        f"# {title}",
        "",
        f"**{subtitle}**",
        "",
        f"*Generated on: {timestamp}*",
        "",
        f"*Total Articles: {len(articles)}*",
        "",
        "---",
        "",
    ]

    # Articles
    for idx, article in enumerate(articles, 1):
        title = article["title"] or "Untitled"
        link = article["link"] or "#"
        source = article["source"] or "Unknown"
        published = article["published"] or "Unknown date"
        description = article["description"] or ""
        content = article["content"] or ""
        thumbnail = article["thumbnail"]

        lines.append(f"## {idx}. {title}")
        lines.append("")
        lines.append(f"**Source:** {source} | **Published:** {published}")
        lines.append("")
        lines.append(f"**Link:** [{link}]({link})")
        lines.append("")

        # Add thumbnail if available
        if thumbnail and thumbnail != "/static/default-thumbnail.jpg":
            lines.append(f"![Article Image]({thumbnail})")
            lines.append("")

        # Add description
        if description:
            lines.append("### Description")
            lines.append("")
            lines.append(description)
            lines.append("")

        # Add full content if available
        if content:
            lines.append("### Full Content")
            lines.append("")
            # Format content with proper paragraph breaks
            formatted_content = format_content_for_markdown(content)
            lines.append(formatted_content)
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# --- Scheduler Functions ---


async def execute_scheduled_report(
    user_id: int, category_id: int, category: str, schedule_type: str
):
    """Execute a scheduled report generation"""
    try:
        logging.info(
            f"Executing scheduled {schedule_type} report for category: {category}"
        )
        result = await generate_markdown_report(
            user_id=user_id,
            category_id=category_id,
            category=category,
            report_type=schedule_type,
        )
        logging.info(f"Scheduled report generated: {result['filename']}")
    except Exception as e:
        logging.error(
            f"Error generating scheduled report for {category} ({schedule_type}): {e}"
        )


async def load_and_schedule_reports(scheduler):
    """Load enabled schedules from database and add to scheduler"""
    global _scheduler
    _scheduler = scheduler  # Store reference for later use

    conn = await get_db_connection()
    try:
        schedules = await conn.fetch(
            "SELECT id, user_id, category_id, category, schedule_type, schedule_hour, schedule_minute FROM report_schedules WHERE enabled = true"
        )

        for schedule in schedules:
            schedule_id = schedule["id"]
            user_id = schedule["user_id"]
            category_id = schedule["category_id"]
            category = schedule["category"]
            schedule_type = schedule["schedule_type"]
            schedule_hour = schedule.get("schedule_hour", 0) or 0
            schedule_minute = schedule.get("schedule_minute", 0) or 0

            job_id = f"report_{user_id}_{schedule_type}_{category}_{schedule_id}"

            # Remove existing job if present
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)

            # Add job based on schedule type
            if schedule_type == "daily":
                # Run daily at specified time
                scheduler.add_job(
                    execute_scheduled_report,
                    "cron",
                    hour=schedule_hour,
                    minute=schedule_minute,
                    args=[user_id, category_id, category, schedule_type],
                    id=job_id,
                    replace_existing=True,
                )
                logging.info(
                    f"Scheduled daily report for {category} at {schedule_hour:02d}:{schedule_minute:02d}"
                )

            elif schedule_type == "weekly":
                # Run weekly on Monday at specified time
                scheduler.add_job(
                    execute_scheduled_report,
                    "cron",
                    day_of_week="mon",
                    hour=schedule_hour,
                    minute=schedule_minute,
                    args=[user_id, category_id, category, schedule_type],
                    id=job_id,
                    replace_existing=True,
                )
                logging.info(
                    f"Scheduled weekly report for {category} at {schedule_hour:02d}:{schedule_minute:02d}"
                )

        logging.info(f"Loaded {len(schedules)} report schedules")

    finally:
        await release_db_connection(conn)


# --- API Endpoints ---


@router.post("/generate/starred/{category}")
async def generate_starred_report(category: str, request: Request):
    """Generate a report for all starred articles in a category"""
    try:
        user = require_request_user(request)
        conn = await get_db_connection()
        category_row = await conn.fetchrow(
            "SELECT id, name FROM categories WHERE user_id = $1 AND name = $2",
            user["id"],
            category,
        )
        await release_db_connection(conn)
        if not category_row:
            raise HTTPException(status_code=404, detail="Category not found")
        result = await generate_markdown_report(
            user_id=user["id"],
            category_id=category_row["id"],
            category=category_row["name"],
            report_type="starred",
        )
        return JSONResponse(
            content={
                "message": "Report generated successfully",
                "filename": result["filename"],
                "article_count": result["article_count"],
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"Error generating starred report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate report")


@router.get("/schedules")
async def get_schedules(request: Request):
    """Get all report schedules"""
    user = require_request_user(request)
    conn = await get_db_connection()
    try:
        schedules = await conn.fetch(
            """
            SELECT id, category, schedule_type, schedule_hour, schedule_minute, enabled, created_at, updated_at
            FROM report_schedules
            WHERE user_id = $1
            ORDER BY category, schedule_type
            """,
            user["id"],
        )
        return JSONResponse(
            content=[
                {
                    "id": s["id"],
                    "category": s["category"],
                    "schedule_type": s["schedule_type"],
                    "schedule_hour": s.get("schedule_hour", 0) or 0,
                    "schedule_minute": s.get("schedule_minute", 0) or 0,
                    "enabled": s["enabled"],
                    "created_at": s["created_at"].isoformat()
                    if s["created_at"]
                    else None,
                    "updated_at": s["updated_at"].isoformat()
                    if s["updated_at"]
                    else None,
                }
                for s in schedules
            ]
        )
    finally:
        await release_db_connection(conn)


@router.post("/schedules")
async def create_schedule(schedule: ReportSchedule, request: Request):
    """Create a new report schedule"""
    user = require_request_user(request)
    conn = await get_db_connection()
    try:
        # Validate category exists
        category_row = await conn.fetchrow(
            "SELECT id, name FROM categories WHERE user_id = $1 AND name = $2",
            user["id"],
            schedule.category,
        )
        if not category_row:
            raise HTTPException(
                status_code=400, detail=f"Category '{schedule.category}' does not exist"
            )

        # Check for duplicate
        existing = await conn.fetchval(
            "SELECT id FROM report_schedules WHERE user_id = $1 AND category_id = $2 AND schedule_type = $3",
            user["id"],
            category_row["id"],
            schedule.schedule_type,
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Schedule already exists for {schedule.category} ({schedule.schedule_type})",
            )

        # Insert schedule
        schedule_id = await conn.fetchval(
            """
            INSERT INTO report_schedules (user_id, category_id, category, schedule_type, schedule_hour, schedule_minute, enabled)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            user["id"],
            category_row["id"],
            category_row["name"],
            schedule.schedule_type,
            schedule.schedule_hour,
            schedule.schedule_minute,
            schedule.enabled,
        )

        # Reload schedules
        if _scheduler:
            await load_and_schedule_reports(_scheduler)

        return JSONResponse(
            content={
                "message": "Schedule created successfully",
                "id": schedule_id,
                "category": schedule.category,
                "schedule_type": schedule.schedule_type,
                "schedule_hour": schedule.schedule_hour,
                "schedule_minute": schedule.schedule_minute,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error creating schedule: {e}")
        raise HTTPException(status_code=500, detail="Failed to create schedule")
    finally:
        await release_db_connection(conn)


@router.put("/schedules/{schedule_id}")
async def update_schedule(schedule_id: int, schedule: ReportSchedule, request: Request):
    """Update an existing schedule"""
    user = require_request_user(request)
    conn = await get_db_connection()
    try:
        category_row = await conn.fetchrow(
            "SELECT id, name FROM categories WHERE user_id = $1 AND name = $2",
            user["id"],
            schedule.category,
        )
        if not category_row:
            raise HTTPException(
                status_code=400, detail=f"Category '{schedule.category}' does not exist"
            )

        # Check if schedule exists
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM report_schedules WHERE id = $1 AND user_id = $2)",
            schedule_id,
            user["id"],
        )
        if not exists:
            raise HTTPException(status_code=404, detail="Schedule not found")

        # Update schedule
        await conn.execute(
            """
            UPDATE report_schedules
            SET category_id = $1, category = $2, schedule_type = $3, schedule_hour = $4, schedule_minute = $5, enabled = $6, updated_at = NOW()
            WHERE id = $7 AND user_id = $8
            """,
            category_row["id"],
            category_row["name"],
            schedule.schedule_type,
            schedule.schedule_hour,
            schedule.schedule_minute,
            schedule.enabled,
            schedule_id,
            user["id"],
        )

        # Reload schedules
        if _scheduler:
            await load_and_schedule_reports(_scheduler)

        return JSONResponse(
            content={"message": "Schedule updated successfully", "id": schedule_id}
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating schedule: {e}")
        raise HTTPException(status_code=500, detail="Failed to update schedule")
    finally:
        await release_db_connection(conn)


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: int, request: Request):
    """Delete a schedule"""
    user = require_request_user(request)
    conn = await get_db_connection()
    try:
        result = await conn.execute(
            "DELETE FROM report_schedules WHERE id = $1 AND user_id = $2",
            schedule_id,
            user["id"],
        )

        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Schedule not found")

        # Reload schedules
        if _scheduler:
            await load_and_schedule_reports(_scheduler)

        return JSONResponse(content={"message": "Schedule deleted successfully"})

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting schedule: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete schedule")
    finally:
        await release_db_connection(conn)


@router.get("/files")
async def list_report_files(request: Request):
    """List all generated report files"""
    try:
        user = require_request_user(request)
        files = []
        for filepath in get_user_reports_dir(user["id"]).glob("report_*.md"):
            # Parse filename: report_{category}_{type}_{timestamp}.md
            parts = filepath.stem.split("_")
            if len(parts) >= 4:
                category = parts[1]
                report_type = parts[2]
                timestamp = "_".join(parts[3:])

                stat = filepath.stat()
                files.append(
                    {
                        "filename": filepath.name,
                        "category": category,
                        "report_type": report_type,
                        "generated_at": timestamp,
                        "file_size": stat.st_size,
                        "path": str(filepath),
                    }
                )

        # Sort by generated_at descending (newest first)
        files.sort(key=lambda x: x["generated_at"], reverse=True)

        return JSONResponse(content=files)

    except Exception as e:
        logging.error(f"Error listing report files: {e}")
        raise HTTPException(status_code=500, detail="Failed to list reports")


@router.get("/download/{filename}")
async def download_report(filename: str, request: Request):
    """Download a specific report file"""
    try:
        user = require_request_user(request)
        # Validate filename - must be report_*.md format
        if not filename.startswith("report_") or not filename.endswith(".md"):
            raise HTTPException(status_code=400, detail="Invalid filename format")

        # Check for directory traversal attempts
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        filepath = get_user_reports_dir(user["id"]) / filename

        if not filepath.exists() or not filepath.is_file():
            raise HTTPException(status_code=404, detail="Report file not found")

        return FileResponse(
            path=filepath,
            media_type="text/markdown",
            filename=filepath.name,
            headers={"Content-Disposition": f"attachment; filename={filepath.name}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error downloading report: {e}")
        raise HTTPException(status_code=500, detail="Failed to download report")
