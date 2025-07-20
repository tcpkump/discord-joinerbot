import os
from typing import List

import psycopg


class Database:
    def __init__(self):
        self.connection_string = os.environ.get(
            "DATABASE_URL", "postgresql://localhost/joinerbot"
        )
        self._connection = None
        self._init_tables()

    def _get_connection(self):
        if self._connection is None or self._connection.closed:
            self._connection = psycopg.connect(self.connection_string)
        return self._connection

    def _init_tables(self):
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS callers (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL UNIQUE,
                    username VARCHAR(255) NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )  # user_id/username are separate because people like to change names :)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS join_leave_history (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(255) NOT NULL,
                    action VARCHAR(10) NOT NULL CHECK (action IN ('join', 'leave')),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_history_user_id ON join_leave_history(user_id);
                CREATE INDEX IF NOT EXISTS idx_history_timestamp ON join_leave_history(timestamp);
            """
            )
            conn.commit()

    def get_num_callers(self) -> int:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM callers")
            result = cur.fetchone()
            return result[0] if result else 0

    def get_callers(self) -> List[tuple]:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id, username, joined_at FROM callers ORDER BY joined_at"
            )
            return cur.fetchall()

    def add_caller(self, user_id: int, username: str) -> bool:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO callers (user_id, username) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING",
                    (user_id, username),
                )
                conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            conn.rollback()
            print(f"Error adding caller: {e}")
            return False

    def del_caller(self, user_id: int) -> bool:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM callers WHERE user_id = %s", (user_id,))
                conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            conn.rollback()
            print(f"Error deleting caller: {e}")
            return False

    def log_join_leave(self, user_id: int, username: str, action: str) -> bool:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO join_leave_history (user_id, username, action) VALUES (%s, %s, %s)",
                    (user_id, username, action),
                )
                conn.commit()
                return True
        except Exception as e:
            conn.rollback()
            print(f"Error logging {action} event: {e}")
            return False

    def was_recently_connected(self, user_id: int, minutes: int = 5) -> bool:
        """Check if user was connected within the last X minutes"""
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM join_leave_history
                WHERE user_id = %s
                AND action = 'join'
                AND timestamp > NOW() - INTERVAL '%s minutes'
                """,
                (user_id, minutes),
            )
            result = cur.fetchone()
            return (result[0] if result else 0) > 0

    def close(self):
        if self._connection and not self._connection.closed:
            self._connection.close()
