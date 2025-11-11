# config.py
import os
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env

class Config:
    # Database Settings
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_NAME = os.getenv("DB_NAME")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    
    # FastAPI Settings
    FASTAPI_HOST_PORT = os.getenv("FASTAPI_HOST_PORT", "8666")
    
    # Redis Settings
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    
    # Other Services / API Keys
    RSSBRIDGE_HOST = os.getenv("RSSBRIDGE_HOST", "http://91/99.19.202:3333")
    NITTER_URL = os.getenv("NITTER_URL", "https://nitter.space")

    # Data Retention Policy
    DEFAULT_ARTICLE_RETENTION_DAYS = int(os.getenv("DEFAULT_ARTICLE_RETENTION_DAYS", 30))
    
    # Search Settings
    SEARCH_SCORE_THRESHOLD = float(os.getenv("SEARCH_SCORE_THRESHOLD", "60.0"))

     # New variables for the Telegram bot and AI
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:2112")  # default for local
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    
    # OpenAI-Compatible API Settings for AI Content Filtering
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")  # Default to OpenAI
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "100"))
    OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.3"))

    # CORS Settings
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(',')
