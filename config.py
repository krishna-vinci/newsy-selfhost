# config.py
import os
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env


def _get_env_bool(name: str) -> bool | None:
    value = os.getenv(name)
    if value is None:
        return None
    return value.lower() == "true"


class Config:
    # Database Settings
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_NAME = os.getenv("DB_NAME")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")

    # FastAPI Settings
    FASTAPI_HOST_PORT = os.getenv("FASTAPI_HOST_PORT", "8765")

    # Redis Settings
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))

    # Other Services / API Keys
    RSSBRIDGE_HOST = os.getenv("RSSBRIDGE_HOST", "http://91/99.19.202:3333")
    NITTER_URL = os.getenv("NITTER_URL", "https://nitter.space")

    # Data Retention Policy
    DEFAULT_ARTICLE_RETENTION_DAYS = int(
        os.getenv("DEFAULT_ARTICLE_RETENTION_DAYS", 30)
    )

    # Search Settings
    SEARCH_SCORE_THRESHOLD = float(os.getenv("SEARCH_SCORE_THRESHOLD", "60.0"))

    # New variables for the Telegram bot and AI
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    PUBLIC_URL = os.getenv("PUBLIC_URL")
    WEB_PUSH_VAPID_PUBLIC_KEY = os.getenv("WEB_PUSH_VAPID_PUBLIC_KEY")
    WEB_PUSH_VAPID_PRIVATE_KEY = os.getenv("WEB_PUSH_VAPID_PRIVATE_KEY")
    WEB_PUSH_SUBJECT = os.getenv("WEB_PUSH_SUBJECT")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

    # OpenAI-Compatible API Settings for AI Content Filtering
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL = os.getenv(
        "OPENAI_BASE_URL", "https://api.openai.com/v1"
    )  # Default to OpenAI
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "100"))
    OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.3"))

    # CORS Settings
    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3456,http://127.0.0.1:3456,http://localhost:8667,http://go-scheduler:8667",
    ).split(",")

    # Authentication Settings
    AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "change-me-in-production")
    AUTH_ACCESS_TTL_MINUTES = int(os.getenv("AUTH_ACCESS_TTL_MINUTES", "15"))
    AUTH_REFRESH_TTL_DAYS = int(os.getenv("AUTH_REFRESH_TTL_DAYS", "30"))
    AUTH_ALLOW_PUBLIC_SIGNUP = (
        os.getenv("AUTH_ALLOW_PUBLIC_SIGNUP", "true").lower() == "true"
    )
    AUTH_COOKIE_SECURE = _get_env_bool("AUTH_COOKIE_SECURE")
    if AUTH_COOKIE_SECURE is None:
        AUTH_COOKIE_SECURE = False
    AUTH_ACCESS_COOKIE_NAME = os.getenv("AUTH_ACCESS_COOKIE_NAME", "newsy_access_token")
    AUTH_REFRESH_COOKIE_NAME = os.getenv(
        "AUTH_REFRESH_COOKIE_NAME", "newsy_refresh_token"
    )
    INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

    # Cache Settings
    CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    CACHE_DURATION_SECONDS = int(
        os.getenv("CACHE_DURATION_SECONDS", "300")
    )  # Default: 5 minutes
