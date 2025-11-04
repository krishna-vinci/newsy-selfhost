import os
import asyncio
import logging
from datetime import datetime, timedelta

import nest_asyncio
import psycopg2
import pytz

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Apply nest_asyncio to support nested event loops
nest_asyncio.apply()

# --- Configuration Setup ---
from config import Config  # Ensure Config loads DB_*, TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY, YOUR_SITE_URL, etc.

# --- Database Setup ---
def get_db_connection():
    conn_str = (
        f"dbname={Config.DB_NAME} "
        f"user={Config.DB_USER} "
        f"password={Config.DB_PASSWORD} "
        f"host={Config.DB_HOST} "
        f"port={Config.DB_PORT}"
    )
    return psycopg2.connect(conn_str)

# Indian Standard Time
IST = pytz.timezone("Asia/Kolkata")

# --- Telegram & OpenRouter Setup ---
TELEGRAM_BOT_TOKEN = Config.TELEGRAM_BOT_TOKEN  # from .env via Config

# For OpenRouter, use your working client pattern:
from openai import OpenAI  # using the OpenAI client compatible with OpenRouter

# Instantiate the client
# (Make sure your Config.OPENROUTER_API_KEY is set correctly)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=Config.OPENROUTER_API_KEY,
)

# Create the Telegram bot Application (using the async API)
telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("Received /start command from chat_id: %s", update.effective_chat.id)
    text = (
        "Welcome to the Workflow Bot!\n\n"
        "Commands:\n"
        "• /subscribe – Subscribe for new article notifications\n"
        "• /unsubscribe – Unsubscribe from notifications\n"
        "• /query <your query> – Search articles via AI\n"
        "• /help – Show available commands"
    )
    await update.message.reply_text(text)

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    username = update.effective_chat.username or ""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO telegram_subscribers (chat_id, username) VALUES (%s, %s) ON CONFLICT (chat_id) DO NOTHING",
            (chat_id, username)
        )
        conn.commit()
        cur.close()
        conn.close()
        await update.message.reply_text("Subscribed successfully! You will now receive notifications.")
    except Exception as e:
        logging.exception("Subscription error")
        await update.message.reply_text("Subscription failed. Please try again later.")

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM telegram_subscribers WHERE chat_id = %s", (chat_id,))
        conn.commit()
        cur.close()
        conn.close()
        await update.message.reply_text("Unsubscribed successfully.")
    except Exception as e:
        logging.exception("Unsubscription error")
        await update.message.reply_text("Unsubscription failed. Please try again later.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Available commands:\n"
        "/start – Start the bot\n"
        "/subscribe – Subscribe for notifications\n"
        "/unsubscribe – Unsubscribe from notifications\n"
        "/query <query> – Search articles using AI\n"
        "/help – Show this help message"
    )
    await update.message.reply_text(text)

async def query_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a query. E.g., /query Trump and Musk")
        return
    query_text = " ".join(context.args)
    response_text = await handle_ai_query(query_text)
    await update.message.reply_text(response_text, disable_web_page_preview=True)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Unknown command. Use /help to see available commands.")

# --- AI Query Handling ---
async def handle_ai_query(query_text: str) -> str:
    try:
        # Fetch recent articles (last 90 days) from your database
        conn = get_db_connection()
        cur = conn.cursor()
        three_months_ago = datetime.now(IST) - timedelta(days=90)
        cur.execute(
            """
            SELECT title, description, link 
            FROM "YouTube-articles" 
            WHERE published_datetime >= %s 
            ORDER BY published_datetime DESC 
            LIMIT 10
            """,
            (three_months_ago,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        articles = "\n".join(
            f"Title: {row[0]}\nDescription: {row[1]}\nLink: {row[2]}"
            for row in rows
        )
        prompt = (
            f"Given the following recent articles:\n\n{articles}\n\n"
            f"Please answer the following query concisely:\n{query_text}"
        )

        # Use your working OpenRouter client pattern:
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": Config.YOUR_SITE_URL if hasattr(Config, "YOUR_SITE_URL") else "",
                "X-Title": Config.YOUR_SITE_NAME if hasattr(Config, "YOUR_SITE_NAME") else "",
            },
            model="google/gemma-3-27b-it",
            messages=[{"role": "user", "content": prompt}],
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.exception("Error in AI query")
        return "Sorry, there was an error processing your query."

# --- Setup Telegram Handlers ---
def setup_telegram_handlers():
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("subscribe", subscribe))
    telegram_app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(CommandHandler("query", query_command))
    telegram_app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    logging.info("Telegram handlers set up.")

setup_telegram_handlers()

# --- Polling Runner ---
async def start_polling():
    logging.info("Starting Telegram bot polling in integrated mode...")
    # Use close_loop=False to avoid closing the already running event loop.
    await telegram_app.run_polling(close_loop=False)

# --- Notification Helper ---
def notify_subscribers(article: dict):
    """
    Call this function after inserting a new article.
    'article' should be a dict with keys: title, description, link, and published.
    """
    async def _notify():
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT chat_id FROM telegram_subscribers")
            subscribers = cur.fetchall()
            cur.close()
            conn.close()
            message = (
                f"📰 *New Article Alert!*\n\n"
                f"*{article['title']}*\n"
                f"{article['description']}\n"
                f"Published: {article['published']}\n"
                f"[Read more]({article['link']})"
            )
            for (chat_id,) in subscribers:
                try:
                    await telegram_app.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode="Markdown",
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logging.exception("Failed to notify subscriber %s", chat_id)
        except Exception as e:
            logging.exception("Error notifying subscribers")
    asyncio.create_task(_notify())

# --- Expose Functions for Main App Integration ---
__all__ = [
    "telegram_app",
    "start_polling",
    "notify_subscribers",
]
