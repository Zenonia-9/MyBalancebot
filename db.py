import sqlite3
import psycopg2
from config import DATABASE_URL

class FinanceDB:
    def __init__(self):
        self.db_url = DATABASE_URL
        self.is_postgres = self.db_url.startswith("postgres://")

        if not self.is_postgres:
            conn = sqlite3.connect(self.db_url)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    type TEXT,
                    amount REAL,
                    note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_settings(
                    user_id INTEGER PRIMARY KEY,
                    currency TEXT DEFAULT 'MMK',
                    timezone TEXT DEFAULT 'UTC'
                )
            """)
            conn.commit()
            conn.close()
        else:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions(
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    type TEXT,
                    amount DOUBLE PRECISION,
                    note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_settings(
                    user_id BIGINT PRIMARY KEY,
                    currency TEXT DEFAULT 'MMK',
                    timezone TEXT DEFAULT 'UTC'
                )
            """)
            conn.commit()
            conn.close()

    def get_connection(self):
        if self.is_postgres:
            return psycopg2.connect(self.db_url)
        return sqlite3.connect(self.db_url)

    def add_transaction(self, user_id: int, t_type: str, amount: float, note: str = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO transactions (user_id, type, amount, note) VALUES (?, ?, ?, ?)",
            (user_id, t_type, amount, note)
        )
        conn.commit()
        conn.close()

    def get_balance(self, user_id: int) -> float:
        return self.get_balance_full(user_id)[0]

    def get_balance_full(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN type='in' THEN amount ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN type='out' THEN amount ELSE 0 END),0)
            FROM transactions
            WHERE user_id=?
        """, (user_id,))
        total_in, total_out = cursor.fetchone()
        conn.close()
        return total_in - total_out, total_in, total_out

    def get_transaction(self, user_id: int, t_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, type, amount, note, created_at
            FROM transactions
            WHERE user_id=? AND id=?
        """, (user_id, t_id))

        row = cursor.fetchone()
        conn.close()
        return row
    
    def get_monthly_breakdown(self, user_id: int, year: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        if self.is_postgres:
            cursor.execute("""
                SELECT
                    EXTRACT(MONTH FROM created_at)::int AS month,
                    COALESCE(SUM(CASE WHEN type='in' THEN amount ELSE 0 END),0),
                    COALESCE(SUM(CASE WHEN type='out' THEN amount ELSE 0 END),0)
                FROM transactions
                WHERE user_id=%s AND EXTRACT(YEAR FROM created_at)=%s
                GROUP BY month ORDER BY month
            """, (user_id, year))
        else:
            cursor.execute("""
                SELECT
                    CAST(strftime('%m', created_at) AS INTEGER) AS month,
                    COALESCE(SUM(CASE WHEN type='in' THEN amount ELSE 0 END),0),
                    COALESCE(SUM(CASE WHEN type='out' THEN amount ELSE 0 END),0)
                FROM transactions
                WHERE user_id=? AND strftime('%Y', created_at)=?
                GROUP BY month ORDER BY month
            """, (user_id, str(year)))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_yearly_breakdown(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        if self.is_postgres:
            cursor.execute("""
                SELECT
                    EXTRACT(YEAR FROM created_at)::int AS year,
                    COALESCE(SUM(CASE WHEN type='in' THEN amount ELSE 0 END),0),
                    COALESCE(SUM(CASE WHEN type='out' THEN amount ELSE 0 END),0)
                FROM transactions
                WHERE user_id=%s
                GROUP BY year ORDER BY year
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT
                    CAST(strftime('%Y', created_at) AS INTEGER) AS year,
                    COALESCE(SUM(CASE WHEN type='in' THEN amount ELSE 0 END),0),
                    COALESCE(SUM(CASE WHEN type='out' THEN amount ELSE 0 END),0)
                FROM transactions
                WHERE user_id=?
                GROUP BY year ORDER BY year
            """, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_settings(self, user_id: int) -> dict:
        conn = self.get_connection()
        cursor = conn.cursor()
        ph = "%s" if self.is_postgres else "?"
        cursor.execute(f"SELECT currency, timezone FROM user_settings WHERE user_id={ph}", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"currency": row[0], "timezone": row[1]}
        return {"currency": "MMK", "timezone": "UTC"}

    def save_settings(self, user_id: int, currency: str, timezone: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        if self.is_postgres:
            cursor.execute("""
                INSERT INTO user_settings (user_id, currency, timezone)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET currency=EXCLUDED.currency, timezone=EXCLUDED.timezone
            """, (user_id, currency, timezone))
        else:
            cursor.execute("""
                INSERT INTO user_settings (user_id, currency, timezone)
                VALUES (?, ?, ?)
                ON CONFLICT (user_id) DO UPDATE SET currency=excluded.currency, timezone=excluded.timezone
            """, (user_id, currency, timezone))
        conn.commit()
        conn.close()

    def get_history(self, user_id: int, limit: int = 20, offset: int = 0):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, type, amount, note, created_at
            FROM transactions
            WHERE user_id=?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (user_id, limit, offset))

        rows = cursor.fetchall()
        conn.close()
        return rows