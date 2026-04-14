import os
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import ALLOWED_USERS, BOT_TOKEN, WEBHOOK_URL, PORT
from handlers import handle_income, handle_expense, handle_balance, handle_history, handle_delete, handle_summary, summary_callback, handle_export, handle_import

# Create bot application
app = ApplicationBuilder().token(BOT_TOKEN).build()

# Register handlers
app.add_handler(CommandHandler("in", handle_income))
app.add_handler(CommandHandler("out", handle_expense))
app.add_handler(CommandHandler("balance", handle_balance))
app.add_handler(CommandHandler("history", handle_history))
app.add_handler(CommandHandler("delete", handle_delete))
app.add_handler(CommandHandler("summary", handle_summary))
app.add_handler(CallbackQueryHandler(summary_callback, pattern="^summary_"))
app.add_handler(CommandHandler("export", handle_export))
app.add_handler(CommandHandler("import", handle_import))
app.add_handler(MessageHandler(filters.Document.ALL, handle_import))

# Optional: /start handler
async def start(update, context):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        return
    await update.message.reply_text(
        "👋 Welcome! Use /in, /out, /balance, /history, /delete, /summary, /export to track your money."
    )
app.add_handler(CommandHandler("start", start))

USE_WEBHOOK = os.getenv("USE_WEBHOOK", "false").lower() == "true"

if __name__ == "__main__":
    print("Bot is running…")
    if USE_WEBHOOK:
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL
        )
    else:
        app.run_polling()