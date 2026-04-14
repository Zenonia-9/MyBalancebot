import sqlite3
import psycopg2
from config import DATABASE_URL

class FinanceDB:
    def __init__(self):
        self.db_url = DATABASE_URL
        self.is_postgres = self.db_url.startswith("postgres://")

        if not self.is_postgres:
            # Create SQLite table if not exists
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
            conn.commit()
            conn.close()
        else:
            # Create PostgreSQL table if not exists
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
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN type='in' THEN amount ELSE 0 END),0) -
                COALESCE(SUM(CASE WHEN type='out' THEN amount ELSE 0 END),0)
            FROM transactions
            WHERE user_id=?
        """, (user_id,))
        balance = cursor.fetchone()[0]
        conn.close()
        return balance

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