"""
data/repositories.py - Data Access Layer (DAL) implementing the Repository pattern.

Designed by Member 69030343 (นายธีระนิตย์ บุญทวี — Backend & Database Developer).
Encapsulates all SQL queries, ensuring decoupled business logic and transaction safety.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union

from data.database import DatabaseManager, default_manager
from data.models import LoginLog, Session, User


class UserRepository:
    """Repository handling all database operations for User accounts."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or default_manager

    def count(self, conn: Optional[sqlite3.Connection] = None) -> int:
        """Count total registered users."""
        if conn is not None:
            return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        with self.db.connect() as c:
            return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def get_by_id(self, user_id: int, conn: Optional[sqlite3.Connection] = None) -> Optional[User]:
        """Fetch a user by numeric primary key."""
        query = "SELECT * FROM users WHERE id = ?"
        if conn is not None:
            row = conn.execute(query, (user_id,)).fetchone()
            return User.from_row(row) if row else None
        with self.db.connect() as c:
            row = c.execute(query, (user_id,)).fetchone()
            return User.from_row(row) if row else None

    def get_by_username(self, username: str, conn: Optional[sqlite3.Connection] = None) -> Optional[User]:
        """Fetch a user by unique username (case-insensitive via NOCASE collation)."""
        query = "SELECT * FROM users WHERE username = ?"
        if conn is not None:
            row = conn.execute(query, (username,)).fetchone()
            return User.from_row(row) if row else None
        with self.db.connect() as c:
            row = c.execute(query, (username,)).fetchone()
            return User.from_row(row) if row else None

    def find_by_nickname_and_birthday(
        self, nickname: str, birthday: str, conn: Optional[sqlite3.Connection] = None
    ) -> List[User]:
        """Find users matching normalized nickname and birthday."""
        clean_nick = (nickname or "").strip().lower()
        query = "SELECT * FROM users WHERE LOWER(TRIM(nickname)) = ? AND birthday = ?"
        if conn is not None:
            rows = conn.execute(query, (clean_nick, birthday)).fetchall()
            return [User.from_row(r) for r in rows]
        with self.db.connect() as c:
            rows = c.execute(query, (clean_nick, birthday)).fetchall()
            return [User.from_row(r) for r in rows]

    def create(
        self,
        username: str,
        password_hash: str,
        nickname: str,
        birthday: str,
        role: str,
        created_at: float,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """Insert a new user and return the assigned row ID."""
        sql = (
            "INSERT INTO users (username, password_hash, nickname, birthday, role, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)"
        )
        params = (username, password_hash, nickname, birthday, role, created_at)
        if conn is not None:
            cur = conn.execute(sql, params)
            return cur.lastrowid
        with self.db.connect() as c:
            cur = c.execute(sql, params)
            return cur.lastrowid

    def record_login_success(
        self, user_id: int, last_login_ts: float, conn: Optional[sqlite3.Connection] = None
    ) -> None:
        """Reset failed attempts and record successful login timestamp."""
        sql = "UPDATE users SET failed_count = 0, locked_until = 0, last_login = ? WHERE id = ?"
        if conn is not None:
            conn.execute(sql, (last_login_ts, user_id))
        else:
            with self.db.connect() as c:
                c.execute(sql, (last_login_ts, user_id))

    def set_failed_count(
        self, user_id: int, fails: int, conn: Optional[sqlite3.Connection] = None
    ) -> None:
        """Update consecutive failed login count."""
        sql = "UPDATE users SET failed_count = ? WHERE id = ?"
        if conn is not None:
            conn.execute(sql, (fails, user_id))
        else:
            with self.db.connect() as c:
                c.execute(sql, (fails, user_id))

    def lock_user(
        self, user_id: int, locked_until_ts: float, conn: Optional[sqlite3.Connection] = None
    ) -> None:
        """Reset failed count and set lockout expiry timestamp."""
        sql = "UPDATE users SET failed_count = 0, locked_until = ? WHERE id = ?"
        if conn is not None:
            conn.execute(sql, (locked_until_ts, user_id))
        else:
            with self.db.connect() as c:
                c.execute(sql, (locked_until_ts, user_id))

    def set_reset_failed_count(
        self, user_id: int, fails: int, conn: Optional[sqlite3.Connection] = None
    ) -> None:
        """Update consecutive failed password reset attempt count."""
        sql = "UPDATE users SET reset_failed_count = ? WHERE id = ?"
        if conn is not None:
            conn.execute(sql, (fails, user_id))
        else:
            with self.db.connect() as c:
                c.execute(sql, (fails, user_id))

    def lock_reset(
        self, user_id: int, locked_until_ts: float, conn: Optional[sqlite3.Connection] = None
    ) -> None:
        """Reset reset_failed_count and set reset lockout expiry timestamp."""
        sql = "UPDATE users SET reset_failed_count = 0, reset_locked_until = ? WHERE id = ?"
        if conn is not None:
            conn.execute(sql, (locked_until_ts, user_id))
        else:
            with self.db.connect() as c:
                c.execute(sql, (locked_until_ts, user_id))

    def reset_password_success(
        self, user_id: int, new_password_hash: str, conn: Optional[sqlite3.Connection] = None
    ) -> None:
        """Reset user password and clear all lockout counters."""
        sql = (
            "UPDATE users SET password_hash = ?, failed_count = 0, locked_until = 0, "
            "reset_failed_count = 0, reset_locked_until = 0 WHERE id = ?"
        )
        if conn is not None:
            conn.execute(sql, (new_password_hash, user_id))
        else:
            with self.db.connect() as c:
                c.execute(sql, (new_password_hash, user_id))

    def update_password(
        self, user_id: int, new_password_hash: str, conn: Optional[sqlite3.Connection] = None
    ) -> None:
        """Update password without clearing reset lockout counters."""
        sql = "UPDATE users SET password_hash = ? WHERE id = ?"
        if conn is not None:
            conn.execute(sql, (new_password_hash, user_id))
        else:
            with self.db.connect() as c:
                c.execute(sql, (new_password_hash, user_id))

    def admin_reset_password(
        self, user_id: int, new_password_hash: str, conn: Optional[sqlite3.Connection] = None
    ) -> bool:
        """Admin force reset password and clear login lockouts."""
        sql = "UPDATE users SET password_hash = ?, failed_count = 0, locked_until = 0 WHERE id = ?"
        if conn is not None:
            return conn.execute(sql, (new_password_hash, user_id)).rowcount > 0
        with self.db.connect() as c:
            return c.execute(sql, (new_password_hash, user_id)).rowcount > 0

    def set_active(
        self, user_id: int, active: bool, conn: Optional[sqlite3.Connection] = None
    ) -> bool:
        """Activate or deactivate a user account."""
        val = 1 if active else 0
        sql = "UPDATE users SET active = ? WHERE id = ?"
        if conn is not None:
            return conn.execute(sql, (val, user_id)).rowcount > 0
        with self.db.connect() as c:
            return c.execute(sql, (val, user_id)).rowcount > 0

    def delete(self, user_id: int, conn: Optional[sqlite3.Connection] = None) -> bool:
        """Delete user by ID. Cascades to delete related sessions."""
        sql = "DELETE FROM users WHERE id = ?"
        if conn is not None:
            return conn.execute(sql, (user_id,)).rowcount > 0
        with self.db.connect() as c:
            return c.execute(sql, (user_id,)).rowcount > 0

    def list_all(self, conn: Optional[sqlite3.Connection] = None) -> List[User]:
        """Fetch all users sorted by ID."""
        sql = (
            "SELECT id, username, password_hash, nickname, birthday, role, active, "
            "failed_count, locked_until, reset_failed_count, reset_locked_until, created_at, last_login "
            "FROM users ORDER BY id"
        )
        if conn is not None:
            rows = conn.execute(sql).fetchall()
            return [User.from_row(r) for r in rows]
        with self.db.connect() as c:
            rows = c.execute(sql).fetchall()
            return [User.from_row(r) for r in rows]


class SessionRepository:
    """Repository handling all database operations for authentication sessions."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or default_manager

    def create(
        self,
        token_hash: str,
        user_id: int,
        expires_at: float,
        created_at: float,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        """Persist a new session token hash."""
        sql = "INSERT INTO sessions (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)"
        params = (token_hash, user_id, expires_at, created_at)
        if conn is not None:
            conn.execute(sql, params)
        else:
            with self.db.connect() as c:
                c.execute(sql, params)

    def get_by_token_hash(
        self, token_hash: str, conn: Optional[sqlite3.Connection] = None
    ) -> Optional[Session]:
        """Fetch a session record by token hash."""
        sql = "SELECT * FROM sessions WHERE token_hash = ?"
        if conn is not None:
            row = conn.execute(sql, (token_hash,)).fetchone()
            return Session.from_row(row) if row else None
        with self.db.connect() as c:
            row = c.execute(sql, (token_hash,)).fetchone()
            return Session.from_row(row) if row else None

    def get_session_with_user(
        self, token_hash: str, conn: Optional[sqlite3.Connection] = None
    ) -> Optional[sqlite3.Row]:
        """Fetch session joined with corresponding user account details."""
        sql = (
            "SELECT u.id, u.username, u.nickname, u.birthday, u.role, u.active, s.expires_at "
            "FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?"
        )
        if conn is not None:
            return conn.execute(sql, (token_hash,)).fetchone()
        with self.db.connect() as c:
            return c.execute(sql, (token_hash,)).fetchone()

    def delete(self, token_hash: str, conn: Optional[sqlite3.Connection] = None) -> bool:
        """Delete single session by token hash."""
        sql = "DELETE FROM sessions WHERE token_hash = ?"
        if conn is not None:
            return conn.execute(sql, (token_hash,)).rowcount > 0
        with self.db.connect() as c:
            return c.execute(sql, (token_hash,)).rowcount > 0

    def delete_expired(self, now_ts: float, conn: Optional[sqlite3.Connection] = None) -> int:
        """Prune all expired sessions."""
        sql = "DELETE FROM sessions WHERE expires_at < ?"
        if conn is not None:
            return conn.execute(sql, (now_ts,)).rowcount
        with self.db.connect() as c:
            return c.execute(sql, (now_ts,)).rowcount

    def delete_all_for_user(self, user_id: int, conn: Optional[sqlite3.Connection] = None) -> int:
        """Invalidate all sessions belonging to user_id."""
        sql = "DELETE FROM sessions WHERE user_id = ?"
        if conn is not None:
            return conn.execute(sql, (user_id,)).rowcount
        with self.db.connect() as c:
            return c.execute(sql, (user_id,)).rowcount

    def delete_other_user_sessions(
        self, user_id: int, keep_token_hash: str, conn: Optional[sqlite3.Connection] = None
    ) -> int:
        """Invalidate all user sessions except the specified active session."""
        sql = "DELETE FROM sessions WHERE user_id = ? AND token_hash != ?"
        if conn is not None:
            return conn.execute(sql, (user_id, keep_token_hash)).rowcount
        with self.db.connect() as c:
            return c.execute(sql, (user_id, keep_token_hash)).rowcount


class LogRepository:
    """Repository handling all database operations for security login audit logs."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or default_manager

    def log(
        self,
        username: Optional[str],
        ok: bool,
        ip: Optional[str],
        at_ts: float,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """Insert a login audit entry."""
        sql = "INSERT INTO login_logs (username, ok, ip, at) VALUES (?, ?, ?, ?)"
        params = (username, 1 if ok else 0, ip, at_ts)
        if conn is not None:
            cur = conn.execute(sql, params)
            return cur.lastrowid
        with self.db.connect() as c:
            cur = c.execute(sql, params)
            return cur.lastrowid

    def get_recent_logs(
        self, limit: int = 100, conn: Optional[sqlite3.Connection] = None
    ) -> List[LoginLog]:
        """Fetch most recent login audit logs."""
        sql = "SELECT id, username, ok, ip, at FROM login_logs ORDER BY id DESC LIMIT ?"
        if conn is not None:
            rows = conn.execute(sql, (limit,)).fetchall()
            return [LoginLog.from_row(r) for r in rows]
        with self.db.connect() as c:
            rows = c.execute(sql, (limit,)).fetchall()
            return [LoginLog.from_row(r) for r in rows]
