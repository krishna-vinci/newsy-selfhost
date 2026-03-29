from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from threading import Lock
from typing import Any


DEFAULT_CACHE_MAX_AGE_SECONDS = 24 * 60 * 60


class TTLFileCache:
    def __init__(
        self,
        cache_dir: str = ".cache",
        max_cache_age_seconds: int = DEFAULT_CACHE_MAX_AGE_SECONDS,
        cleanup_interval_seconds: int = 5 * 60,
    ) -> None:
        requested_cache_dir = Path(cache_dir)
        try:
            requested_cache_dir.mkdir(parents=True, exist_ok=True)
            self.cache_dir = requested_cache_dir
        except PermissionError:
            fallback_cache_dir = Path(tempfile.gettempdir()) / "rss-gen-cache"
            fallback_cache_dir.mkdir(parents=True, exist_ok=True)
            self.cache_dir = fallback_cache_dir
        self.max_cache_age_seconds = max_cache_age_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self._lock = Lock()
        self._last_cleanup_at = 0.0

    def _path_for_key(self, key: str) -> Path:
        safe_key = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in key)
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str, ttl_seconds: int) -> Any | None:
        path = self._path_for_key(key)
        if not path.exists():
            return None

        with self._lock:
            self._maybe_cleanup_expired_files()
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None

        cached_at = payload.get("cached_at", 0)
        if time.time() - cached_at > ttl_seconds:
            return None
        return payload.get("value")

    def set(self, key: str, value: Any) -> None:
        path = self._path_for_key(key)
        temp_path = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        payload = {"cached_at": time.time(), "value": value}

        with self._lock:
            self._maybe_cleanup_expired_files()
            temp_path.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(temp_path, path)

    def _maybe_cleanup_expired_files(self) -> None:
        now = time.time()
        if now - self._last_cleanup_at < self.cleanup_interval_seconds:
            return
        self._cleanup_expired_files(now)
        self._last_cleanup_at = now

    def _cleanup_expired_files(self, now: float | None = None) -> None:
        current_time = now or time.time()
        cutoff = current_time - self.max_cache_age_seconds
        for file_path in self.cache_dir.glob("*.json"):
            try:
                if file_path.stat().st_mtime < cutoff:
                    file_path.unlink(missing_ok=True)
            except OSError:
                continue
