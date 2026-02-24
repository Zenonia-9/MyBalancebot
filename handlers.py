import datetime

from telegram import Update
from telegram.ext import ContextTypes
from db import FinanceDB
from config import ALLOWED_USERS, HISTORY_LIMIT

db = FinanceDB()

# Check if user is allowed
def is_allowed(user_id):
    return user_id in ALLOWED_USERS

def parse_amount(amount_input) -> float:
    # Make sure it is a string
    amount_str = str(amount_input).lower().replace(",", "").strip()

    if amount_str.endswith("k"):
        return float(amount_str[:-1]) * 1_000
    elif amount_str.endswith("m"):
        return float(amount_str[:-1]) * 1_000_000
    else:
        return float(amount_str)

def format_amount_shorthand(amount: float) -> str:
    if amount >= 1_000_000:
        value = amount / 1_000_000
        return f"{value:.2f}m" if value % 1 else f"{int(value)}m"
    elif amount >= 1_000:
        value = amount / 1_000
        return f"{value:.2f}k" if value % 1 else f"{int(value)}k"
    else:
        return f"{int(amount)}"
       
# /in command
async def handle_income(update, context):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        return

    if not context.args:
        await update.message.reply_text("Usage: /in <amount> <optional note>")
        return

    try:
        # First arg = amount
        raw_amount = context.args[0]
        amount = parse_amount(raw_amount)

        # Everything after first arg = note
        note = " ".join(context.args[1:]) if len(context.args) > 1 else None

        db.add_transaction(user_id, "in", amount, note)
        await update.message.reply_text(f"✅ Added income: {int(amount)} {note or ''}")

    except ValueError:
        await update.message.reply_text("Invalid amount. Example: /in 10k Pocket Money")

# /out command
async def handle_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        return

    if not context.args:
        await update.message.reply_text("Usage: /in <amount> <optional note>")
        return
    
    try:
        raw_amount = context.args[0]
        amount = parse_amount(raw_amount)
        note = " ".join(context.args[1:]) if len(context.args) > 1 else None
        db.add_transaction(user_id, "out", amount, note)
        await update.message.reply_text(f"✅ Added expense: {amount} {note or ''}")
    except ValueError:
        await update.message.reply_text("Invalid amount. Example: /out 10k Coffee")

# /balance command
async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        return
    balance = db.get_balance(user_id)
    await update.message.reply_text(f"💹 Your balance is: {balance}")

# /history command
async def handle_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        return

    history = db.get_history(user_id, HISTORY_LIMIT)
    if not history:
        await update.message.reply_text("No transactions yet.")
        return

    msg = "<b>ID | Type | Amount | Note | Date</b>\n"
    for t in history:
        t_id, t_type, amount, note, created_at = t
        note = note or ""
        icon = "💰" if t_type == "in" else "💸"
        msg += f"{t_id} | {icon} | {format_amount_shorthand(amount)} | <b>{note}</b> | {created_at}\n"

    await update.message.reply_text(msg, parse_mode="HTML")

async def handle_delete(update, context):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        return

    if not context.args:
        await update.message.reply_text("Usage: /delete <transaction_id>")
        return

    try:
        t_id = int(context.args[0])
        # Delete only if belongs to this user
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (t_id, user_id))
        if cursor.rowcount == 0:
            await update.message.reply_text(f"No transaction found with ID {t_id}")
        else:
            await update.message.reply_text(f"✅ Transaction {t_id} deleted")
        conn.commit()
        conn.close()
    except ValueError:
        await update.message.reply_text("Transaction ID must be a number")

async def handle_summary(update, context):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        return

    period = context.args[0].lower() if context.args else "week"
    now = datetime.datetime.now()
    conn = db.get_connection()
    cursor = conn.cursor()

    if period == "week":
        start = now - datetime.timedelta(days=7)
        title = "Last 7 days"
    elif period == "month":
        start = now - datetime.timedelta(days=30)
        title = "Last 30 days"
    else:
        await update.message.reply_text("Usage: /summary [week|month]")
        return

    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN type='in' THEN amount ELSE 0 END),0) AS total_in,
            COALESCE(SUM(CASE WHEN type='out' THEN amount ELSE 0 END),0) AS total_out
        FROM transactions
        WHERE user_id=? AND created_at>=?
    """, (user_id, start))
    total_in, total_out = cursor.fetchone()
    conn.close()

    balance = total_in - total_out
    msg = (
        f"📊 {title} Summary\n"
        f"💰 Income: {int(total_in)}\n"
        f"💸 Expenses: {int(total_out)}\n"
        f"💹 Net: {int(balance)}"
    )
    await update.message.reply_text(msg)