"""
gui/client.py - HTTP API client and background thread runner for Fisch Macro.

Owned by Member 69030208 (นายฤทธิพร วงค์ป้อม — GUI & DB Integration).
Provides non-blocking backend communication and session lifecycle management.
"""
import json
import os
import threading
import tkinter as tk
from typing import Any, Callable, Dict, Optional, Tuple

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_CFG_FILE = os.path.join(BASE_DIR, "fisch_client.json")
DEFAULT_SERVER = "http://127.0.0.1:8000"
HEARTBEAT_SECS = 60      # Periodically check session validity
OFFLINE_GRACE = 5        # Consecutive connection failures before kicking


def load_client_cfg() -> Dict[str, Any]:
    """Load client configuration with default server and last used username."""
    cfg = {"server": DEFAULT_SERVER, "last_user": ""}
    if os.path.exists(CLIENT_CFG_FILE):
        try:
            with open(CLIENT_CFG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_client_cfg(cfg: Dict[str, Any]) -> None:
    """Save client configuration atomically."""
    try:
        tmp_file = f"{CLIENT_CFG_FILE}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, CLIENT_CFG_FILE)
    except Exception:
        pass


class ClientError(Exception):
    """Exception raised by ApiClient with HTTP status code (status=0 means connection failure)."""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.message = message
        self.status = status


class ApiClient:
    """HTTP client communicating with the FastAPI authentication backend."""

    def __init__(self, base_url: str):
        self.base = base_url.strip().rstrip("/")
        self.token: Optional[str] = None
        self.http = requests.Session()

    def _call(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        auth: bool = True,
        timeout: float = 8.0,
    ) -> Dict[str, Any]:
        """Send HTTP request to backend and return parsed JSON response."""
        headers = {}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            r = self.http.request(
                method, self.base + path, json=body, headers=headers, timeout=timeout
            )
        except requests.exceptions.RequestException:
            raise ClientError(
                "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ ตรวจที่อยู่เซิร์ฟเวอร์ และว่าเปิด backend อยู่",
                0,
            ) from None

        try:
            data = r.json()
        except ValueError:
            data = {}

        if r.status_code >= 400:
            detail = data.get("detail") if isinstance(data, dict) else None
            if not isinstance(detail, str):
                detail = (
                    "ข้อมูลที่ส่งไปไม่ครบ/ไม่ถูกต้อง"
                    if r.status_code == 422
                    else f"เซิร์ฟเวอร์ตอบผิดปกติ ({r.status_code})"
                )
            raise ClientError(detail, r.status_code)
        return data

    # --- Public Endpoints ---
    def health(self) -> Dict[str, Any]:
        return self._call("GET", "/health", auth=False, timeout=5.0)

    def register(self, username: str, password: str, nickname: str, birthday: str) -> Dict[str, Any]:
        return self._call(
            "POST",
            "/register",
            {"username": username, "password": password, "nickname": nickname, "birthday": birthday},
            auth=False,
        )

    def login(self, username: str, password: str) -> Dict[str, Any]:
        d = self._call("POST", "/login", {"username": username, "password": password}, auth=False)
        self.token = d.get("token")
        return d

    def reset_password(self, username: str, birthday: str, nickname: str, new_password: str) -> Dict[str, Any]:
        return self._call(
            "POST",
            "/password/reset",
            {"username": username, "birthday": birthday, "nickname": nickname, "new_password": new_password},
            auth=False,
        )

    # --- Authenticated Endpoints ---
    def me(self) -> Dict[str, Any]:
        return self._call("GET", "/me")

    def logout(self) -> None:
        try:
            self._call("POST", "/logout", timeout=4.0)
        finally:
            self.token = None

    def change_password(self, old: str, new: str) -> Dict[str, Any]:
        return self._call("POST", "/change-password", {"old_password": old, "new_password": new})

    # --- Admin Endpoints ---
    def admin_users(self) -> list:
        return self._call("GET", "/admin/users")

    def admin_set_active(self, uid: int, active: bool) -> Dict[str, Any]:
        return self._call("POST", f"/admin/users/{uid}/active", {"active": active})

    def admin_reset_password(self, uid: int, new_password: str = "") -> Dict[str, Any]:
        return self._call("POST", f"/admin/users/{uid}/reset-password", {"new_password": new_password})

    def admin_delete(self, uid: int) -> Dict[str, Any]:
        return self._call("DELETE", f"/admin/users/{uid}")

    def admin_sync_sheet(self) -> Dict[str, Any]:
        return self._call("POST", "/admin/sync-sheet", timeout=45.0)


def run_bg(
    widget: tk.Widget,
    fn: Callable[[], Any],
    on_ok: Callable[[Any], None],
    on_err: Callable[[ClientError], None],
) -> None:
    """
    Execute fn() asynchronously in a background daemon thread so the Tkinter UI
    event loop never blocks. Dispatches on_ok or on_err back onto the main Tk thread.
    """
    box: Dict[str, Any] = {}

    def work():
        try:
            box["ok"] = fn()
        except ClientError as e:
            box["err"] = e
        except Exception as e:
            box["err"] = ClientError(f"เกิดข้อผิดพลาด: {e}", 0)

    t = threading.Thread(target=work, daemon=True)
    t.start()

    def check():
        try:
            if t.is_alive():
                widget.after(60, check)
            elif "err" in box:
                on_err(box["err"])
            else:
                on_ok(box.get("ok"))
        except tk.TclError:
            pass  # Window closed during execution

    widget.after(60, check)
