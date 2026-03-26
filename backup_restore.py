"""
Backup, Restore, Export, and OPML module for RSS Newsapp
Handles database backups, data exports, OPML import/export, and feed reordering
"""

import os
import logging
import subprocess
import json
import csv
import io
import gzip
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import xml.etree.ElementTree as ET

import asyncpg
from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from auth import require_request_user
from config import Config
import database

# Backups directory
BACKUPS_DIR = Path("data/backups")
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

# Router for backup/restore/export endpoints
router = APIRouter(tags=["backup_restore"])

# --- Pydantic Models ---


class BackupInfo(BaseModel):
    filename: str
    created_at: str
    size_bytes: int
    size_mb: float


class RestoreRequest(BaseModel):
    filename: str


class FeedReorderRequest(BaseModel):
    category: str
    feed_ids: List[int]


# --- Database Functions ---


async def get_db_connection():
    """Get database connection from pool"""
    return await database.get_db_connection()


# --- Backup Functions ---


def create_backup_filename() -> str:
    """Generate a timestamped backup filename"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"backup_{timestamp}.sql.gz"


def run_pg_dump() -> Path:
    """Create a PostgreSQL backup using pg_dump"""
    backup_file = BACKUPS_DIR / create_backup_filename()

    try:
        # Set environment for PostgreSQL password
        env = os.environ.copy()
        env["PGPASSWORD"] = Config.DB_PASSWORD

        # Run pg_dump and compress output
        dump_cmd = [
            "pg_dump",
            "-h",
            Config.DB_HOST,
            "-p",
            Config.DB_PORT,
            "-U",
            Config.DB_USER,
            "-d",
            Config.DB_NAME,
            "--format=plain",
            "--no-owner",
            "--no-privileges",
        ]

        # Run pg_dump and compress
        with gzip.open(backup_file, "wb") as f:
            result = subprocess.run(
                dump_cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            f.write(result.stdout)

        logging.info(f"Backup created: {backup_file}")
        return backup_file

    except subprocess.CalledProcessError as e:
        logging.error(f"Backup failed: {e.stderr.decode()}")
        raise HTTPException(
            status_code=500, detail=f"Backup failed: {e.stderr.decode()}"
        )
    except Exception as e:
        logging.error(f"Backup error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Backup error: {str(e)}")


def run_pg_restore(backup_file: Path):
    """Restore a PostgreSQL backup using psql"""
    try:
        # Set environment for PostgreSQL password
        env = os.environ.copy()
        env["PGPASSWORD"] = Config.DB_PASSWORD

        # Drop and recreate database
        logging.info("Dropping and recreating database...")

        # Drop database
        drop_cmd = [
            "psql",
            "-h",
            Config.DB_HOST,
            "-p",
            Config.DB_PORT,
            "-U",
            Config.DB_USER,
            "-d",
            "postgres",
            "-c",
            f"DROP DATABASE IF EXISTS {Config.DB_NAME};",
        ]
        subprocess.run(drop_cmd, env=env, check=True, capture_output=True)

        # Create database
        create_cmd = [
            "psql",
            "-h",
            Config.DB_HOST,
            "-p",
            Config.DB_PORT,
            "-U",
            Config.DB_USER,
            "-d",
            "postgres",
            "-c",
            f"CREATE DATABASE {Config.DB_NAME};",
        ]
        subprocess.run(create_cmd, env=env, check=True, capture_output=True)

        # Restore backup
        logging.info("Restoring backup...")

        with gzip.open(backup_file, "rb") as f:
            restore_cmd = [
                "psql",
                "-h",
                Config.DB_HOST,
                "-p",
                Config.DB_PORT,
                "-U",
                Config.DB_USER,
                "-d",
                Config.DB_NAME,
                "--quiet",
            ]
            subprocess.run(
                restore_cmd, env=env, stdin=f, check=True, capture_output=True
            )

        logging.info(f"Database restored from {backup_file}")

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        logging.error(f"Restore failed: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Restore failed: {error_msg}")
    except Exception as e:
        logging.error(f"Restore error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Restore error: {str(e)}")


# --- API Endpoints ---


@router.post("/api/backups")
async def create_backup():
    """Create a new database backup"""
    try:
        backup_file = run_pg_dump()
        file_size = backup_file.stat().st_size

        return JSONResponse(
            {
                "message": "Backup created successfully",
                "filename": backup_file.name,
                "size_mb": round(file_size / (1024 * 1024), 2),
            }
        )
    except Exception as e:
        logging.error(f"Error creating backup: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/backups")
async def list_backups():
    """List all available backups"""
    try:
        backups = []
        for backup_file in sorted(BACKUPS_DIR.glob("backup_*.sql.gz"), reverse=True):
            stat = backup_file.stat()
            backups.append(
                {
                    "filename": backup_file.name,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                }
            )
        return JSONResponse(backups)
    except Exception as e:
        logging.error(f"Error listing backups: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/backups/download/{filename}")
async def download_backup(filename: str):
    """Download a backup file"""
    backup_file = BACKUPS_DIR / filename

    if not backup_file.exists() or not backup_file.name.startswith("backup_"):
        raise HTTPException(status_code=404, detail="Backup file not found")

    return FileResponse(
        path=str(backup_file), filename=filename, media_type="application/gzip"
    )


@router.delete("/api/backups/{filename}")
async def delete_backup(filename: str):
    """Delete a backup file"""
    backup_file = BACKUPS_DIR / filename

    if not backup_file.exists() or not backup_file.name.startswith("backup_"):
        raise HTTPException(status_code=404, detail="Backup file not found")

    try:
        backup_file.unlink()
        return JSONResponse({"message": f"Backup {filename} deleted successfully"})
    except Exception as e:
        logging.error(f"Error deleting backup: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/backups/restore")
async def restore_backup(request: RestoreRequest):
    """Restore database from a backup file"""
    backup_file = BACKUPS_DIR / request.filename

    if not backup_file.exists():
        raise HTTPException(status_code=404, detail="Backup file not found")

    try:
        run_pg_restore(backup_file)
        return JSONResponse(
            {"message": f"Database restored successfully from {request.filename}"}
        )
    except Exception as e:
        raise e


# --- Export Endpoints ---


@router.get("/api/export/articles")
async def export_articles(
    request: Request, format: str = Query("csv", regex="^(csv|json)$")
):
    """Export articles in CSV or JSON format"""
    try:
        user = require_request_user(request)
        conn = await get_db_connection()
        rows = await conn.fetch(
            """
            SELECT 
                a.id, a.title, a.link, a.description, a.published, a.category, 
                a.source, COALESCE(uas.is_saved, false) as starred, f.name as feed_name, 
                COALESCE(uas.is_read, false) as is_read
            FROM articles a
            LEFT JOIN feeds f ON a.feed_id = f.id
            LEFT JOIN user_article_state uas ON a.id = uas.article_id AND uas.user_id = $1
            WHERE a.user_id = $1
            ORDER BY a.published_datetime DESC
        """,
            user["id"],
        )
        await database.release_db_connection(conn)

        articles = [dict(row) for row in rows]

        if format == "csv":
            # Create CSV
            output = io.StringIO()
            if articles:
                writer = csv.DictWriter(output, fieldnames=articles[0].keys())
                writer.writeheader()
                writer.writerows(articles)

            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=articles_export_{datetime.now().strftime('%Y%m%d')}.csv"
                },
            )
        else:  # json
            return StreamingResponse(
                iter([json.dumps(articles, indent=2, default=str)]),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=articles_export_{datetime.now().strftime('%Y%m%d')}.json"
                },
            )

    except Exception as e:
        logging.error(f"Error exporting articles: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# --- OPML Endpoints ---


@router.get("/api/opml/export")
async def export_opml(request: Request):
    """Export feeds as OPML file"""
    try:
        user = require_request_user(request)
        conn = await get_db_connection()
        rows = await conn.fetch(
            """
            SELECT f.name, f.url, f.category, f.display_order
            FROM feeds f
            WHERE f.user_id = $1
            ORDER BY f.category, f.display_order, f.name
        """,
            user["id"],
        )
        await database.release_db_connection(conn)

        # Create OPML XML structure
        opml = ET.Element("opml", version="2.0")
        head = ET.SubElement(opml, "head")
        title = ET.SubElement(head, "title")
        title.text = "RSS Newsapp Feed Export"
        date_created = ET.SubElement(head, "dateCreated")
        date_created.text = datetime.now().isoformat()

        body = ET.SubElement(opml, "body")

        # Group feeds by category
        categories = {}
        for row in rows:
            category = row["category"]
            if category not in categories:
                categories[category] = []
            categories[category].append({"name": row["name"], "url": row["url"]})

        # Add feeds to OPML
        for category, feeds in categories.items():
            category_outline = ET.SubElement(
                body, "outline", text=category, title=category
            )
            for feed in feeds:
                ET.SubElement(
                    category_outline,
                    "outline",
                    type="rss",
                    text=feed["name"],
                    title=feed["name"],
                    xmlUrl=feed["url"],
                )

        # Generate XML string
        xml_str = ET.tostring(opml, encoding="unicode", method="xml")
        xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str

        return StreamingResponse(
            iter([xml_str]),
            media_type="application/xml",
            headers={
                "Content-Disposition": f"attachment; filename=feeds_export_{datetime.now().strftime('%Y%m%d')}.opml"
            },
        )

    except Exception as e:
        logging.error(f"Error exporting OPML: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/opml/import")
async def import_opml(request: Request, file: UploadFile = File(...)):
    """Import feeds from OPML file with robust duplicate handling"""
    user = require_request_user(request)
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    # Validate file type
    if not (file.filename.endswith(".opml") or file.filename.endswith(".xml")):
        raise HTTPException(status_code=400, detail="File must be .opml or .xml format")

    try:
        # Read and parse OPML file
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="File is empty")

        root = ET.fromstring(content)

        conn = await get_db_connection()

        imported_count = 0
        skipped_count = 0
        categories_created = []
        errors = []

        # Find all outline elements
        body = root.find("body")
        if body is None:
            raise HTTPException(
                status_code=400, detail="Invalid OPML file: no body element"
            )

        for category_outline in body.findall("outline"):
            # Check if this is a category (has child outlines) or a direct feed
            child_outlines = category_outline.findall("outline")

            if child_outlines:
                # This is a category
                category_name = category_outline.get("text") or category_outline.get(
                    "title", "Uncategorized"
                )

                # Create category if it doesn't exist
                try:
                    # Check if category exists first
                    category_exists = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM categories WHERE user_id = $1 AND LOWER(name) = LOWER($2))",
                        user["id"],
                        category_name,
                    )

                    if not category_exists:
                        await conn.execute(
                            "INSERT INTO categories (user_id, name, priority) SELECT $1, $2, COALESCE(MAX(priority), 0) + 1 FROM categories WHERE user_id = $1",
                            user["id"],
                            category_name,
                        )
                    categories_created.append(category_name)
                    logging.info(f"Created new category: {category_name}")
                except Exception as e:
                    logging.warning(
                        f"Error creating category {category_name}: {str(e)}"
                    )
                    errors.append(f"Category '{category_name}': {str(e)}")

                # Import feeds in this category
                for feed_outline in child_outlines:
                    feed_url = feed_outline.get("xmlUrl")
                    feed_name = feed_outline.get("text") or feed_outline.get(
                        "title", "Unnamed Feed"
                    )

                    if feed_url:
                        try:
                            # Check if feed already exists
                            existing_feed = await conn.fetchrow(
                                "SELECT id, name, category FROM feeds WHERE user_id = $1 AND url = $2",
                                user["id"],
                                feed_url,
                            )

                            if existing_feed:
                                skipped_count += 1
                                logging.info(
                                    f"Skipped existing feed: {feed_name} (already in '{existing_feed['category']}')"
                                )
                            else:
                                category_id = await conn.fetchval(
                                    "SELECT id FROM categories WHERE user_id = $1 AND name = $2",
                                    user["id"],
                                    category_name,
                                )
                                next_order = await conn.fetchval(
                                    "SELECT COALESCE(MAX(display_order), 0) + 1 FROM feeds WHERE user_id = $1 AND category_id = $2",
                                    user["id"],
                                    category_id,
                                )
                                # Insert new feed
                                await conn.execute(
                                    """
                                    INSERT INTO feeds (user_id, category_id, name, url, category, "isActive", display_order, priority)
                                    VALUES ($1, $2, $3, $4, $5, true, $6, $7)
                                    """,
                                    user["id"],
                                    category_id,
                                    feed_name,
                                    feed_url,
                                    category_name,
                                    next_order,
                                    next_order,
                                )
                                imported_count += 1
                                logging.info(
                                    f"Imported feed: {feed_name} -> {category_name}"
                                )
                        except Exception as e:
                            logging.error(
                                f"Error importing feed {feed_name} ({feed_url}): {str(e)}"
                            )
                            skipped_count += 1
                            errors.append(f"Feed '{feed_name}': {str(e)}")
            else:
                # This is an uncategorized feed
                feed_url = category_outline.get("xmlUrl")
                feed_name = category_outline.get("text") or category_outline.get(
                    "title", "Unnamed Feed"
                )

                if feed_url:
                    # Use default "Feeds" category for uncategorized feeds
                    default_category = "Feeds"

                    # Create default category if it doesn't exist
                    try:
                        category_exists = await conn.fetchval(
                            "SELECT EXISTS(SELECT 1 FROM categories WHERE user_id = $1 AND LOWER(name) = LOWER($2))",
                            user["id"],
                            default_category,
                        )

                        if not category_exists:
                            await conn.execute(
                                "INSERT INTO categories (user_id, name, priority) SELECT $1, $2, COALESCE(MAX(priority), 0) + 1 FROM categories WHERE user_id = $1",
                                user["id"],
                                default_category,
                            )
                            if default_category not in categories_created:
                                categories_created.append(default_category)
                                logging.info(
                                    f"Created default category: {default_category}"
                                )
                    except Exception as e:
                        logging.warning(f"Error creating default category: {str(e)}")
                        errors.append(f"Default category: {str(e)}")

                    try:
                        # Check if feed already exists
                        existing_feed = await conn.fetchrow(
                            "SELECT id, name, category FROM feeds WHERE user_id = $1 AND url = $2",
                            user["id"],
                            feed_url,
                        )

                        if existing_feed:
                            skipped_count += 1
                            logging.info(
                                f"Skipped existing feed: {feed_name} (already in '{existing_feed['category']}')"
                            )
                        else:
                            category_id = await conn.fetchval(
                                "SELECT id FROM categories WHERE user_id = $1 AND name = $2",
                                user["id"],
                                default_category,
                            )
                            next_order = await conn.fetchval(
                                "SELECT COALESCE(MAX(display_order), 0) + 1 FROM feeds WHERE user_id = $1 AND category_id = $2",
                                user["id"],
                                category_id,
                            )
                            # Insert new feed
                            await conn.execute(
                                """
                                INSERT INTO feeds (user_id, category_id, name, url, category, "isActive", display_order, priority)
                                VALUES ($1, $2, $3, $4, $5, true, $6, $7)
                                """,
                                user["id"],
                                category_id,
                                feed_name,
                                feed_url,
                                default_category,
                                next_order,
                                next_order,
                            )
                            imported_count += 1
                            logging.info(
                                f"Imported uncategorized feed: {feed_name} -> {default_category}"
                            )
                    except Exception as e:
                        logging.error(
                            f"Error importing uncategorized feed {feed_name} ({feed_url}): {str(e)}"
                        )
                        skipped_count += 1
                        errors.append(f"Feed '{feed_name}': {str(e)}")

        await database.release_db_connection(conn)

        # Build response message
        message = f"OPML import completed: {imported_count} feeds imported, {skipped_count} skipped"
        if categories_created:
            message += f", {len(categories_created)} categories created"

        response_data = {
            "message": message,
            "imported": imported_count,
            "skipped": skipped_count,
            "categories_created": categories_created,
            "success": True,
        }

        if errors:
            response_data["warnings"] = errors[:10]  # Limit to first 10 errors
            logging.warning(f"OPML import completed with {len(errors)} warnings")

        logging.info(
            f"OPML import summary: {imported_count} imported, {skipped_count} skipped, {len(categories_created)} categories created"
        )
        return JSONResponse(response_data)

    except ET.ParseError as e:
        logging.error(f"OPML parse error: {str(e)}")
        raise HTTPException(
            status_code=400, detail=f"Invalid OPML file format: {str(e)}"
        )
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logging.exception(f"Unexpected error importing OPML: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to import OPML: {str(e)}")


# --- Feed Reordering Endpoint ---


@router.post("/api/feeds/reorder")
async def reorder_feeds(request: FeedReorderRequest, http_request: Request):
    """Reorder feeds within a category"""
    try:
        user = require_request_user(http_request)
        conn = await get_db_connection()

        category_id = await conn.fetchval(
            "SELECT id FROM categories WHERE user_id = $1 AND name = $2",
            user["id"],
            request.category,
        )
        if not category_id:
            raise HTTPException(status_code=404, detail="Category not found")

        # Update display_order for each feed
        for index, feed_id in enumerate(request.feed_ids):
            await conn.execute(
                "UPDATE feeds SET display_order = $1 WHERE id = $2 AND user_id = $3 AND category_id = $4",
                index,
                feed_id,
                user["id"],
                category_id,
            )

        await database.release_db_connection(conn)
        return JSONResponse({"message": "Feed order updated successfully"})

    except Exception as e:
        logging.error(f"Error reordering feeds: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
