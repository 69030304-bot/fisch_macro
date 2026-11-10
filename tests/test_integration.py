"""
tests/test_integration.py - Full Cross-Module End-to-End Integration Test Suite.

Validates:
1. Complete user lifecycle: Backend Registration -> Login -> Token Auth -> Profile Fetch.
2. Full headless Macro integration: MacroDashboard + Bot + FishingWorkflow + MockScreenGrabber + MockInputDriver.
3. State machine transitions, event publishing, and catch/cycle tracking.
4. Configuration persistence roundtrip with ConfigManager.
5. Failsafe watchdog activation and input release guarantee.
6. Package exports and standalone entrypoints (main, fisch_macro, view_database).
"""
import os
import sys
import tempfile
import time
import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import automation
import core
import data
import fisch_macro
import gui
import vision
from automation.workflow import FishingWorkflow
from core.input import InputManager, MockInputDriver
from core.state import MacroState
from data.config import ConfigManager
from data.database import DatabaseManager
from gui.dashboard import MacroDashboard
from vision.capture import MockScreenGrabber


@pytest.fixture
def temp_db():
    """Provides a fresh isolated SQLite database for integration testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db_mgr = DatabaseManager(db_path=db_path)
    db_mgr.init_db()
    yield db_mgr, db_path
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass


def test_package_exports_and_interop():
    """Verify that all modular layers cleanly expose their contracts."""
    # core
    assert hasattr(core, "MacroEngine")
    assert hasattr(core, "StateManager")
    assert hasattr(core, "EventBus")
    assert hasattr(core, "CancellationToken")
    assert hasattr(core, "InputManager")

    # automation
    assert hasattr(automation, "FishingWorkflow")
    assert hasattr(automation, "ReelController")
    assert hasattr(automation, "SigmaDeltaModulator")
    assert hasattr(automation, "EquipRodOperation")
    assert hasattr(automation, "CastOperation")
    assert hasattr(automation, "BiteWaitOperation")
    assert hasattr(automation, "ReelOperation")

    # vision
    assert hasattr(vision, "ScreenGrabber")
    assert hasattr(vision, "MockScreenGrabber")
    assert hasattr(vision, "Track")
    assert hasattr(vision, "analyze")
    assert hasattr(vision, "detect")

    # data
    assert hasattr(data, "DatabaseManager")
    assert hasattr(data, "UserRepository")
    assert hasattr(data, "SessionRepository")
    assert hasattr(data, "ConfigManager")

    # gui
    assert hasattr(gui, "MacroDashboard")
    assert hasattr(gui, "LoginWindow")
    assert hasattr(gui, "AccountDialog")
    assert hasattr(gui, "ApiClient")


def test_end_to_end_auth_and_user_service(temp_db):
    """End-to-end integration: User Registration, Login, Token generation, and Profile lookup."""
    db_mgr, _ = temp_db
    import service

    # Patch service database path to test database
    with patch.object(service, "db", db_mgr.connect):
        # 1. Register first user -> must be admin
        user1 = service.register(
            username="integ_admin",
            password="AdminPassword123!",
            nickname="AdminUser",
            birthday="2000-01-01",
        )
        assert user1["username"] == "integ_admin"
        assert user1["role"] == "admin"

        # 2. Register second user -> must be user
        user2 = service.register(
            username="integ_fisher",
            password="FisherPassword123!",
            nickname="FisherPro",
            birthday="2001-05-15",
        )
        assert user2["username"] == "integ_fisher"
        assert user2["role"] == "user"

        # 3. Login user
        login_res = service.login(username="integ_fisher", password="FisherPassword123!")
        token = login_res["token"]
        assert token is not None
        assert login_res["role"] == "user"

        # 4. Authenticate session token and retrieve current user
        me = service.current_user(token)
        assert me["username"] == "integ_fisher"
        assert me["nickname"] == "FisherPro"

        # 5. Export users rows for Google Sheets sync
        headers, rows = service.export_users_rows()
        assert headers == service.SHEET_HEADERS
        assert len(rows) == 2
        usernames = [r[1] for r in rows]
        assert "integ_admin" in usernames
        assert "integ_fisher" in usernames


def test_bot_and_workflow_integration_with_mock_hardware():
    """
    Validates end-to-end execution of fisch_macro.Bot with FishingWorkflow,
    MockScreenGrabber, and MockInputDriver.
    """
    mock_driver = MockInputDriver()
    input_mgr = InputManager(driver=mock_driver)
    mock_grabber = MockScreenGrabber()

    cfg = dict(fisch_macro.DEFAULTS)
    cfg["start_delay"] = 0.01
    cfg["cast_hold"] = 0.01
    cfg["loop_delay"] = 0.01
    cfg["equip_on_start"] = True
    cfg["use_shake"] = True

    logs = []
    catches = []
    finished = []

    def log_cb(msg):
        logs.append(msg)

    def catch_cb():
        catches.append(1)

    def finish_cb():
        finished.append(True)

    bot = fisch_macro.Bot(
        cfg=cfg,
        log=log_cb,
        on_catch=catch_cb,
        on_finish=finish_cb,
        grabber=mock_grabber,
        input_mgr=input_mgr,
    )

    # Start bot in background thread
    bot.start()
    assert bot.is_alive()

    # Allow bot to start and begin cycle
    time.sleep(0.1)

    # Verify input driver received equip and cast actions
    assert len(mock_driver.event_log) > 0

    # Stop bot
    bot.stop()
    bot.join(timeout=2.0)

    assert not bot.is_alive()
    assert bot.stopped()
    assert len(finished) == 1
    assert mock_driver.mouse_down is False


def test_headless_dashboard_and_bot_lifecycle():
    """
    Validates full MacroDashboard initialization and bot lifecycle
    within a headless Tkinter window.
    """
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display not available")

    root.withdraw()
    mock_driver = MockInputDriver()
    input_mgr = InputManager(driver=mock_driver)
    mock_grabber = MockScreenGrabber()

    api_mock = MagicMock()
    user_info = {"id": 1, "username": "e2e_tester", "nickname": "Tester", "role": "admin"}

    # Factory that binds Bot to mock hardware
    def integrated_bot_factory(cfg, log, on_catch, on_finish):
        cfg["start_delay"] = 0.01
        cfg["cast_hold"] = 0.01
        cfg["loop_delay"] = 0.01
        return fisch_macro.Bot(
            cfg=cfg,
            log=log,
            on_catch=on_catch,
            on_finish=on_finish,
            grabber=mock_grabber,
            input_mgr=input_mgr,
        )

    dashboard = MacroDashboard(
        root,
        api=api_mock,
        info=user_info,
        bot_factory=integrated_bot_factory,
    )

    # 1. Start Macro via dashboard
    dashboard.start()
    assert dashboard.bot is not None
    assert dashboard.bot.is_alive()

    # 2. Allow bot to run for a short duration
    time.sleep(0.1)

    # 3. Simulate catch
    dashboard.add_catch()
    assert dashboard.catches == 1

    # 4. Stop Macro via dashboard
    dashboard.stop()
    if dashboard.bot:
        dashboard.bot.join(timeout=2.0)

    assert not dashboard.bot.is_alive()

    # 5. Close dashboard (which cleanly destroys the window)
    dashboard.close()


def test_atomic_config_persistence_roundtrip():
    """Validates configuration file read/write roundtrip and recovery."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        cfg_path = f.name

    defaults = {"rod_slot": "1", "cast_hold": 1.0, "tolerance": 25}
    mgr = ConfigManager(file_path=cfg_path, defaults=defaults)

    # Load defaults
    loaded = mgr.load()
    assert loaded["rod_slot"] == "1"
    assert loaded["cast_hold"] == 1.0

    # Mutate and save
    loaded["rod_slot"] = "5"
    loaded["tolerance"] = 40
    assert mgr.save(loaded) is True

    # Re-read
    mgr2 = ConfigManager(file_path=cfg_path, defaults=defaults)
    reloaded = mgr2.load()
    assert reloaded["rod_slot"] == "5"
    assert reloaded["tolerance"] == 40

    if os.path.exists(cfg_path):
        os.remove(cfg_path)


def test_failsafe_watchdog_trigger():
    """Validates that emergency stop triggers cleanly when mouse moves to (0, 0)."""
    mock_driver = MockInputDriver()
    mock_driver.set_cursor_pos(0, 0)  # At corner
    input_mgr = InputManager(driver=mock_driver)

    cfg = dict(fisch_macro.DEFAULTS)
    cfg["start_delay"] = 5  # Would wait 5s if not stopped
    logs = []

    bot = fisch_macro.Bot(
        cfg=cfg,
        log=logs.append,
        on_catch=lambda: None,
        on_finish=lambda: None,
        grabber=MockScreenGrabber(),
        input_mgr=input_mgr,
    )

    bot.check_failsafe()
    assert bot.stopped()
    assert any("FAILSAFE" in msg for msg in logs)


def test_standalone_modules_importability():
    """Verify that standalone script entrypoints can be imported without errors."""
    import main
    assert hasattr(main, "app")

    import view_database
    assert hasattr(view_database, "DB_PATH")

    import ui_kit
    assert hasattr(ui_kit, "GButton")
    assert hasattr(ui_kit, "Card")
