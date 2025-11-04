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
    PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
    RSSBRIDGE_HOST = os.getenv("RSSBRIDGE_HOST", "http://91/99.19.202:3333")
    METUBE_URL = os.getenv("METUBE_URL", "http://192.168.0.122:8081")
    NITTER_URL = os.getenv("NITTER_URL", "https://nitter.space")

     # New variables for the Telegram bot and AI
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:2112")  # default for local
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    
    # Paths
    PROJECTS_ROOT = os.getenv("PROJECTS_ROOT", "/app/data/youtube-videos")
    DAILY_REPORT_DIR = os.getenv("DAILY_REPORT_DIR", "/app/data/daily_report")
