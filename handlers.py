import datetime

import csv
import io

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from db import FinanceDB
from config import ALLOWED_USERS, HISTORY_LIMIT

db = FinanceDB()
EXPECTED_HEADERS = {"id", "type", "amount", "note", "created_at"}

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
        await update.message.reply_text("Usage: /out <amount> <optional note>")
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

async def handle_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        return

    args = context.args
    now = datetime.datetime.now()

    # 👉 If no args → show buttons
    if not args:
        return await summary_menu(update, context)

    conn = db.get_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            COALESCE(SUM(CASE WHEN type='in' THEN amount ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN type='out' THEN amount ELSE 0 END),0)
        FROM transactions
        WHERE user_id=?
    """

    params = [user_id]
    title = ""

    # ======================
    # YEARLY
    # ======================
    if args[0].lower() == "year":
        if len(args) == 2:
            year = int(args[1])
            start = datetime.datetime(year, 1, 1)
            end = datetime.datetime(year, 12, 31)
            title = f"Year {year}"

            query += " AND created_at BETWEEN ? AND ?"
            params.extend([start, end])
        else:
            title = "All Time"

    # ======================
    # MONTHLY
    # ======================
    elif args[0].lower() == "month":
        if len(args) >= 2:
            try:
                month = int(args[1])
                year = int(args[2]) if len(args) == 3 else now.year

                start = datetime.datetime(year, month, 1)

                if month == 12:
                    end = datetime.datetime(year + 1, 1, 1)
                else:
                    end = datetime.datetime(year, month + 1, 1)

                title = f"{start.strftime('%B %Y')}"

                query += " AND created_at BETWEEN ? AND ?"
                params.extend([start, end])

            except:
                await update.message.reply_text("Invalid month/year format.")
                return
        else:
            await update.message.reply_text(
                "Usage:\n"
                "/summary month <month> [year]\n"
                "Example: /summary month 4 2025"
            )
            return

    else:
        await update.message.reply_text("Invalid usage.")
        return

    cursor.execute(query, params)
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

async def summary_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("📅 This Month", callback_data="summary_month"),
            InlineKeyboardButton("📆 This Year", callback_data="summary_year"),
        ],
        [
            InlineKeyboardButton("📊 All Time", callback_data="summary_all"),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Choose summary type:",
        reply_markup=reply_markup
    )

async def summary_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_cb = update.callback_query
    await query_cb.answer()

    user_id = query_cb.from_user.id
    now = datetime.datetime.now()

    conn = db.get_connection()
    cursor = conn.cursor()

    base_query = """
        SELECT 
            COALESCE(SUM(CASE WHEN type='in' THEN amount ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN type='out' THEN amount ELSE 0 END),0)
        FROM transactions
        WHERE user_id=?
    """

    params = [user_id]
    title = ""

    if query_cb.data == "summary_month":
        start = now.replace(day=1)
        end = now
        title = now.strftime("%B %Y")

        base_query += " AND created_at BETWEEN ? AND ?"
        params.extend([start, end])

    elif query_cb.data == "summary_year":
        start = datetime.datetime(now.year, 1, 1)
        end = datetime.datetime(now.year, 12, 31)
        title = f"Year {now.year}"

        base_query += " AND created_at BETWEEN ? AND ?"
        params.extend([start, end])

    elif query_cb.data == "summary_all":
        title = "All Time"

    cursor.execute(base_query, params)
    total_in, total_out = cursor.fetchone()
    conn.close()

    balance = total_in - total_out

    msg = (
        f"📊 {title} Summary\n"
        f"💰 Income: {int(total_in)}\n"
        f"💸 Expenses: {int(total_out)}\n"
        f"💹 Net: {int(balance)}"
    )

    await query_cb.edit_message_text(msg)

async def handle_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        return

    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, type, amount, note, created_at
        FROM transactions
        WHERE user_id=?
        ORDER BY created_at ASC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("No data to export.")
        return

    # 👉 Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(["id", "type", "amount", "note", "created_at"])

    # Data
    writer.writerows(rows)

    output.seek(0)

    # 👉 Send as file
    await update.message.reply_document(
        document=io.BytesIO(output.getvalue().encode()),
        filename="transactions_backup.csv",
        caption="📦 Your backup file"
    )


async def handle_import(update, context):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        return

    if not update.message.document:
        await update.message.reply_text("Please send a CSV file.")
        return

    file = await update.message.document.get_file()
    file_bytes = await file.download_as_bytearray()

    stream = io.StringIO(file_bytes.decode())
    reader = csv.DictReader(stream)

    # ======================
    # 🔍 STEP 1: Validate headers
    # ======================
    headers = set(reader.fieldnames or [])
    if headers != EXPECTED_HEADERS:
        await update.message.reply_text(
            "❌ Invalid CSV format.\n"
            f"Expected columns: {', '.join(EXPECTED_HEADERS)}"
        )
        return

    rows = list(reader)

    if not rows:
        await update.message.reply_text("❌ CSV file is empty.")
        return

    # ======================
    # 🔍 STEP 2: Validate rows
    # ======================
    for i, row in enumerate(rows, start=1):
        try:
            if row["type"] not in ("in", "out"):
                raise ValueError("type must be 'in' or 'out'")

            float(row["amount"])  # validate number

            if not row["created_at"]:
                raise ValueError("created_at is required")

        except Exception as e:
            await update.message.reply_text(
                f"❌ Error in row {i}:\n{str(e)}"
            )
            return

    # ======================
    # 💣 STEP 3: Safe to delete + import
    # ======================
    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        # 🗑 STEP 1: Delete old data ONLY after validation
        cursor.execute("DELETE FROM transactions WHERE user_id=?", (user_id,))

        # 📦 STEP 2: Prepare batch data
        data = [
            (
                user_id,
                row["type"],
                float(row["amount"]),
                row["note"],
                row["created_at"]
            )
            for row in rows
        ]

        # ⚡ STEP 3: Bulk insert (faster + cheaper CPU)
        cursor.executemany("""
            INSERT INTO transactions (user_id, type, amount, note, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, data)

        conn.commit()

        await update.message.reply_text(
            f"✅ Import successful!\n"
            f"🗑 Old data replaced\n"
            f"📥 {len(data)} transactions imported"
        )

    except Exception as e:
        conn.rollback()
        await update.message.reply_text(f"❌ Import failed:\n{str(e)}")

    finally:
        conn.close()
