"""
data/models.py - Strongly typed data models for Fisch Macro persistence layer.

Designed by Member 69030343 (นายธีระนิตย์ บุญทวี — Backend & Database Developer).
Preserves 100% field compatibility with existing SQLite schema (app.db).
"""
from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Union


@dataclass
class User:
    """User account model matching the 'users' table."""
    username: str
    password_hash: str
    nickname: str
    birthday: str
    id: Optional[int] = None
    role: str = "user"
    active: int = 1
    failed_count: int = 0
    locked_until: float = 0.0
    reset_failed_count: int = 0
    reset_locked_until: float = 0.0
    created_at: float = 0.0
    last_login: Optional[float] = None

    @classmethod
    def from_row(cls, row: Union[sqlite3.Row, Dict[str, Any]]) -> "User":
        """Instantiate User from sqlite3.Row or dict mapping."""
        if row is None:
            raise ValueError("Cannot instantiate User from None row")
        return cls(
            id=row["id"],
            username=row["username"],
            password_hash=row["password_hash"],
            nickname=row["nickname"],
            birthday=row["birthday"],
            role=row["role"] if "role" in row.keys() else "user",
            active=int(row["active"]) if "active" in row.keys() else 1,
            failed_count=int(row["failed_count"]) if "failed_count" in row.keys() else 0,
            locked_until=float(row["locked_until"]) if "locked_until" in row.keys() else 0.0,
            reset_failed_count=int(row["reset_failed_count"]) if "reset_failed_count" in row.keys() else 0,
            reset_locked_until=float(row["reset_locked_until"]) if "reset_locked_until" in row.keys() else 0.0,
            created_at=float(row["created_at"]) if "created_at" in row.keys() else 0.0,
            last_login=float(row["last_login"]) if row["last_login"] is not None else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to complete dictionary representation."""
        return asdict(self)

    def to_public_dict(self) -> Dict[str, Any]:
        """Return safe user dictionary excluding hashes and security counters."""
        return {
            "id": self.id,
            "username": self.username,
            "nickname": self.nickname,
            "birthday": self.birthday,
            "role": self.role,
            "active": bool(self.active),
        }

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_active(self) -> bool:
        return bool(self.active)


@dataclass
class Session:
    """Authentication session token model matching the 'sessions' table."""
    token_hash: str
    user_id: int
    expires_at: float
    created_at: float

    @classmethod
    def from_row(cls, row: Union[sqlite3.Row, Dict[str, Any]]) -> "Session":
        if row is None:
            raise ValueError("Cannot instantiate Session from None row")
        return cls(
            token_hash=row["token_hash"],
            user_id=row["user_id"],
            expires_at=float(row["expires_at"]),
            created_at=float(row["created_at"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def is_expired(self, current_time: float) -> bool:
        return self.expires_at < current_time


@dataclass
class LoginLog:
    """Security audit log record matching the 'login_logs' table."""
    at: float
    ok: int
    id: Optional[int] = None
    username: Optional[str] = None
    ip: Optional[str] = None

    @classmethod
    def from_row(cls, row: Union[sqlite3.Row, Dict[str, Any]]) -> "LoginLog":
        if row is None:
            raise ValueError("Cannot instantiate LoginLog from None row")
        return cls(
            id=row["id"],
            username=row["username"],
            ok=int(row["ok"]),
            ip=row["ip"],
            at=float(row["at"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
