"""
tests/test_gui.py - Automated unit and integration tests for Fisch Macro GUI subsystem.

Authored for Member 69030208 (นายฤทธิพร วงค์ป้อม — GUI & DB Integration)
in collaboration with Member 69030377 (นางสาวพิชชาภา ภูววิไลเมธา — UX/UI Design).
Validates ApiClient networking, DateField validation, background dispatching,
and MacroDashboard component lifecycle.
"""
import os
import tempfile
import threading
import time
import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest
import requests

from gui.client import ApiClient, ClientError, load_client_cfg, run_bg, save_client_cfg
from gui.dashboard import MacroDashboard, load_config
from gui.widgets import DateField, Tip


@pytest.fixture
def tk_root():
    """Create a headless/withdrawn Tk root instance for safe GUI unit tests."""
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_client_cfg_load_and_save(tmp_path):
    """Verify loading and saving client configuration atomically."""
    test_file = str(tmp_path / "test_client.json")
    with patch("gui.client.CLIENT_CFG_FILE", test_file):
        cfg = load_client_cfg()
        assert cfg["server"] == "http://127.0.0.1:8000"
        assert cfg["last_user"] == ""

        # Update and save
        cfg["last_user"] = "SuperAngler"
        cfg["server"] = "http://192.168.1.100:8000"
        save_client_cfg(cfg)

        # Reload
        reloaded = load_client_cfg()
        assert reloaded["last_user"] == "SuperAngler"
        assert reloaded["server"] == "http://192.168.1.100:8000"


def test_api_client_error_handling():
    """Verify ApiClient constructs appropriate ClientError on connection failures and HTTP errors."""
    client = ApiClient("http://127.0.0.1:9999")

    # Connection error simulation
    with patch.object(client.http, "request", side_effect=requests.exceptions.ConnectionError):
        with pytest.raises(ClientError) as exc_info:
            client.health()
        assert exc_info.value.status == 0
        assert "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้" in exc_info.value.message

    # HTTP 401 error response simulation
    mock_resp_401 = MagicMock()
    mock_resp_401.status_code = 401
    mock_resp_401.json.return_value = {"detail": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"}

    with patch.object(client.http, "request", return_value=mock_resp_401):
        with pytest.raises(ClientError) as exc_info:
            client.login("user", "wrong_pw")
        assert exc_info.value.status == 401
        assert "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง" in exc_info.value.message

    # HTTP 200 success response simulation
    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {"token": "valid_token_xyz", "username": "angler1"}

    with patch.object(client.http, "request", return_value=mock_resp_200):
        res = client.login("angler1", "correct_pw")
        assert res["token"] == "valid_token_xyz"
        assert client.token == "valid_token_xyz"


def test_date_field_validation(tk_root):
    """Verify DateField compound selection and ISO 8601 formatting."""
    df = DateField(tk_root)
    df.pack()

    # Empty date should return None
    assert df.get() is None

    # Set valid date: 15-May-1995
    df.d.set("15")
    df.m.set("May (05)")
    df.y.set("1995")
    assert df.get() == "1995-05-15"

    # Set invalid date: 31-Feb-2020
    df.d.set("31")
    df.m.set("Feb (02)")
    df.y.set("2020")
    assert df.get() is None

    # Test clear
    df.clear()
    assert df.get() is None


def test_run_bg_async_dispatch(tk_root):
    """Verify that run_bg executes function in thread and dispatches result to main Tk loop."""
    result_box = []

    def background_task():
        time.sleep(0.05)
        return "async_success"

    def on_ok(res):
        result_box.append(res)

    def on_err(err):
        result_box.append(err)

    run_bg(tk_root, background_task, on_ok, on_err)

    # Process Tk events until background thread completes
    start = time.time()
    while not result_box and time.time() - start < 3.0:
        tk_root.update()
        time.sleep(0.02)

    assert result_box == ["async_success"]


def test_macro_dashboard_log_tagging():
    """Verify log_tag categorizes severity messages accurately."""
    assert MacroDashboard.log_tag("error: connection dropped") == "err"
    assert MacroDashboard.log_tag("บันทึกไม่สำเร็จ") == "err"
    assert MacroDashboard.log_tag("FAILSAFE: cursor at origin") == "warn"
    assert MacroDashboard.log_tag("รอปลากินหมดเวลา") == "warn"
    assert MacroDashboard.log_tag("จบมินิเกม") == "ok"
    assert MacroDashboard.log_tag("บันทึกตั้งค่าแล้ว") == "ok"
    assert MacroDashboard.log_tag("--- รอบที่ 5 ---") == "info"
    assert MacroDashboard.log_tag("ธรรมดา") == "dim"


def test_macro_dashboard_init_and_lifecycle(tk_root):
    """Verify MacroDashboard widget initialization and mocked bot lifecycle."""
    api_mock = MagicMock(spec=ApiClient)
    user_info = {"id": 1, "username": "AdminPro", "role": "admin", "nickname": "TheBoss"}

    # Mock bot to avoid launching real hardware threads
    class MockBot:
        def __init__(self, cfg, log, on_catch, on_finish):
            self.cfg = cfg
            self.log = log
            self.on_catch = on_catch
            self.on_finish = on_finish
            self._alive = False
            self.phase = "idle"
            self.cycle = 0

        def is_alive(self):
            return self._alive

        def start(self):
            self._alive = True
            self.phase = "reel"
            self.cycle = 1
            self.on_catch()

        def stop(self):
            self._alive = False
            self.phase = "idle"
            self.on_finish()

    app = MacroDashboard(tk_root, api=api_mock, info=user_info, bot_factory=MockBot)
    assert app.user == "AdminPro"
    assert app.role == "admin"
    assert app.cur_tol() >= 5

    # Test log message queueing
    app.log("Test log entry")
    assert not app.q.empty()

    # Test start and stop
    app.start()
    assert app.catches == 1
    assert app.bot.is_alive() is True

    app.stop()
    assert app.bot.is_alive() is False
