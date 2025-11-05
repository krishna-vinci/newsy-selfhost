# config.py
import os
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env

class Config:
    # Database Settings
    DB_USER = os.getenv("DB_USER", "krishna")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "1122")
    DB_NAME = os.getenv("DB_NAME", "youtube_cm")
    DB_HOST = os.getenv("DB_HOST", "db")
    DB_PORT = os.getenv("DB_PORT", "5432")
    
    # FastAPI Settings
    FASTAPI_HOST_PORT = os.getenv("FASTAPI_HOST_PORT", "8666")
    
    # Other Services / API Keys
    RSSBRIDGE_HOST = os.getenv("RSSBRIDGE_HOST", "http://91/99.19.202:3333")
    NITTER_URL = os.getenv("NITTER_URL", "https://nitter.space")

    # Data Retention Policy
    DEFAULT_ARTICLE_RETENTION_DAYS = int(os.getenv("DEFAULT_ARTICLE_RETENTION_DAYS", 30))

     # New variables for the Telegram bot and AI
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:2112")  # default for local
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
