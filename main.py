import nest_asyncio
from flask import Flask, render_template, request, jsonify
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Import your own modules
from config import BOT_TOKEN, PORT, WEBHOOK_URL
from handlers import *
from db import FinanceDB


# This is the magic line that prevents "Event loop is closed"
nest_asyncio.apply()
# ================= BOT SETUP =================
# We initialize the application but we DO NOT call .run_polling()
tg_app = ApplicationBuilder().token(BOT_TOKEN).build()

# Add handlers (keeping your existing logic)
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("in", handle_income))
tg_app.add_handler(CommandHandler("out", handle_expense))
tg_app.add_handler(CommandHandler("balance", handle_balance))
tg_app.add_handler(CommandHandler("history", handle_history))
tg_app.add_handler(CallbackQueryHandler(history_callback, pattern="^history_"))
tg_app.add_handler(CommandHandler("delete", handle_delete))
tg_app.add_handler(CallbackQueryHandler(delete_ui_callback, pattern="^del"))
tg_app.add_handler(CommandHandler("summary", handle_summary))
tg_app.add_handler(CallbackQueryHandler(summary_callback, pattern="^summary_"))
tg_app.add_handler(CommandHandler("export", handle_export))
tg_app.add_handler(CommandHandler("import", handle_import))
tg_app.add_handler(MessageHandler(filters.Document.ALL, handle_import))

# ================= FLASK SETUP =================
db = FinanceDB()
flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return render_template("index.html")

# Define an initialization function
async def init_bot():
    if not tg_app.running:
        await tg_app.initialize()
        await tg_app.start()
        print("Bot initialized and started!")

# TELEGRAM WEBHOOK ENDPOINT
@flask_app.route("/webhook", methods=["POST"])
async def telegram_webhook():
    """Receive updates from Telegram and push them to the PTB application"""
    try:
        # Ensure the bot is initialized and started
        # Run the initialization in the current loop
        await init_bot()
            
        json_data = request.get_json(force=True)
        update = Update.de_json(json_data, tg_app.bot)
        
        # Process the update
        await tg_app.process_update(update)
        return "OK", 200
    except Exception as e:
        print(f"Error processing update: {e}")
        return "Error", 500

# Your existing API routes
@flask_app.route("/api/balance")
def api_balance():
    user_id = request.args.get("user_id", type=int)
    return jsonify({"balance": db.get_balance(user_id)})

@flask_app.route("/api/add", methods=["POST"])
def api_add():
    data = request.json
    user_id = data["user_id"]
    amount = float(data["amount"])
    note = data.get("note", "")
    if amount >= 0:
        db.add_transaction(user_id, "in", amount, note)
    else:
        db.add_transaction(user_id, "out", abs(amount), note)
    return jsonify({"status": "ok"})

# ================= RUNNER =================
if __name__ == "__main__":
    print(f"Starting server on port {PORT}...")
    
    # NOTE: To use 'async' routes in Flask, you must use Flask 2.3+ 
    # or run the app with an ASGI server like Hypercorn or Uvicorn.
    # For local testing, this works:
    flask_app.run(host="0.0.0.0", port=PORT)