"""
settings.py - โหลดค่าตั้งค่าการเชื่อมต่อ Google Sheet จาก settings.json หรือ Environment Variables

Refactored in Phase 5 to use ConfigManager for atomic and safe reading/writing.
"""
import os

from data.config import ConfigManager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

_settings_mgr = ConfigManager(
    SETTINGS_FILE,
    {
        "sheet_webhook_url": "",
        "sheet_secret": "",
    },
)

SHEET_WEBHOOK_URL = os.environ.get("SHEET_WEBHOOK_URL") or _settings_mgr.get("sheet_webhook_url", "")
SHEET_SECRET = os.environ.get("SHEET_SECRET") or _settings_mgr.get("sheet_secret", "")


def reload_settings():
    """Reload settings from disk and environment."""
    global SHEET_WEBHOOK_URL, SHEET_SECRET
    _settings_mgr.load()
    SHEET_WEBHOOK_URL = os.environ.get("SHEET_WEBHOOK_URL") or _settings_mgr.get("sheet_webhook_url", "")
    SHEET_SECRET = os.environ.get("SHEET_SECRET") or _settings_mgr.get("sheet_secret", "")


def save_settings(sheet_webhook_url: str = "", sheet_secret: str = "") -> None:
    """Persist new settings atomically."""
    global SHEET_WEBHOOK_URL, SHEET_SECRET
    _settings_mgr.save({
        "sheet_webhook_url": sheet_webhook_url,
        "sheet_secret": sheet_secret,
    })
    SHEET_WEBHOOK_URL = os.environ.get("SHEET_WEBHOOK_URL") or sheet_webhook_url
    SHEET_SECRET = os.environ.get("SHEET_SECRET") or sheet_secret
