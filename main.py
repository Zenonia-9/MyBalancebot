import nest_asyncio
from flask import Flask, render_template, request, jsonify
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Import your own modules
from config import BOT_TOKEN, PORT
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

# ── API routes ──────────────────────────────────────────

@flask_app.route("/api/balance")
def api_balance():
    user_id = request.args.get("user_id", type=int)
    balance, total_in, total_out = db.get_balance_full(user_id)
    month_in, month_out = db.get_current_month_breakdown(user_id)
    resp = jsonify({"balance": balance, "total_in": month_in, "total_out": month_out})
    resp.headers["Cache-Control"] = "no-store"
    return resp

@flask_app.route("/api/update", methods=["POST"])
def api_update():
    data = request.json or {}
    try:
        user_id = int(data["user_id"])
        t_id = int(data["transaction_id"])
        t_type = data["type"] if data["type"] in ("in", "out") else None
        amount = float(data["amount"])
        created_at = data["created_at"]
        if not t_type or amount <= 0 or not created_at:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return jsonify({"status": "error", "error": "Invalid transaction data"}), 400
    affected = db.update_transaction(user_id, t_id, t_type, amount, data.get("note") or None, created_at)
    if not affected:
        return jsonify({"status": "error", "error": "Not found"}), 404
    return jsonify({"status": "ok"})

@flask_app.route("/api/add", methods=["POST"])
def api_add():
    data = request.json
    user_id = data["user_id"]
    raw = str(data["amount"]).lower().replace(",", "").strip()
    try:
        if raw.endswith("k"):
            amount = float(raw[:-1]) * 1_000
        elif raw.endswith("m"):
            amount = float(raw[:-1]) * 1_000_000
        else:
            amount = float(raw)
    except ValueError:
        return jsonify({"status": "error", "error": "Invalid amount"}), 400
    note = data.get("note") or None
    created_at = data.get("created_at") or None  # UTC string or None
    if amount >= 0:
        db.add_transaction(user_id, "in", amount, note, created_at)
    else:
        db.add_transaction(user_id, "out", abs(amount), note, created_at)
    return jsonify({"status": "ok"})

@flask_app.route("/api/history")
def api_history():
    user_id = request.args.get("user_id", type=int)
    limit = min(request.args.get("limit", 20, type=int), 50)  # cap at 50
    offset = request.args.get("offset", 0, type=int)
    rows = db.get_history(user_id, limit, offset)
    transactions = [
        {"id": r[0], "type": r[1], "amount": r[2], "note": r[3], "created_at": r[4]}
        for r in rows
    ]
    return jsonify({"transactions": transactions})

@flask_app.route("/api/delete", methods=["POST"])
def api_delete():
    data = request.json
    user_id = data["user_id"]
    t_id = data["transaction_id"]
    conn = db.get_connection()
    cursor = conn.cursor()
    ph = "%s" if db.is_postgres else "?"
    cursor.execute(f"DELETE FROM transactions WHERE id={ph} AND user_id={ph}", (t_id, user_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    if affected:
        return jsonify({"status": "ok"})
    return jsonify({"status": "error", "error": "Not found"}), 404

@flask_app.route("/api/summary")
def api_summary():
    from datetime import datetime, UTC
    user_id = request.args.get("user_id", type=int)
    period = request.args.get("period", "month")
    now = datetime.now(UTC)

    conn = db.get_connection()
    cursor = conn.cursor()
    ph = "%s" if db.is_postgres else "?"
    base = f"""
        SELECT
            COALESCE(SUM(CASE WHEN type='in' THEN amount ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN type='out' THEN amount ELSE 0 END),0)
        FROM transactions WHERE user_id={ph}
    """
    params = [user_id]

    if period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        base += f" AND created_at >= {ph}"
        params.append(start.strftime("%Y-%m-%d %H:%M:%S"))
    elif period == "year":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        base += f" AND created_at >= {ph}"
        params.append(start.strftime("%Y-%m-%d %H:%M:%S"))

    cursor.execute(base, params)
    total_in, total_out = cursor.fetchone()
    conn.close()
    return jsonify({"total_in": total_in, "total_out": total_out})

@flask_app.route("/api/settings")
def api_get_settings():
    user_id = request.args.get("user_id", type=int)
    return jsonify(db.get_settings(user_id))

@flask_app.route("/api/settings", methods=["POST"])
def api_save_settings():
    data = request.json
    user_id = data["user_id"]
    currency = data.get("currency", "MMK").strip().upper()
    timezone = data.get("timezone", "UTC").strip()
    db.save_settings(user_id, currency, timezone)
    return jsonify({"status": "ok"})

@flask_app.route("/api/summary/monthly")
def api_summary_monthly():
    from datetime import datetime, UTC
    user_id = request.args.get("user_id", type=int)
    year = request.args.get("year", datetime.now(UTC).year, type=int)
    rows = db.get_monthly_breakdown(user_id, year)
    return jsonify({"year": year, "rows": [{"month": r[0], "total_in": r[1], "total_out": r[2]} for r in rows]})

@flask_app.route("/api/summary/yearly")
def api_summary_yearly():
    user_id = request.args.get("user_id", type=int)
    rows = db.get_yearly_breakdown(user_id)
    return jsonify({"rows": [{"year": r[0], "total_in": r[1], "total_out": r[2]} for r in rows]})

# ================= RUNNER =================
if __name__ == "__main__":
    print(f"Starting server on port {PORT}...")
    
    # NOTE: To use 'async' routes in Flask, you must use Flask 2.3+ 
    # or run the app with an ASGI server like Hypercorn or Uvicorn.
    # For local testing, this works:
    flask_app.run(host="0.0.0.0", port=PORT)
