"""
data/database.py - Database connection management, schemas, and safe migrations.

Designed by Member 69030343 (นายธีระนิตย์ บุญทวี — Backend & Database Developer).
Ensures atomic transactions, PRAGMA foreign_keys = ON, and non-destructive migrations.
"""
from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager
from typing import Callable, Generator, List, Optional, Tuple

DEFAULT_DB_FILENAME = "app.db"

# Canonical SQLite DDL Schema matching existing project contract
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,      -- Unique identifier
    username           TEXT    NOT NULL UNIQUE COLLATE NOCASE,  -- Case-insensitive username
    password_hash      TEXT    NOT NULL,                        -- PBKDF2 password hash
    nickname           TEXT    NOT NULL,                        -- User display / nickname
    birthday           TEXT    NOT NULL,                        -- 'YYYY-MM-DD'
    role               TEXT    NOT NULL DEFAULT 'user',         -- 'admin' or 'user'
    active             INTEGER NOT NULL DEFAULT 1,              -- 1 = active, 0 = disabled
    failed_count       INTEGER NOT NULL DEFAULT 0,              -- Consecutive failed logins
    locked_until       REAL    NOT NULL DEFAULT 0,              -- Lockout expiration epoch seconds
    reset_failed_count INTEGER NOT NULL DEFAULT 0,              -- Consecutive failed reset attempts
    reset_locked_until REAL    NOT NULL DEFAULT 0,
    created_at         REAL    NOT NULL,                        -- Registration timestamp
    last_login         REAL                                     -- Most recent login timestamp
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,                                -- SHA-256 hash of session token
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at REAL    NOT NULL,
    created_at REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS login_logs (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    ok       INTEGER NOT NULL,                                  -- 1 = success, 0 = failure
    ip       TEXT,
    at       REAL    NOT NULL
);

-- Performance indices
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_users_nickname_birthday ON users(nickname, birthday);
"""

MIGRATIONS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS _schema_migrations (
    version    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    applied_at REAL NOT NULL
);
"""


def get_default_db_path() -> str:
    """Resolve database path from FISCH_DB environment variable or default to project app.db."""
    env_path = os.environ.get("FISCH_DB")
    if env_path:
        return env_path
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, DEFAULT_DB_FILENAME)


class DatabaseManager:
    """Manages SQLite database connections, transactional integrity, and migrations."""

    def __init__(self, db_path: Optional[str] = None, timeout: float = 10.0):
        self._custom_db_path = db_path
        self.timeout = timeout

    @property
    def db_path(self) -> str:
        """Dynamically resolve database path if not explicitly overridden."""
        return self._custom_db_path or get_default_db_path()

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Transactional connection context manager.
        - Enables PRAGMA foreign_keys = ON.
        - Sets row_factory = sqlite3.Row.
        - Commits automatically on normal block completion.
        - Rolls back all uncommitted work on any exception.
        - Always closes the connection.
        """
        path = self.db_path
        dir_name = os.path.dirname(path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)

        conn = sqlite3.connect(path, timeout=self.timeout)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self) -> None:
        """Create baseline schema and run any registered migrations."""
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            conn.executescript(MIGRATIONS_TABLE_DDL)

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        with self.connect() as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name = ?",
                (table_name,),
            )
            return cur.fetchone()[0] > 0

    def get_applied_migrations(self) -> List[int]:
        """Return list of applied migration version numbers."""
        if not self.table_exists("_schema_migrations"):
            return []
        with self.connect() as conn:
            rows = conn.execute("SELECT version FROM _schema_migrations ORDER BY version").fetchall()
            return [int(r["version"]) for r in rows]

    def apply_migration(self, version: int, name: str, migration_fn: Callable[[sqlite3.Connection], None]) -> bool:
        """
        Safely execute a migration in a transaction and record it in _schema_migrations.
        Returns True if migration was applied, False if already applied.
        """
        self.init_db()
        with self.connect() as conn:
            applied = conn.execute(
                "SELECT COUNT(*) FROM _schema_migrations WHERE version = ?", (version,)
            ).fetchone()[0] > 0
            if applied:
                return False

            # Execute migration logic
            migration_fn(conn)
            conn.execute(
                "INSERT INTO _schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, time.time()),
            )
            return True


# Default global instance
default_manager = DatabaseManager()


@contextmanager
def db(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Compatibility context manager function mirroring original database.db()."""
    mgr = DatabaseManager(db_path) if db_path else default_manager
    with mgr.connect() as conn:
        yield conn


def init_db(db_path: Optional[str] = None) -> None:
    """Compatibility database initialization function mirroring original database.init_db()."""
    mgr = DatabaseManager(db_path) if db_path else default_manager
    mgr.init_db()
