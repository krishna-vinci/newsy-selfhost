import os
import asyncio
import logging
from datetime import datetime, timedelta

import nest_asyncio
import psycopg2
import pytz

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Apply nest_asyncio to support nested event loops (needed for uvicorn or interactive environments)
nest_asyncio.apply()

# --- Configuration & Database Setup ---
from config import Config  # Ensure Config has DB_*, TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY, YOUR_SITE_URL, YOUR_SITE_NAME, etc.

# (If needed, you may define get_db_connection() here—but in our setup main.py has DB functions.)

# Define Indian Standard Time
IST = pytz.timezone("Asia/Kolkata")

# --- Telegram & OpenRouter Setup ---
TELEGRAM_BOT_TOKEN = Config.TELEGRAM_BOT_TOKEN
openai.api_key = Config.OPENROUTER_API_KEY
openai.api_base = "https://openrouter.ai/api/v1"

# Use your working OpenRouter client; we import OpenAI from openai.
from openai import OpenAI
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
    # In your telegram_bot module, we assume the DB table exists.
    from config import Config  # if needed for DB settings
    # For simplicity, use a local DB connection (or import a shared function)
    try:
        # Here you can call your DB helper if available.
        # Otherwise, a simple implementation:
        import psycopg2
        conn_str = f"dbname={Config.DB_NAME} user={Config.DB_USER} password={Config.DB_PASSWORD} host={Config.DB_HOST} port={Config.DB_PORT}"
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor()
        chat_id = update.effective_chat.id
        username = update.effective_chat.username or ""
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
    from config import Config
    try:
        import psycopg2
        conn_str = f"dbname={Config.DB_NAME} user={Config.DB_USER} password={Config.DB_PASSWORD} host={Config.DB_HOST} port={Config.DB_PORT}"
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor()
        chat_id = update.effective_chat.id
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
        # In this isolated module, we assume the DB is set up.
        # For demonstration, we won’t connect to the DB; you can integrate your DB query logic.
        # Here, we simulate fetching recent articles from the DB:
        simulated_articles = (
            "**Article One**\n\nDescription of article one.\n\n[Read more](http://example.com/article1)\n\n---\n\n"
            "**Article Two**\n\nDescription of article two.\n\n[Read more](http://example.com/article2)"
        )
        prompt = (
            f"Below are recent articles:\n\n{simulated_articles}\n\n"
            f"For the query: \"{query_text}\", list the articles relevant to the query. "
            f"Output in markdown format with the title as a header, followed by the description and a 'Read more' link. "
            f"If no article is relevant, respond with 'No relevant articles found.'"
        )
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
    await telegram_app.run_polling(close_loop=False)

# --- Notification Helper ---
def notify_subscribers(article: dict):
    """
    Call this function after inserting a new article.
    'article' should be a dict with keys: title, description, link, and published.
    """
    async def _notify():
        try:
            message = (
                f"📰 *New Article Alert!*\n\n"
                f"**{article['title']}**\n\n"
                f"{article['description']}\n\n"
                f"Published: {article['published']}\n\n"
                f"[Read more]({article['link']})"
            )
            await telegram_app.bot.send_message(
                chat_id=None,  # We will send to each subscriber individually
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            # Alternatively, you could fetch subscribers from your DB and loop over them.
        except Exception as e:
            logging.exception("Error sending notification")
    asyncio.create_task(_notify())

# Expose functions for integration
__all__ = [
    "telegram_app",
    "start_polling",
    "notify_subscribers",
]
