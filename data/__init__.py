"""
data - Persistence and data access layer for Fisch Macro.

Owned by Member 69030343 (นายธีระนิตย์ บุญทวี — Backend & Database Developer).
Provides strongly typed models, transactional connection management, repository pattern,
and atomic configuration storage.
"""
from data.config import ConfigManager
from data.database import DatabaseManager, SCHEMA, db, default_manager, get_default_db_path, init_db
from data.models import LoginLog, Session, User
from data.repositories import LogRepository, SessionRepository, UserRepository

__all__ = [
    "DatabaseManager",
    "SCHEMA",
    "db",
    "default_manager",
    "get_default_db_path",
    "init_db",
    "User",
    "Session",
    "LoginLog",
    "UserRepository",
    "SessionRepository",
    "LogRepository",
    "ConfigManager",
]
