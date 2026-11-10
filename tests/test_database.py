"""
tests/test_database.py - Comprehensive automated tests for Fisch Macro persistence layer.

Authored for Member 69030343 (นายธีระนิตย์ บุญทวี — Backend & Database Developer).
Validates SQLite foreign key cascade, transaction rollback, repository operations,
schema migrations, and atomic configuration storage.
"""
import os
import sqlite3
import tempfile
import time
import pytest

from data.config import ConfigManager
from data.database import DatabaseManager
from data.models import LoginLog, Session, User
from data.repositories import LogRepository, SessionRepository, UserRepository


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database file for testing and cleanup afterwards."""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_fisch_")
    os.close(fd)
    if os.path.exists(path):
        os.remove(path)
    mgr = DatabaseManager(path)
    mgr.init_db()
    yield mgr
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass


def test_database_init_and_tables(temp_db):
    """Verify that all core tables and indices are created upon initialization."""
    assert temp_db.table_exists("users")
    assert temp_db.table_exists("sessions")
    assert temp_db.table_exists("login_logs")
    assert temp_db.table_exists("_schema_migrations")

    with temp_db.connect() as conn:
        indices = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        idx_names = [r["name"] for r in indices]
        assert "idx_sessions_user_id" in idx_names
        assert "idx_sessions_expires_at" in idx_names
        assert "idx_users_nickname_birthday" in idx_names


def test_foreign_key_cascade_deletion(temp_db):
    """Verify PRAGMA foreign_keys = ON and ON DELETE CASCADE on sessions when user is deleted."""
    user_repo = UserRepository(temp_db)
    session_repo = SessionRepository(temp_db)

    now = time.time()
    user_id = user_repo.create(
        username="cascade_test",
        password_hash="hash123",
        nickname="CascadeUser",
        birthday="1999-12-31",
        role="user",
        created_at=now,
    )
    assert user_id > 0

    # Insert two active sessions
    session_repo.create("hash_token_1", user_id, now + 3600, now)
    session_repo.create("hash_token_2", user_id, now + 7200, now)

    # Confirm sessions exist
    s1 = session_repo.get_by_token_hash("hash_token_1")
    s2 = session_repo.get_by_token_hash("hash_token_2")
    assert s1 is not None and s1.user_id == user_id
    assert s2 is not None and s2.user_id == user_id

    # Delete the user; sessions must be cascade deleted automatically
    deleted = user_repo.delete(user_id)
    assert deleted is True

    # Assert sessions were cascade deleted
    assert session_repo.get_by_token_hash("hash_token_1") is None
    assert session_repo.get_by_token_hash("hash_token_2") is None


def test_transaction_rollback_on_error(temp_db):
    """Verify that any exception within connect() context triggers an atomic rollback."""
    user_repo = UserRepository(temp_db)
    initial_count = user_repo.count()

    with pytest.raises(RuntimeError):
        with temp_db.connect() as conn:
            user_repo.create(
                username="rollback_user",
                password_hash="pw_hash",
                nickname="Rollback",
                birthday="1990-01-01",
                role="user",
                created_at=time.time(),
                conn=conn,
            )
            # Deliberately raise exception before context exit
            raise RuntimeError("Forced simulation error")

    # Verify user was NOT committed
    assert user_repo.count() == initial_count
    assert user_repo.get_by_username("rollback_user") is None


def test_user_repository_crud_and_lockouts(temp_db):
    """Verify complete User lifecycle, case-insensitive usernames, and lockout tracking."""
    user_repo = UserRepository(temp_db)
    now = time.time()

    # Create first user (admin)
    uid = user_repo.create(
        username="FisherKing",
        password_hash="secret_hash",
        nickname="The King",
        birthday="1985-06-15",
        role="admin",
        created_at=now,
    )
    assert uid > 0

    # Case-insensitive username lookup
    u_exact = user_repo.get_by_username("FisherKing")
    u_lower = user_repo.get_by_username("fisherking")
    u_upper = user_repo.get_by_username("FISHERKING")
    assert u_exact is not None and u_exact.id == uid
    assert u_lower is not None and u_lower.id == uid
    assert u_upper is not None and u_upper.id == uid
    assert u_exact.role == "admin"
    assert u_exact.is_admin is True
    assert u_exact.is_active is True

    # Nickname and birthday search
    matched = user_repo.find_by_nickname_and_birthday("the king", "1985-06-15")
    assert len(matched) == 1
    assert matched[0].id == uid

    # Lockout counters
    user_repo.set_failed_count(uid, 3)
    u_updated = user_repo.get_by_id(uid)
    assert u_updated.failed_count == 3

    # Lockout triggered
    user_repo.lock_user(uid, now + 60.0)
    u_locked = user_repo.get_by_id(uid)
    assert u_locked.failed_count == 0
    assert u_locked.locked_until == pytest.approx(now + 60.0, rel=1e-2)

    # Successful login resets lockout
    user_repo.record_login_success(uid, now + 100.0)
    u_success = user_repo.get_by_id(uid)
    assert u_success.failed_count == 0
    assert u_success.locked_until == 0.0
    assert u_success.last_login == pytest.approx(now + 100.0, rel=1e-2)

    # Reset password lockouts
    user_repo.set_reset_failed_count(uid, 4)
    assert user_repo.get_by_id(uid).reset_failed_count == 4
    user_repo.lock_reset(uid, now + 300.0)
    u_reset_locked = user_repo.get_by_id(uid)
    assert u_reset_locked.reset_failed_count == 0
    assert u_reset_locked.reset_locked_until == pytest.approx(now + 300.0, rel=1e-2)

    # Successful reset clears all lockouts
    user_repo.reset_password_success(uid, "brand_new_hash")
    u_reset_done = user_repo.get_by_id(uid)
    assert u_reset_done.password_hash == "brand_new_hash"
    assert u_reset_done.reset_locked_until == 0.0

    # Account deactivation / activation
    user_repo.set_active(uid, False)
    assert user_repo.get_by_id(uid).is_active is False
    user_repo.set_active(uid, True)
    assert user_repo.get_by_id(uid).is_active is True


def test_session_repository_lifecycle_and_pruning(temp_db):
    """Verify session storage, token lookup, join query, and expiry pruning."""
    user_repo = UserRepository(temp_db)
    session_repo = SessionRepository(temp_db)
    now = time.time()

    uid = user_repo.create("angler", "hash", "Angler", "2001-01-01", "user", now)

    # Session 1: expired
    session_repo.create("expired_hash", uid, expires_at=now - 100, created_at=now - 200)
    # Session 2: active
    session_repo.create("active_hash_1", uid, expires_at=now + 3600, created_at=now)
    # Session 3: active
    session_repo.create("active_hash_2", uid, expires_at=now + 7200, created_at=now)

    # Test join query
    joined = session_repo.get_session_with_user("active_hash_1")
    assert joined is not None
    assert joined["username"] == "angler"
    assert joined["nickname"] == "Angler"
    assert joined["active"] == 1

    # Prune expired
    pruned = session_repo.delete_expired(now)
    assert pruned == 1
    assert session_repo.get_by_token_hash("expired_hash") is None
    assert session_repo.get_by_token_hash("active_hash_1") is not None

    # Delete other sessions keeping active_hash_1
    session_repo.delete_other_user_sessions(uid, keep_token_hash="active_hash_1")
    assert session_repo.get_by_token_hash("active_hash_1") is not None
    assert session_repo.get_by_token_hash("active_hash_2") is None


def test_login_log_repository(temp_db):
    """Verify recording and querying login audit logs."""
    log_repo = LogRepository(temp_db)
    now = time.time()

    log_repo.log("user_alpha", ok=True, ip="127.0.0.1", at_ts=now)
    log_repo.log("user_beta", ok=False, ip="192.168.1.50", at_ts=now + 1)
    log_repo.log("user_gamma", ok=True, ip="10.0.0.2", at_ts=now + 2)

    logs = log_repo.get_recent_logs(limit=2)
    assert len(logs) == 2
    # Ordered by ID DESC
    assert logs[0].username == "user_gamma"
    assert logs[0].ok == 1
    assert logs[1].username == "user_beta"
    assert logs[1].ok == 0


def test_schema_migrations(temp_db):
    """Verify safe idempotent schema migration execution."""
    applied_before = temp_db.get_applied_migrations()
    assert applied_before == []

    # Migration 1: Add a test column safely
    def migration_add_notes(conn: sqlite3.Connection):
        conn.execute("ALTER TABLE users ADD COLUMN notes TEXT DEFAULT ''")

    success = temp_db.apply_migration(version=1, name="add_users_notes", migration_fn=migration_add_notes)
    assert success is True
    assert 1 in temp_db.get_applied_migrations()

    # Re-applying same migration should be an idempotent no-op returning False
    success_retry = temp_db.apply_migration(version=1, name="add_users_notes", migration_fn=migration_add_notes)
    assert success_retry is False

    # Verify column was actually added
    with temp_db.connect() as conn:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        assert "notes" in cols


def test_config_manager_atomic_and_recovery():
    """Verify ConfigManager atomic writing and corrupted file recovery."""
    fd, path = tempfile.mkstemp(suffix=".json", prefix="test_config_")
    os.close(fd)
    if os.path.exists(path):
        os.remove(path)

    defaults = {"speed": 10, "enabled": True, "name": "standard"}
    cfg = ConfigManager(path, defaults)

    # Defaults loaded
    assert cfg.get("speed") == 10
    assert cfg.get("enabled") is True

    # Mutate and save atomically
    cfg.set("speed", 25)
    cfg.save()
    assert os.path.exists(path)

    # Reload fresh
    cfg_fresh = ConfigManager(path, defaults)
    assert cfg_fresh.get("speed") == 25
    assert cfg_fresh.get("name") == "standard"

    # Test corruption recovery
    with open(path, "w", encoding="utf-8") as f:
        f.write("{ invalid json formatting !!! ...")

    cfg_recovered = ConfigManager(path, defaults)
    # Should fall back cleanly to defaults without crashing
    assert cfg_recovered.get("speed") == 10
    # Corrupted backup file should exist
    backup = f"{path}.corrupted"
    assert os.path.exists(backup)

    # Cleanup
    for p in (path, backup):
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
