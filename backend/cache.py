"""
Cache module for RSS News App
Implements a thread-safe TTL (Time To Live) cache with invalidation support.
"""

import time
import logging
import hashlib
import json
from threading import Lock
from typing import Any, Optional, Dict, Callable
from functools import wraps
from backend.config import Config

# Cache storage: {cache_key: {"data": ..., "expires_at": timestamp}}
_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = Lock()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_cache_key(prefix: str, **kwargs) -> str:
    """
    Generate a unique cache key based on prefix and parameters.

    Args:
        prefix: Cache key prefix (e.g., "feeds", "categories")
        **kwargs: Parameters to include in the cache key

    Returns:
        A unique cache key string
    """
    # Sort kwargs for consistent key generation
    params_str = json.dumps(kwargs, sort_keys=True)
    params_hash = hashlib.md5(params_str.encode()).hexdigest()
    user_namespace = kwargs.get("user_id", "global")
    return f"{prefix}:{user_namespace}:{params_hash}"


def get_from_cache(cache_key: str) -> Optional[Any]:
    """
    Retrieve data from cache if it exists and hasn't expired.

    Args:
        cache_key: The cache key to retrieve

    Returns:
        Cached data if found and valid, None otherwise
    """
    if not Config.CACHE_ENABLED:
        return None

    with _cache_lock:
        if cache_key in _cache:
            cache_entry = _cache[cache_key]

            # Check if cache has expired
            if time.time() < cache_entry["expires_at"]:
                logger.debug(f"Cache HIT: {cache_key}")
                return cache_entry["data"]
            else:
                # Remove expired entry
                logger.debug(f"Cache EXPIRED: {cache_key}")
                del _cache[cache_key]

        logger.debug(f"Cache MISS: {cache_key}")
        return None


def set_in_cache(cache_key: str, data: Any, ttl: Optional[int] = None) -> None:
    """
    Store data in cache with TTL.

    Args:
        cache_key: The cache key to store under
        data: The data to cache
        ttl: Time to live in seconds (defaults to Config.CACHE_DURATION_SECONDS)
    """
    if not Config.CACHE_ENABLED:
        return

    if ttl is None:
        ttl = Config.CACHE_DURATION_SECONDS

    expires_at = time.time() + ttl

    with _cache_lock:
        _cache[cache_key] = {"data": data, "expires_at": expires_at}
        logger.debug(f"Cache SET: {cache_key} (TTL: {ttl}s)")


def invalidate_cache(pattern: Optional[str] = None) -> int:
    """
    Invalidate cache entries matching a pattern or all entries if no pattern provided.

    Args:
        pattern: Optional pattern to match cache keys (e.g., "feeds:" to clear all feed caches)

    Returns:
        Number of cache entries invalidated
    """
    with _cache_lock:
        if pattern is None:
            # Clear all cache
            count = len(_cache)
            _cache.clear()
            logger.info(f"Cache INVALIDATED ALL: {count} entries cleared")
            return count
        else:
            # Clear entries matching pattern
            keys_to_delete = [key for key in _cache.keys() if key.startswith(pattern)]
            for key in keys_to_delete:
                del _cache[key]
            logger.info(
                f"Cache INVALIDATED: {len(keys_to_delete)} entries matching '{pattern}'"
            )
            return len(keys_to_delete)


def invalidate_feeds_cache(user_id: int | None = None) -> None:
    """Invalidate feed-related cache entries, optionally scoped to one user."""
    if user_id is None:
        invalidate_cache("feeds:")
        invalidate_cache("categories:")
        invalidate_cache("feeds_config:")
        invalidate_cache("article_full_text:")
        logger.info("Feed caches invalidated globally")
        return

    patterns = [
        f"feeds:{user_id}:",
        f"categories:{user_id}:",
        f"feeds_config:{user_id}:",
        f"article_full_text:{user_id}:",
    ]
    invalidated = 0
    with _cache_lock:
        keys_to_delete = [
            key
            for key in list(_cache.keys())
            if any(key.startswith(pattern) for pattern in patterns)
        ]
        for key in keys_to_delete:
            del _cache[key]
        invalidated = len(keys_to_delete)

    logger.info("Feed caches invalidated for user %s: %s entries", user_id, invalidated)


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.

    Returns:
        Dictionary with cache stats
    """
    with _cache_lock:
        total_entries = len(_cache)
        expired_entries = sum(
            1 for entry in _cache.values() if time.time() >= entry["expires_at"]
        )
        active_entries = total_entries - expired_entries

        return {
            "enabled": Config.CACHE_ENABLED,
            "total_entries": total_entries,
            "active_entries": active_entries,
            "expired_entries": expired_entries,
            "ttl_seconds": Config.CACHE_DURATION_SECONDS,
        }


def clean_expired_entries() -> int:
    """
    Remove expired entries from cache.

    Returns:
        Number of entries cleaned
    """
    with _cache_lock:
        current_time = time.time()
        keys_to_delete = [
            key for key, entry in _cache.items() if current_time >= entry["expires_at"]
        ]

        for key in keys_to_delete:
            del _cache[key]

        if keys_to_delete:
            logger.debug(
                f"Cache CLEANUP: {len(keys_to_delete)} expired entries removed"
            )

        return len(keys_to_delete)


def cached_endpoint(cache_key_prefix: str):
    """
    Decorator for FastAPI endpoints to add caching support.

    Usage:
        @app.get("/api/endpoint")
        @cached_endpoint("endpoint")
        async def my_endpoint(param1: str, param2: int):
            ...

    Args:
        cache_key_prefix: Prefix for the cache key
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function arguments
            cache_key = generate_cache_key(cache_key_prefix, **kwargs)

            # Try to get from cache
            cached_data = get_from_cache(cache_key)
            if cached_data is not None:
                return cached_data

            # Execute function if not in cache
            result = await func(*args, **kwargs)

            # Store in cache
            set_in_cache(cache_key, result)

            return result

        return wrapper

    return decorator
