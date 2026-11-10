"""
gui - Presentation layer for Fisch Macro.

Owned by Member 69030208 (นายฤทธิพร วงค์ป้อม — GUI & DB Integration)
in collaboration with Member 69030377 (นางสาวพิชชาภา ภูววิไลเมธา — UX/UI Design).
Provides modular, decoupled Tkinter windows, widgets, and API client adapters.
"""
from gui.admin_dialog import AccountDialog
from gui.auth_window import LoginWindow
from gui.client import (
    ApiClient,
    ClientError,
    CLIENT_CFG_FILE,
    DEFAULT_SERVER,
    load_client_cfg,
    run_bg,
    save_client_cfg,
)
from gui.dashboard import App, MacroDashboard, load_config, save_config
from gui.widgets import DateField, FONT, FONT_NAME, Tip

__all__ = [
    "MacroDashboard",
    "App",
    "LoginWindow",
    "AccountDialog",
    "ApiClient",
    "ClientError",
    "DateField",
    "Tip",
    "run_bg",
    "load_config",
    "save_config",
    "load_client_cfg",
    "save_client_cfg",
    "FONT",
    "FONT_NAME",
    "CLIENT_CFG_FILE",
    "DEFAULT_SERVER",
]
