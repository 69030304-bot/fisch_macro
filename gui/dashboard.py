"""
gui/dashboard.py - Main desktop dashboard and automation control interface.

Owned by Member 69030208 (นายฤทธิพร วงค์ป้อม — GUI & DB Integration)
in collaboration with Member 69030377 (นางสาวพิชชาภา ภูววิไลเมธา — UX/UI Design).
Provides real-time telemetry display, calibration loupe tool, two-way settings binding,
and non-blocking background queue polling.
"""
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageGrab, ImageTk

try:
    from pynput import keyboard
except ImportError:
    keyboard = None

try:
    import winsound
except ImportError:
    winsound = None

import ui_kit as ui
from data.config import ConfigManager
from gui.admin_dialog import AccountDialog
from gui.client import ApiClient, ClientError, HEARTBEAT_SECS, OFFLINE_GRACE
from gui.widgets import FONT, FONT_NAME, Tip
from vision import Grabber, analyze, centers, detect

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, "fisch_config.json")

# Default macro configuration
DEFAULTS = {
    "rod_slot": "1",
    "region": [600, 800, 720, 60],
    "fish_color": [90, 90, 90],
    "bar_color": [255, 255, 255],
    "bar_color2": None,
    "tolerance": 25,
    "cast_hold": 1.0,
    "bite_timeout": 25,
    "reel_timeout": 40,
    "loop_delay": 2.0,
    "start_delay": 5,
    "kp": 1.0,
    "kd": 0.10,
    "latency": 0.05,
    "use_shake": True,
    "nav_each_cycle": True,
    "equip_on_start": True,
    "invert": False,
    "trace": False,
}

_cfg_mgr = ConfigManager(CONFIG_FILE, DEFAULTS)


def load_config() -> Dict[str, Any]:
    return _cfg_mgr.load()


def save_config(cfg: Dict[str, Any]) -> None:
    _cfg_mgr.save(cfg)


def rgb_hex(c) -> str:
    if not c:
        return "#000000"
    return "#%02x%02x%02x" % tuple(int(v) for v in c)


FONT_B = (FONT_NAME, 9, "bold")
IDLE_COLOR = "#566486"
ACTIVE_COLOR = "#0fae86"
AMBER = "#fbbf24"
GREEN = "#22c55e"
RED = "#ef4444"
ACCENT = "#2de0c0"
DARK = "#0b1220"
BG = "#0e1427"
FG = "#e8eefc"
MUTED = "#8593b4"
PANEL = "#161f3a"
PANEL2 = "#1d2848"
LINE = "#34457a"

PHASES = {
    "idle": ("หยุด", IDLE_COLOR),
    "start": ("เตรียมเริ่ม", AMBER),
    "cast": ("เหวี่ยงเบ็ด", ui.MAIN.info),
    "wait": ("รอปลากิน", AMBER),
    "reel": ("กำลังดึงปลา", GREEN),
    "rest": ("พักรอบ", ACCENT),
}

SLIDER_RANGE = {
    "rod_slot": (1, 9, 1),
    "cast_hold": (0.2, 3.0, 0.05),
    "bite_timeout": (5, 90, 1),
    "reel_timeout": (10, 120, 1),
    "loop_delay": (0.5, 8.0, 0.1),
    "start_delay": (0, 15, 1),
    "tolerance": (5, 80, 1),
    "kp": (0.1, 3.0, 0.05),
    "kd": (0.0, 0.5, 0.01),
    "latency": (0.0, 0.3, 0.01),
}

FIELD_INFO = {
    "rod_slot": ("ช่องเบ็ด (1-9)", str, "เลขช่อง hotbar ที่ใส่เบ็ดไว้ในเกม"),
    "cast_hold": ("กดค้างเหวี่ยง (วิ)", float, "เวลากดเมาส์ค้างตอนเหวี่ยง ยิ่งนานยิ่งเหวี่ยงไกล"),
    "bite_timeout": ("รอปลากิน (วิ)", int, "รอปลากินนานสุดกี่วินาที เกินแล้วเหวี่ยงใหม่"),
    "reel_timeout": ("ดึงปลา สูงสุด (วิ)", int, "เวลาดึงปลาสูงสุดต่อ 1 ตัว กันบอทค้างในมินิเกม"),
    "loop_delay": ("พักระหว่างรอบ (วิ)", float, "พักก่อนเหวี่ยงรอบใหม่ ให้ป๊อปอัปปลาที่ได้หายก่อน"),
    "start_delay": ("นับถอยหลังเริ่ม (วิ)", int, "เวลาหลังกดเริ่ม ให้คลิกกลับไปหน้าต่างเกมให้ทัน"),
    "tolerance": ("ความคลาดเคลื่อนสี", int, "ยอมให้สีต่างจากที่เก็บไว้ได้เท่าไร\nน้อย = เข้มงวด / มาก = หลวมแต่จับสีผิดได้"),
    "kp": ("ความไว (kp)", float, "ความไวในการตามปลา\nตามไม่ทันให้เพิ่ม / แถบแกว่งไปมาให้ลด"),
    "kd": ("กันแกว่ง (kd)", float, "ถ้าแถบพุ่งเลยปลาบ่อยให้เพิ่มทีละ 0.03"),
    "latency": ("ชดเชยดีเลย์ (วิ)", float, "แถบตามหลังปลาตลอดให้เพิ่ม / พุ่งเลยปลาตลอดให้ลด"),
}

GROUP_TIMING = ["rod_slot", "cast_hold", "bite_timeout", "reel_timeout", "loop_delay", "start_delay"]
GROUP_TRACK = ["tolerance", "kp", "kd", "latency"]
CHECK_INFO = [
    ("กด Shake (Enter รัว)", "use_shake", "กด Enter รัวเพื่อกดปุ่ม Shake อัตโนมัติ"),
    ("สลับ UI Nav ทุกรอบ (\\)", "nav_each_cycle", "กด \\ เปิด UI Navigation ตอนรอ Shake และปิดตอนเริ่มดึง ครบคู่ทุกรอบ"),
    ("กดช่องเบ็ดตอนเริ่ม", "equip_on_start", "กดช่องเบ็ดครั้งเดียวตอนเริ่ม\nถ้าถือเบ็ดอยู่แล้วให้ปิด ไม่งั้นจะเก็บเบ็ด"),
    ("กลับทิศการกด", "invert", "ถ้าแถบวิ่งหนีปลาตลอดไม่ว่าปรับอะไร ให้ติ๊กอันนี้"),
    ("บันทึก trace (ดีบัก)", "trace", "บันทึกข้อมูลทุกเฟรมเป็น fisch_trace.csv ไว้ส่งให้วิเคราะห์"),
]


class MacroDashboard:
    """Main application dashboard for Fisch Macro automation."""

    PREVIEW_W = 480
    MAX_SNAPS = 8

    def __init__(
        self,
        root: tk.Tk,
        api: Optional[ApiClient] = None,
        info: Optional[Dict[str, Any]] = None,
        bot_factory: Optional[Callable] = None,
    ):
        self.root = root
        self.api = api
        self.info = info or {}
        self.bot_factory = bot_factory
        self.user = self.info.get("username", "")
        self.role = self.info.get("role", "user")
        self.uid = self.info.get("id", "-")
        self.nickname = self.info.get("nickname", "")
        self.logout_requested = False
        self.kicked: Optional[str] = None
        self.hb_stop = threading.Event()
        self.cfg = load_config()
        self.bot = None
        self.catches = 0
        self.started_at: Optional[float] = None
        self.q = queue.Queue()
        self.photo = None
        self.pgrab = Grabber()
        self.snaps: List[Image.Image] = []
        self.calib_open = False
        self.vars: Dict[str, tk.StringVar] = {}
        self.types: Dict[str, type] = {}
        self.bool_vars: Dict[str, tk.BooleanVar] = {}

        root.title("Fisch Macro")
        root.configure(bg=BG)
        root.attributes("-topmost", True)
        root.resizable(False, False)
        ui.begin(root)
        ui.setup_ttk(ui.MAIN)
        self.th = th = ui.MAIN
        sc = ui.sc

        main = tk.Frame(root, bg=BG, padx=sc(14), pady=sc(12))
        main.grid()
        main.columnconfigure(0, weight=1)

        # Header card
        head = ui.Card(main, pad=(16, 10), radius=16)
        head.grid(row=0, column=0, sticky="ew")
        hb = head.body
        self._logo = ui.photo(ui.fish_logo(sc(36), th))
        tk.Label(hb, image=self._logo, bg=th.card).pack(side="left", padx=(0, 10))
        tbox = tk.Frame(hb, bg=th.card)
        tbox.pack(side="left")
        row_t = tk.Frame(tbox, bg=th.card)
        row_t.pack(anchor="w")
        self.head_title = tk.Label(row_t, text="Fisch Macro", bg=th.card, fg=th.fg, font=(FONT_NAME, 15, "bold"))
        self.head_title.pack(side="left")
        tk.Label(row_t, text=" v10", bg=th.card, fg=th.accent, font=(FONT_NAME, 8, "bold")).pack(
            side="left", pady=(6, 0)
        )
        tk.Label(tbox, text="Auto-fishing assistant", bg=th.card, fg=th.muted, font=(FONT_NAME, 8)).pack(anchor="w")

        self.chip = ui.Chip(hb, "●  หยุด", IDLE_COLOR, "white", th)
        self.chip.pack(side="right")
        stats = tk.Frame(hb, bg=th.card)
        stats.pack(side="right", padx=14)
        self.st_fish = ui.StatCard(stats, "ปลา", "0", th)
        self.st_time = ui.StatCard(stats, "เวลา", "00:00:00", th)
        self.st_cycle = ui.StatCard(stats, "รอบ", "0", th)
        for w in (self.st_fish, self.st_time, self.st_cycle):
            w.pack(side="left", padx=4)

        # Controls row
        ctl = tk.Frame(main, bg=BG)
        ctl.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        self.btn = ui.GButton(
            ctl, "▶  เริ่ม (F6)", self.toggle, kind="go", theme=th, height=40, width=150, radius=12, font=(FONT_NAME, 10, "bold")
        )
        self.btn.pack(side="left")
        ui.GButton(ctl, "บันทึก", self.save, theme=th, height=40, width=86, radius=12).pack(side="left", padx=8)
        self.preview_var = tk.BooleanVar(value=True)
        ui.toggle_row(ctl, "Preview", self.preview_var, th).pack(side="left", padx=12)
        ui.GButton(ctl, "ออกจากระบบ", self.logout, theme=th, height=34, radius=12).pack(side="right")
        ui.GButton(ctl, "บัญชี", self.open_account, theme=th, height=34, width=72, radius=12).pack(
            side="right", padx=8
        )
        tk.Label(ctl, text=f"{self.nickname or self.user}  (ID {self.uid})", bg=BG, fg=MUTED, font=FONT).pack(
            side="right", padx=(0, 4)
        )

        # Preview card
        pv = ui.Card(main, title="Preview")
        pv.grid(row=2, column=0, sticky="ew")
        self.preview_img = tk.Label(
            pv.body, bg=DARK, fg=MUTED, font=FONT, text="(เปิด Preview เพื่อดูภาพ)", width=64, height=3
        )
        self.preview_img.pack(fill="x")
        self.preview_txt = tk.Label(pv.body, text="", bg=th.card, fg=MUTED, font=FONT, anchor="w")
        self.preview_txt.pack(fill="x", pady=(6, 0))

        # Tab views
        nb = ui.PillTabs(main, th, stack=True)
        nb.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.build_calib_tab(nb)
        self.build_settings_tab(nb)
        self.build_log_tab(nb)

        # Bottom status bar
        sb = ui.Card(main, pad=(14, 6), radius=12)
        sb.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        self.status_lbl = tk.Label(sb.body, text="พร้อมใช้งาน", bg=th.card, fg=MUTED, font=FONT)
        self.status_lbl.pack(side="left")
        tk.Label(sb.body, text="F7 หยุดฉุกเฉิน · F8 ถ่ายภาพ", bg=th.card, fg=th.dim, font=FONT).pack(side="right")

        # Global Hotkeys (guarded in CI / headless environments to prevent X11 hook crashes)
        self.hk = None
        if keyboard is not None and not os.environ.get("CI") and not os.environ.get("HEADLESS"):
            try:
                self.hk = keyboard.GlobalHotKeys({
                    "<f6>": lambda: self.root.after(0, self.toggle),
                    "<f7>": lambda: self.root.after(0, self.stop),
                    "<f8>": self.snapshot,
                })
                self.hk.start()
            except Exception:
                pass

        if self.api is not None:
            threading.Thread(target=self.heartbeat, daemon=True).start()

        root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh_cal()
        self.update_snap_lbl()
        self.poll()
        self.update_preview()
        self.log("F8 ถ่ายภาพมินิเกม → เปิดหน้าสอบเทียบ → กดเริ่ม (F6)")

    # ---------- Calibration Tab ----------
    def make_chip(self, parent: tk.Widget, title: str):
        th = self.th
        c = ui.Card(parent, pad=(10, 5), radius=11, fill=th.field, line=th.field_line)
        c.pack(side="left", padx=(0, 8))
        sw = tk.Label(c.body, width=2, bg="#000", highlightthickness=1, highlightbackground=th.field_line)
        sw.pack(side="left")
        tk.Label(c.body, text=title, bg=th.field, fg=FG, font=FONT).pack(side="left", padx=(6, 4))
        hx = tk.Label(c.body, text="", bg=th.field, fg=MUTED, font=("Consolas", 8))
        hx.pack(side="left")
        return sw, hx

    def build_calib_tab(self, nb: ui.PillTabs):
        th = self.th
        page = nb.add_page("  สอบเทียบ  ")
        card = ui.Card(page, pad=(16, 14))
        card.pack(fill="both", expand=True)
        cal = card.body
        cal.columnconfigure(1, weight=1)
        self._badge = ui.photo(ui.badge_img(ui.sc(26), th))

        def step(r: int, num: str, text: str):
            tk.Label(
                cal, text=num, image=self._badge, compound="center", fg="white", bg=th.card, font=(FONT_NAME, 9, "bold")
            ).grid(row=r, column=0, sticky="nw", padx=(0, 10), pady=6)
            tk.Label(cal, text=text, justify="left", bg=th.card, fg=FG, font=FONT).grid(
                row=r, column=1, sticky="w", pady=4
            )

        step(0, "1", "ตอนมินิเกมโผล่ กด F8 ถ่ายภาพ 2-3 ครั้ง\n(ตอนแถบเป็นสีขาว และตอนเป็นสีน้ำตาล)")
        self.snap_lbl = tk.Label(cal, bg=th.card, fg=ACCENT, font=FONT_B)
        self.snap_lbl.grid(row=0, column=2, padx=10)
        ui.GButton(cal, "ล้างภาพ", self.clear_snaps, theme=th, height=32, width=96).grid(row=0, column=3)

        step(1, "2", "เปิดหน้าต่างสอบเทียบ ลากกรอบคลุมมินิเกมและคลิกดูดสี")
        ui.GButton(cal, "เปิดหน้าต่างสอบเทียบ (เต็มจอ)", self.open_calib, kind="primary", theme=th, height=36).grid(
            row=1, column=2, columnspan=2, sticky="ew", pady=4
        )

        step(2, "3", "ตรวจสอบค่าที่บันทึกไว้")
        vf = tk.Frame(cal, bg=th.card)
        vf.grid(row=2, column=2, columnspan=2, sticky="ew", pady=(4, 0))
        self.fish_sw, self.fish_hx = self.make_chip(vf, "ปลา")
        self.bar_sw, self.bar_hx = self.make_chip(vf, "แถบขาว")
        self.bar2_sw, self.bar2_hx = self.make_chip(vf, "แถบน้ำตาล")
        ui.GButton(vf, "✕", self.clear_bar2, theme=th, height=26, width=28, radius=8).pack(side="left")

        self.region_lbl = tk.Label(cal, text="", bg=th.card, fg=MUTED, font=FONT)
        self.region_lbl.grid(row=3, column=1, columnspan=3, sticky="w", pady=(8, 0))
        ui.GButton(cal, "ทดสอบจับตำแหน่ง", self.test_detect, theme=th, height=30, width=130).grid(
            row=4, column=1, sticky="w", pady=(8, 0)
        )

    # ---------- Settings Tab ----------
    def add_field(self, parent: tk.Widget, row: int, key: str):
        label, typ, tip = FIELD_INFO[key]
        self.types[key] = typ
        v = tk.StringVar(value=str(self.cfg[key]))
        self.vars[key] = v
        th = self.th

        lb = tk.Label(parent, text=label, bg=th.card, fg=FG, font=FONT, anchor="w")
        lb.grid(row=row, column=0, sticky="w", pady=4)
        mn, mx, st = SLIDER_RANGE[key]
        sl = ui.GSlider(parent, v, mn, mx, step=st, theme=th, width=130, height=22)
        sl.grid(row=row, column=1, padx=8)
        en = ui.RoundEntry(
            parent, th, textvariable=v, justify="center", width=66, height=28, radius=9, font=(FONT_NAME, 9), pad=6
        )
        en.grid(row=row, column=2)
        for w in (lb, sl, en):
            Tip(w, tip)

    def build_settings_tab(self, nb: ui.PillTabs):
        th = self.th
        st = nb.add_page("  ตั้งค่า  ")
        st.columnconfigure(0, weight=1, uniform="g")
        st.columnconfigure(1, weight=1, uniform="g")

        g1 = ui.Card(st, title="เหวี่ยงและเวลา")
        g1.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        for i, k in enumerate(GROUP_TIMING):
            self.add_field(g1.body, i, k)

        g2 = ui.Card(st, title="การตามปลา")
        g2.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        for i, k in enumerate(GROUP_TRACK):
            self.add_field(g2.body, i, k)
        ui.GButton(g2.body, "รีเซ็ตเป็นค่าเริ่มต้น", self.reset_defaults, theme=th, height=32).grid(
            row=len(GROUP_TRACK), column=0, columnspan=3, sticky="ew", pady=(16, 0)
        )
        tk.Label(g2.body, text="เอาเมาส์ชี้ช่องต่างๆ เพื่ออ่านคำอธิบาย", bg=th.card, fg=MUTED, font=FONT).grid(
            row=len(GROUP_TRACK) + 1, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )

        g3 = ui.Card(st, title="ตัวเลือก")
        g3.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        for i, (label, key, tip) in enumerate(CHECK_INFO):
            b = tk.BooleanVar(value=bool(self.cfg[key]))
            self.bool_vars[key] = b
            r = ui.toggle_row(g3.body, label, b, th)
            r.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 28), pady=5)
            Tip(r.text, tip)
            Tip(r.toggle, tip)

    # ---------- Log Tab ----------
    def build_log_tab(self, nb: ui.PillTabs):
        th = self.th
        page = nb.add_page("  Log  ")
        card = ui.Card(page, pad=(10, 10))
        card.pack(fill="both", expand=True)
        self.logbox = tk.Text(
            card.body,
            height=9,
            width=64,
            state="disabled",
            font=(FONT_NAME, 9),
            bg=DARK,
            fg=FG,
            relief="flat",
            padx=10,
            pady=8,
            insertbackground=FG,
            highlightthickness=0,
        )
        self.logbox.pack(fill="both", expand=True)
        for tag, color in (("err", RED), ("ok", GREEN), ("warn", AMBER), ("info", th.info), ("dim", MUTED)):
            self.logbox.tag_config(tag, foreground=color)

    def log(self, msg: str):
        self.q.put(f"[{time.strftime('%H:%M:%S')}] {msg}")

    @staticmethod
    def log_tag(line: str) -> str:
        low = line.lower()
        if "error" in low or "ไม่ได้" in line or "ไม่สำเร็จ" in line:
            return "err"
        if "failsafe" in low or "ไม่เจอ" in line or "หมดเวลา" in line or "ไม่พบ" in line:
            return "warn"
        if "จบมินิเกม" in line or "บันทึก" in line or "เสร็จ" in line or "ถ่ายภาพแล้ว" in line:
            return "ok"
        if "รอบที่" in line:
            return "info"
        return "dim"

    def poll(self):
        if self.kicked:
            msg, self.kicked = self.kicked, None
            self.stop()
            messagebox.showwarning("ออกจากระบบ", msg)
            self.logout_requested = True
            self.close()
            return
        while not self.q.empty():
            line = self.q.get()
            self.logbox.configure(state="normal")
            self.logbox.insert("end", line + "\n", self.log_tag(line))
            self.logbox.see("end")
            self.logbox.configure(state="disabled")
            self.status_lbl.config(text=line[11:])
        running = bool(self.bot and self.bot.is_alive())
        phase = getattr(self.bot, "phase", "idle") if running else "idle"
        text, color = PHASES.get(phase, ("หยุด", IDLE_COLOR))
        self.chip.config(text=f"●  {text}", bg=color, fg="white" if color == IDLE_COLOR else "#06202a")
        self.st_fish.config(text=str(self.catches))
        if running:
            s = int(time.time() - (self.started_at or time.time()))
            self.st_time.config(text=f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}")
            self.st_cycle.config(text=str(getattr(self.bot, "cycle", 0)))
        self.root.after(200, self.poll)

    def refresh_cal(self):
        x, y, w, h = self.cfg["region"]
        self.region_lbl.config(text=f"พื้นที่จับภาพ:  x={x}  y={y}  กว้าง={w}  สูง={h}")
        for sw, hx, key in (
            (self.fish_sw, self.fish_hx, "fish_color"),
            (self.bar_sw, self.bar_hx, "bar_color"),
            (self.bar2_sw, self.bar2_hx, "bar_color2"),
        ):
            c = self.cfg.get(key)
            sw.config(bg=rgb_hex(c) if c else "#000")
            hx.config(text=rgb_hex(c) if c else "ยังไม่ได้เลือก")

    def clear_bar2(self):
        self.cfg["bar_color2"] = None
        self.refresh_cal()
        self.log("ล้างสีแถบน้ำตาลแล้ว")

    def cur_tol(self) -> int:
        try:
            return int(self.vars["tolerance"].get())
        except (ValueError, KeyError):
            return self.cfg["tolerance"]

    def read_settings(self) -> bool:
        try:
            for key, typ in self.types.items():
                self.cfg[key] = typ(self.vars[key].get())
            for key, b in self.bool_vars.items():
                self.cfg[key] = b.get()
            return True
        except ValueError:
            messagebox.showerror("ผิดพลาด", "ค่าที่กรอกไม่ถูกต้อง (ตัวเลข/ข้อความ)")
            return False

    def save(self):
        if self.read_settings():
            save_config(self.cfg)
            self.log("บันทึกตั้งค่าแล้ว")

    def reset_defaults(self):
        for key, var in self.vars.items():
            var.set(str(DEFAULTS[key]))
        for key, b in self.bool_vars.items():
            b.set(bool(DEFAULTS[key]))
        self.log("รีเซ็ตค่าเป็นค่าเริ่มต้นแล้ว (กดบันทึกเพื่อยืนยัน)")

    # ---------- Preview ----------
    def update_preview(self):
        running = bool(self.bot and self.bot.is_alive())
        if running:
            live = getattr(self.bot, "live", "กำลังทำงาน...")
            self.preview_txt.config(text=live, foreground=ACCENT)
            self.root.after(200, self.update_preview)
            return
        self.preview_txt.config(foreground=MUTED)
        if self.preview_var.get() and not self.calib_open:
            try:
                arr = self.pgrab.grab(self.cfg["region"])
                f, b, fm, bm1, bm2 = analyze(arr, self.cfg, self.cur_tol())
                out = arr.astype(np.uint8).copy()
                out[fm] = (255, 0, 0)
                out[bm1] = (0, 255, 0)
                if bm2 is not None:
                    out[bm2] = (255, 200, 0)
                pil = Image.fromarray(out)
                d = ImageDraw.Draw(pil)
                fc, bc = centers(f, b)
                if fc is not None:
                    d.line([(fc, 0), (fc, pil.height)], fill=(255, 0, 255), width=1)
                if bc is not None:
                    d.line([(bc, 0), (bc, pil.height)], fill=(0, 255, 255), width=1)
                if pil.width > self.PREVIEW_W:
                    pil = pil.resize((self.PREVIEW_W, max(1, int(pil.height * self.PREVIEW_W / pil.width))))
                self.photo = ImageTk.PhotoImage(pil)
                self.preview_img.config(image=self.photo, text="", width=pil.width, height=pil.height)
                self.preview_txt.config(
                    text=f"ปลา: {'x=%.0f' % fc if fc is not None else 'ไม่เจอ'}   "
                    f"แถบ: {'x=%.0f' % bc if bc is not None else 'ไม่เจอ'}   "
                    f"(แดง=ปลา  เขียว=แถบขาว  เหลือง=แถบน้ำตาล)"
                )
            except Exception as e:
                self.preview_txt.config(text=f"preview error: {e}")
        elif not self.preview_var.get():
            self.preview_img.config(image="", text="(เปิด Preview เพื่อดูภาพ)", width=64, height=3)
            self.preview_txt.config(text="")
        self.root.after(150, self.update_preview)

    # ---------- Snapshots & Calibration ----------
    def snapshot(self):
        if self.calib_open:
            return
        try:
            img = ImageGrab.grab().convert("RGB")
        except Exception as e:
            self.log(f"ถ่ายภาพไม่สำเร็จ: {e}")
            return
        self.snaps.append(img)
        if len(self.snaps) > self.MAX_SNAPS:
            self.snaps.pop(0)
        if winsound:
            try:
                winsound.Beep(1200, 60)
            except Exception:
                pass
        self.log(f"ถ่ายภาพแล้ว ({len(self.snaps)} ภาพ)")
        self.root.after(0, self.update_snap_lbl)

    def update_snap_lbl(self):
        self.snap_lbl.config(text=f"ภาพ {len(self.snaps)}/{self.MAX_SNAPS}")

    def clear_snaps(self):
        self.snaps.clear()
        self.update_snap_lbl()
        self.log("ล้างภาพที่ถ่ายไว้แล้ว")

    def open_calib(self):
        if self.calib_open:
            return
        if not self.snaps:
            messagebox.showinfo("ยังไม่มีภาพ", "กด F8 ตอนมินิเกมแสดงอยู่ เพื่อถ่ายภาพไว้ก่อน")
            return
        self.calib_open = True
        self.root.withdraw()
        self.root.after(250, self._calib_window)

    def _calib_window(self):
        top = tk.Toplevel(self.root)
        top.attributes("-fullscreen", True)
        top.attributes("-topmost", True)
        top.configure(bg="black")
        canvas = tk.Canvas(top, bg="black", highlightthickness=0, cursor="crosshair")
        canvas.pack(fill="both", expand=True)
        W, H = top.winfo_screenwidth(), top.winfo_screenheight()
        first = self.snaps[-1]
        sc = min(W / first.width, H / first.height)
        if sc > 0.98:
            sc = 1.0
        S = {"idx": len(self.snaps) - 1, "photo": None, "loupe": None, "drag": None}
        mode = tk.StringVar(value="region")
        overlay = tk.BooleanVar(value=True)

        img_item = canvas.create_image(0, 0, anchor="nw")
        rect_item = canvas.create_rectangle(0, 0, 0, 0, outline=ACCENT, width=2)
        drag_item = canvas.create_rectangle(0, 0, 0, 0, outline=RED, width=2)
        loupe_item = canvas.create_image(W - 10, 10, anchor="ne")
        loupe_txt = canvas.create_text(W - 10, 195, anchor="ne", fill=AMBER, font=("Tahoma", 10), text="")

        # Toolbar
        bar = tk.Frame(canvas, bg=PANEL, padx=10, pady=6, highlightthickness=1, highlightbackground=ACCENT)
        row1 = tk.Frame(bar, bg=PANEL)
        row1.pack()
        hint = tk.Label(bar, bg=PANEL, fg=AMBER, font=("Tahoma", 10))
        hint.pack(anchor="w", pady=(4, 0))

        def rb(text, val):
            tk.Radiobutton(
                row1,
                text=text,
                variable=mode,
                value=val,
                bg=PANEL,
                fg=FG,
                selectcolor=PANEL2,
                activebackground=PANEL,
                activeforeground=ACCENT,
                font=("Tahoma", 10, "bold"),
                highlightthickness=0,
            ).pack(side="left")

        def sw():
            l = tk.Label(row1, width=2, relief="solid", bd=1)
            l.pack(side="left", padx=(0, 10))
            return l

        def tbtn(text, cmd, **kw):
            b = tk.Button(
                row1,
                text=text,
                command=cmd,
                bg=PANEL2,
                fg=FG,
                activebackground=LINE,
                activeforeground=FG,
                relief="flat",
                padx=8,
                **kw,
            )
            b.pack(side="left")
            return b

        rb("① ลากพื้นที่", "region")
        rb("② สีปลา", "fish")
        sw_fish = sw()
        rb("③ สีแถบขาว", "bar")
        sw_bar = sw()
        rb("④ สีแถบน้ำตาล", "bar2")
        sw_bar2 = sw()

        tbtn("◀", lambda: step(-1))
        idx_lbl = tk.Label(row1, bg=PANEL, fg=FG, font=("Tahoma", 10))
        idx_lbl.pack(side="left", padx=6)
        tbtn("▶", lambda: step(1)).pack_configure(padx=(0, 10))
        tk.Label(row1, text="tol", bg=PANEL, fg=MUTED).pack(side="left")
        spin = tk.Spinbox(
            row1,
            from_=0,
            to=150,
            width=4,
            textvariable=self.vars["tolerance"],
            command=lambda: render(),
            bg=PANEL2,
            fg=FG,
            buttonbackground=PANEL2,
            insertbackground=FG,
            relief="flat",
        )
        spin.pack(side="left", padx=(3, 10))
        spin.bind("<KeyRelease>", lambda e: render())
        tk.Checkbutton(
            row1,
            text="ดูผลจับสี",
            variable=overlay,
            command=lambda: render(),
            bg=PANEL,
            fg=FG,
            selectcolor=PANEL2,
            activebackground=PANEL,
            activeforeground=ACCENT,
            highlightthickness=0,
        ).pack(side="left", padx=(0, 10))
        done = tk.Button(
            row1,
            text="เสร็จ (Esc)",
            command=lambda: close(),
            bg="#16a34a",
            fg="white",
            activebackground=GREEN,
            activeforeground="white",
            relief="flat",
            padx=10,
            font=("Tahoma", 9, "bold"),
        )
        done.pack(side="left")
        canvas.create_window(W // 2, 6, window=bar, anchor="n")

        hints = {
            "region": "ลากกรอบคลุมเฉพาะแถบแนวนอนที่มีปลากับแถบขาว (ให้บางที่สุด)",
            "fish": "คลิกที่ไอคอนปลา (ดูแว่นขยายมุมขวาบนช่วยเล็ง)",
            "bar": "คลิกที่แถบสีขาว (ใช้ภาพที่แถบเป็นสีขาว)",
            "bar2": "คลิกที่แถบสีน้ำตาล (กด ◀ ▶ ไปภาพที่แถบเป็นสีน้ำตาล)",
        }

        def on_mode(*_):
            hint.config(text=hints[mode.get()] + "     |     ← → เปลี่ยนภาพ   Esc ปิด")

        mode.trace_add("write", on_mode)
        on_mode()

        def sync_sw():
            sw_fish.config(bg=rgb_hex(self.cfg["fish_color"]))
            sw_bar.config(bg=rgb_hex(self.cfg["bar_color"]))
            c2 = self.cfg.get("bar_color2")
            sw_bar2.config(bg=rgb_hex(c2) if c2 else PANEL2)

        def base():
            return self.snaps[S["idx"]]

        def render():
            b = base()
            shown = b
            if overlay.get():
                x, y, w, h = self.cfg["region"]
                x0, y0 = max(0, x), max(0, y)
                x1, y1 = min(b.width, x + w), min(b.height, y + h)
                if x1 - x0 > 3 and y1 - y0 > 1:
                    crop = b.crop((x0, y0, x1, y1))
                    arr = np.asarray(crop).astype(np.int16)
                    _, _, fm, bm1, bm2 = analyze(arr, self.cfg, self.cur_tol())
                    out = np.array(crop)
                    out[fm] = (255, 0, 0)
                    out[bm1] = (0, 255, 0)
                    if bm2 is not None:
                        out[bm2] = (255, 200, 0)
                    shown = b.copy()
                    shown.paste(Image.fromarray(out), (x0, y0))
            if sc != 1.0:
                shown = shown.resize((int(shown.width * sc), int(shown.height * sc)), Image.NEAREST)
            S["photo"] = ImageTk.PhotoImage(shown)
            canvas.itemconfig(img_item, image=S["photo"])
            x, y, w, h = self.cfg["region"]
            canvas.coords(rect_item, x * sc, y * sc, (x + w) * sc, (y + h) * sc)
            idx_lbl.config(text=f"ภาพ {S['idx'] + 1}/{len(self.snaps)}")
            sync_sw()

        def step(d):
            S["idx"] = (S["idx"] + d) % len(self.snaps)
            render()

        def to_img(e):
            b = base()
            ix = min(max(int(e.x / sc), 0), b.width - 1)
            iy = min(max(int(e.y / sc), 0), b.height - 1)
            return ix, iy

        def on_move(e):
            b = base()
            ix, iy = to_img(e)
            r = 12
            loupe = b.crop((ix - r, iy - r, ix + r + 1, iy + r + 1)).resize((25 * 7, 25 * 7), Image.NEAREST)
            d = ImageDraw.Draw(loupe)
            c = r * 7
            d.rectangle([c, c, c + 6, c + 6], outline=(255, 0, 255))
            S["loupe"] = ImageTk.PhotoImage(loupe)
            canvas.itemconfig(loupe_item, image=S["loupe"])
            px = b.getpixel((ix, iy))[:3]
            canvas.itemconfig(loupe_txt, text=f"{rgb_hex(px)}  RGB{tuple(px)}  ({ix},{iy})")

        def pick(e):
            m = mode.get()
            key = {"fish": "fish_color", "bar": "bar_color", "bar2": "bar_color2"}[m]
            ix, iy = to_img(e)
            px = list(base().getpixel((ix, iy))[:3])
            self.cfg[key] = px
            self.log(f"เก็บสี {key} = {px}")
            nxt = {"fish": "bar", "bar": "bar2"}
            if m in nxt:
                mode.set(nxt[m])
            render()

        def on_press(e):
            if mode.get() == "region":
                S["drag"] = (e.x, e.y)
                canvas.coords(drag_item, e.x, e.y, e.x, e.y)
            else:
                pick(e)

        def on_drag(e):
            if S["drag"]:
                x0, y0 = S["drag"]
                canvas.coords(drag_item, x0, y0, e.x, e.y)
            on_move(e)

        def on_release(e):
            if not S["drag"]:
                return
            x0, y0 = S["drag"]
            S["drag"] = None
            canvas.coords(drag_item, 0, 0, 0, 0)
            l, t = min(x0, e.x), min(y0, e.y)
            w, h = abs(e.x - x0), abs(e.y - y0)
            if w > 5 and h > 2:
                self.cfg["region"] = [int(l / sc), int(t / sc), int(w / sc), int(h / sc)]
                self.log(f"ตั้งพื้นที่: {self.cfg['region']}")
                mode.set("fish")
                render()

        def close(_=None):
            self.calib_open = False
            try:
                save_config(self.cfg)
            except Exception:
                pass
            top.destroy()
            self.root.deiconify()
            self.refresh_cal()
            self.log("สอบเทียบเสร็จ (บันทึกอัตโนมัติแล้ว) ดูผลที่ Preview")

        canvas.bind("<Motion>", on_move)
        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        top.bind("<Escape>", close)
        top.bind("<Left>", lambda e: step(-1))
        top.bind("<Right>", lambda e: step(1))
        top.protocol("WM_DELETE_WINDOW", close)
        top.focus_force()
        render()

    def test_detect(self):
        if not self.read_settings():
            return
        fish, bar = detect(self.cfg, self.pgrab)
        self.log(f"ทดสอบ: ปลา x={fish}  แถบ x={bar}  (None = ไม่พบ)")

    # ---------- Macro Engine / Bot Lifecycle ----------
    def toggle(self):
        if self.bot and self.bot.is_alive():
            self.stop()
        else:
            self.start()

    def start(self):
        if not self.read_settings():
            return
        self.catches = 0
        self.started_at = time.time()
        self.st_cycle.config(text="0")
        self.st_time.config(text="00:00:00")
        if self.bot_factory is not None:
            self.bot = self.bot_factory(self.cfg, self.log, self.add_catch, self.on_finish)
        else:
            from fisch_macro import Bot
            self.bot = Bot(self.cfg, self.log, self.add_catch, self.on_finish)
        self.bot.start()
        self.btn.config(text="■  หยุด (F6)", kind="stop")
        self.chip.config(text="●  ทำงาน", bg=ACTIVE_COLOR, fg="#06202a")
        self.status_lbl.config(text="กำลังทำงาน (F7 หยุดฉุกเฉิน)")

    def stop(self):
        if self.bot and self.bot.is_alive():
            self.bot.stop()
            self.status_lbl.config(text="กำลังหยุด...")
            self.log("กำลังหยุด...")

    def add_catch(self):
        self.catches += 1

    def on_finish(self):
        try:
            self.root.after(0, self._finished)
        except Exception:
            pass

    def _finished(self):
        self.btn.config(text="▶  เริ่ม (F6)", kind="go")
        self.chip.config(text="●  หยุด", bg=IDLE_COLOR, fg="white")
        self.status_lbl.config(text="หยุดแล้ว (พร้อมใช้งาน)")
        self.log("หยุดการทำงานแล้ว")

    def heartbeat(self):
        fails = 0
        while not self.hb_stop.wait(HEARTBEAT_SECS):
            try:
                self.api.me()
                fails = 0
            except ClientError as e:
                if e.status in (401, 403):
                    self.kicked = e.message
                    return
                fails += 1
                self.log(f"เช็คบัญชีกับเซิร์ฟเวอร์ไม่ได้ ({fails}/{OFFLINE_GRACE})")
                if fails >= OFFLINE_GRACE:
                    self.kicked = "ขาดการเชื่อมต่อเซิร์ฟเวอร์นานเกินไป กรุณาเข้าสู่ระบบใหม่"
                    return

    def open_account(self):
        AccountDialog(self.root, self.api, self.info, self.log)

    def logout(self):
        if self.bot and self.bot.is_alive():
            if not messagebox.askyesno("ออกจากระบบ", "บอทกำลังทำงานอยู่ ต้องการหยุดและออกจากระบบหรือไม่?"):
                return
        self.logout_requested = True
        api = self.api
        if api is not None:
            def bye():
                try:
                    api.logout()
                except Exception:
                    pass
            threading.Thread(target=bye, daemon=True).start()
        self.close()

    def close(self):
        self.hb_stop.set()
        self.stop()
        if self.hk is not None:
            try:
                self.hk.stop()
            except Exception:
                pass
        self.root.destroy()


# Compatibility alias
App = MacroDashboard
