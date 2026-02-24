import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "finance.db")

# Telegram bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Your Railway URL + /webhook path
PORT = int(os.getenv("PORT", 8443))     # Railway provides PORT env

# Allowed Telegram user IDs (private bot)
def parse_allowed_users():
    raw = os.getenv("ALLOWED_USERS", "")
    if not raw:
        return []
    return [int(uid.strip()) for uid in raw.split(",") if uid.strip()]

ALLOWED_USERS = parse_allowed_users()

# Max history entries to show
HISTORY_LIMIT = 20