"""
Fisch Auto-Fishing Macro (GUI) v10  -  Windows เท่านั้น
v10: ปรับหน้าตาใหม่ทั้งหมด หน้าหลักโทนกรมท่า-เขียวน้ำทะเล/ม่วง หน้าล็อกอินโทนคราม-ส้มพีช
    วิดเจ็ตหน้าตาอยู่ในไฟล์ ui_kit.py (ต้องวางไว้โฟลเดอร์เดียวกัน) ตรรกะบอท/ล็อกอินเหมือน v9
v8: ต้องล็อกอินก่อนใช้งาน โดยบัญชีเก็บในฐานข้อมูลฝั่งเซิร์ฟเวอร์ (backend: FastAPI + SQLite)
    แอปคุยกับ backend ผ่าน HTTP เท่านั้น (ไม่ต่อฐานข้อมูลตรง)
    สมัครสมาชิก (ชื่อผู้ใช้/รหัสผ่าน/ชื่อเล่น/วันเกิด) · ลืมรหัสผ่าน · ผู้ดูแลดู ID/รีเซ็ตรหัส/ซิงค์ Google Sheet
    ต้องเปิด backend ก่อน (ดู README.md)  ติดตั้งเพิ่ม: pip install requests
- อ่านหน้าจอ + จำลองการกดปุ่ม/เมาส์ (ไม่ inject โค้ดเข้าเกม)
- ติดตั้ง: pip install pillow numpy pynput mss requests
- รัน:    python fisch_macro.py   (ถ้าเกมไม่รับปุ่ม ให้รันแบบ Run as administrator)
- Hotkey: F6 = เริ่ม/หยุด, F7 = หยุดฉุกเฉิน, F8 = ถ่ายภาพหน้าจอไว้สอบเทียบ
          ลากเมาส์ไปมุมซ้ายบนสุดของจอ = หยุดฉุกเฉิน
"""
import csv
import ctypes
import json
import math
import os
import queue
import sys
import threading
import time
import tkinter as tk
from datetime import date
from tkinter import ttk, messagebox, simpledialog

import numpy as np
import requests
from PIL import ImageGrab, Image, ImageDraw, ImageTk
from pynput import keyboard

import ui_kit as ui

try:
    import mss
except ImportError:
    mss = None

try:
    import winsound
except ImportError:
    winsound = None

# ---------------------------------------------------------------- Hardware Input (via core.input)
from automation.controller import ReelController, SigmaDeltaModulator
from core.input import (
    SCAN,
    cursor_pos,
    input_manager,
    key_event,
    mouse_button,
    tap,
)


# ---------------------------------------------------------------- ตั้งค่า
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "fisch_config.json")
TRACE_FILE = os.path.join(BASE_DIR, "fisch_trace.csv")

DEFAULTS = {
    "rod_slot": "1",
    "region": [600, 800, 720, 60],
    "fish_color": [90, 90, 90],
    "bar_color": [255, 255, 255],
    "bar_color2": None,          # สีแถบตอนหลุดจากปลา (น้ำตาล)
    "tolerance": 25,
    "cast_hold": 1.0,
    "bite_timeout": 25,
    "reel_timeout": 40,
    "loop_delay": 2.0,
    "start_delay": 5,
    "kp": 1.0,                   # ความไวในการตามปลา
    "kd": 0.10,                  # กันแกว่ง (ใช้ความเร็วสัมพัทธ์)
    "latency": 0.05,             # ชดเชยดีเลย์ของเกม (วินาที)
    "use_shake": True,
    "nav_each_cycle": True,      # กด \ เปิดตอนรอ Shake และกด \ ปิดตอนเริ่มดึง (ครบคู่ทุกรอบ)
    "equip_on_start": True,      # กดช่องเบ็ดครั้งเดียวตอนเริ่ม (ถ้าถือเบ็ดอยู่แล้วให้ปิด)
    "invert": False,
    "trace": False,              # บันทึก fisch_trace.csv ของมินิเกมล่าสุด
}


from data.config import ConfigManager

_config_manager = ConfigManager(CONFIG_FILE, DEFAULTS)


def load_config():
    return _config_manager.load()


def save_config(cfg):
    _config_manager.save(cfg)


def rgb_hex(c):
    return "#%02x%02x%02x" % tuple(int(v) for v in c)


# ---------------------------------------------------------------- จับภาพ + ตรวจจับ (via vision)
from vision import (
    BAR_GAP,
    FISH_GAP,
    Grabber,
    ScreenGrabber,
    Track,
    analyze,
    centers,
    choose,
    color_mask,
    detect,
    measure,
    row_stride,
    runs_of,
)


# ---------------------------------------------------------------- บอท
class Bot(threading.Thread):
    def __init__(self, cfg, log, on_catch, on_finish):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.log = log
        self.on_catch = on_catch
        self.on_finish = on_finish
        self.stop_event = threading.Event()
        self.holding = False
        self.grabber = None
        self.live = ""
        self.phase = "idle"      # idle / start / cast / wait / reel / rest
        self.cycle = 0

    def stop(self):
        self.stop_event.set()

    def stopped(self):
        return self.stop_event.is_set()

    def check_failsafe(self):
        if cursor_pos() == (0, 0):
            self.log("FAILSAFE: เมาส์อยู่มุมซ้ายบน หยุดทำงาน")
            self.stop()

    def wait(self, sec):
        end = time.time() + sec
        while not self.stopped() and time.time() < end:
            time.sleep(min(0.05, max(0.0, end - time.time())))
            self.check_failsafe()

    def hold(self, state):
        if state != self.holding:
            mouse_button(state)
            self.holding = state

    def cast(self):
        self.phase = "cast"
        self.live = "เหวี่ยงเบ็ด"
        self.hold(True)
        self.wait(self.cfg["cast_hold"])
        self.hold(False)
        self.log("เหวี่ยงเบ็ด")

    def wait_for_bite(self):
        cfg = self.cfg
        self.phase = "wait"
        self.live = "รอปลากิน / กด Shake"
        nav = cfg["use_shake"] and cfg["nav_each_cycle"]
        found = False
        if nav:
            self.wait(0.3)
            tap("\\")                      # เปิด UI Navigation
        try:
            start = time.time()
            while not self.stopped() and time.time() - start < cfg["bite_timeout"]:
                if cfg["use_shake"]:
                    tap("enter")
                fish, bar = detect(cfg, self.grabber)
                if fish is not None and bar is not None:
                    found = True
                    break
                self.wait(0.1)
        finally:
            if nav:
                tap("\\")                  # ปิด UI Navigation ให้ครบคู่เสมอ
                self.wait(0.15)
        return found

    def reel(self):
        cfg = self.cfg
        self.phase = "reel"
        kp, kd, lat = cfg["kp"], cfg["kd"], cfg["latency"]
        region = cfg["region"]
        stride = row_stride(region)
        ft, bt = Track(), Track()
        bar_w = None
        ctrl = ReelController(kp=cfg["kp"], kd=cfg["kd"], latency=cfg["latency"], invert=cfg["invert"])
        modulator = SigmaDeltaModulator(initial_acc=0.5)
        trace = []
        t0 = time.perf_counter()
        last_fish_seen = last_ctrl = fps_t = t0
        frames = fps_n = 0
        fps = 0.0
        u = 0.5
        while not self.stopped() and time.perf_counter() - t0 < cfg["reel_timeout"]:
            arr = self.grabber.grab(region, stride)
            now = time.perf_counter()
            frames += 1
            fps_n += 1
            f, b = measure(arr, cfg, ft.pos(now), bt.pos(now))
            if f:
                ft.update(f[2], now)
                last_fish_seen = now
            elif now - last_fish_seen > 0.7:
                break                           # ไม่เห็นปลานาน = มินิเกมจบ
            if b:
                bt.update((b[0] + b[1]) / 2, now)
                w = b[1] - b[0] + 1
                bar_w = w if bar_w is None else 0.9 * bar_w + 0.1 * w

            if now - last_ctrl >= 0.006:        # ส่งคำสั่งกดทุก ~6ms
                dt = now - last_ctrl
                last_ctrl = now
                if ft.fresh(now) and bt.fresh(now):
                    tp = now + lat
                    fp, bp = ft.pos(tp), bt.pos(tp)
                    u, e, ev = ctrl.compute(fp, ft.v, bp, bt.v, bar_w, dt)
                    hold = modulator.step(u)
                    self.hold(hold)
                    if cfg["trace"]:
                        trace.append((round(now - t0, 4), round(ft.x, 1), round(bt.x, 1),
                                      round(bar_w or 0, 1), round(u, 3), int(self.holding)))
                    if frames % 8 == 0:
                        self.live = (f"ปลา {fp:.0f}  แถบ {bp:.0f}  กว้าง {bar_w or 0:.0f}  "
                                     f"u={u:.2f}  {fps:.0f} fps")
                elif not bt.fresh(now):
                    self.hold(False)                      # ไม่เห็นแถบ ปล่อยไว้ก่อนกันค้าง

            if fps_n >= 40:
                fps = fps_n / max(now - fps_t, 1e-6)
                fps_t, fps_n = now, 0
            if frames % 25 == 0:
                self.check_failsafe()
            time.sleep(0.001)
        self.hold(False)
        dur = time.perf_counter() - t0
        if cfg["trace"] and trace:
            try:
                with open(TRACE_FILE, "w", newline="", encoding="utf-8") as fh:
                    wr = csv.writer(fh)
                    wr.writerow(["t", "fish_x", "bar_x", "bar_w", "u", "hold"])
                    wr.writerows(trace)
            except Exception as e:
                self.log(f"เขียน trace ไม่ได้: {e}")
        self.live = ""
        return dur, frames / max(dur, 1e-6)

    def run(self):
        try:
            try:
                if sys.platform == "win32":
                    ctypes.windll.winmm.timeBeginPeriod(1)    # ให้ sleep/นาฬิกาละเอียด 1ms
            except Exception:
                pass
            self.grabber = Grabber()
            self.log("ใช้ mss จับภาพ" if self.grabber.sct else "ไม่พบ mss ใช้ ImageGrab (ช้ากว่า) แนะนำ pip install mss")
            self.log(f"เริ่มใน {self.cfg['start_delay']} วิ  คลิกกลับไปหน้าต่าง Roblox ให้ทัน")
            self.phase = "start"
            self.live = "นับถอยหลัง... คลิกกลับไปหน้าเกม"
            self.wait(self.cfg["start_delay"])
            if self.cfg["equip_on_start"] and not self.stopped():
                tap(self.cfg["rod_slot"])
                self.log(f"กดช่อง {self.cfg['rod_slot']} ถือเบ็ด (ครั้งเดียว)")
                self.wait(0.8)
            while not self.stopped():
                self.cycle += 1
                self.log(f"--- รอบที่ {self.cycle} ---")
                self.cast()
                if self.stopped():
                    break
                if self.wait_for_bite():
                    self.log("เจอมินิเกม เริ่มดึง")
                    dur, fps = self.reel()
                    self.on_catch()
                    self.log(f"จบมินิเกม ({dur:.1f} วิ, เฉลี่ย {fps:.0f} fps)")
                elif not self.stopped():
                    self.log("ไม่เจอมินิเกมจนหมดเวลา (เช็คว่าถือเบ็ดอยู่/พื้นที่ถูกไหม)")
                self.phase = "rest"
                self.live = "พักก่อนเหวี่ยงรอบถัดไป"
                self.wait(self.cfg["loop_delay"])
        except Exception as e:
            self.log(f"error: {e}")
        finally:
            try:
                input_manager.release_all()
            except Exception:
                pass
            try:
                if sys.platform == "win32":
                    ctypes.windll.winmm.timeEndPeriod(1)
            except Exception:
                pass
            self.phase = "idle"
            self.live = ""
            self.on_finish()


# ---------------------------------------------------------------- ธีม (สีทั้งหมดมาจาก ui_kit.MAIN)
TH = ui.MAIN
FONT_NAME = ui.FONT_NAME
BG, PANEL, PANEL2, LINE = TH.bg, TH.card, TH.field, TH.field_line
FG, MUTED, ACCENT = TH.fg, TH.muted, TH.accent
GREEN, RED, AMBER, DARK = TH.ok, TH.err, TH.warn, "#0a0f1f"
FONT = (FONT_NAME, 9)
FONT_B = (FONT_NAME, 9, "bold")

IDLE_COLOR = "#566486"
PHASES = {
    "idle": ("หยุด", IDLE_COLOR),
    "start": ("เตรียมเริ่ม", AMBER),
    "cast": ("เหวี่ยงเบ็ด", TH.info),
    "wait": ("รอปลากิน", AMBER),
    "reel": ("กำลังดึงปลา", GREEN),
    "rest": ("พักรอบ", ACCENT),
}

# ช่วงค่าของสไลเดอร์ (ต่ำสุด, สูงสุด, ก้าว) พิมพ์เลขเองในช่องก็ได้ ไม่จำกัดตามนี้
SLIDER_RANGE = {
    "rod_slot": (1, 9, 1), "cast_hold": (0.2, 3.0, 0.05), "bite_timeout": (5, 90, 1),
    "reel_timeout": (10, 120, 1), "loop_delay": (0.5, 8.0, 0.1), "start_delay": (0, 15, 1),
    "tolerance": (5, 80, 1), "kp": (0.1, 3.0, 0.05), "kd": (0.0, 0.5, 0.01), "latency": (0.0, 0.3, 0.01),
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


class Tip:
    """tooltip เมื่อเอาเมาส์ชี้"""

    def __init__(self, widget, text):
        self.w, self.text, self.tw = widget, text, None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def show(self, _=None):
        if self.tw:
            return
        x = self.w.winfo_rootx() + 14
        y = self.w.winfo_rooty() + self.w.winfo_height() + 4
        self.tw = tw = tk.Toplevel(self.w)
        tw.wm_overrideredirect(True)
        tw.attributes("-topmost", True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, bg=TH.tip_bg, fg=TH.fg, justify="left", font=FONT,
                 padx=10, pady=6, relief="flat", bd=0, highlightthickness=1,
                 highlightbackground=TH.tip_line, wraplength=300).pack()

    def hide(self, _=None):
        if self.tw:
            self.tw.destroy()
            self.tw = None


# ---------------------------------------------------------------- ระบบล็อกอิน (คุยกับ backend ผ่าน HTTP)
CLIENT_CFG_FILE = os.path.join(BASE_DIR, "fisch_client.json")
DEFAULT_SERVER = "http://127.0.0.1:8000"
HEARTBEAT_SECS = 60      # ถามเซิร์ฟเวอร์ทุกกี่วินาทีว่าบัญชียังใช้ได้ไหม (ถูกระงับ/ลบ/หมดอายุ = ออกจากระบบ)
OFFLINE_GRACE = 5        # ต่อเซิร์ฟเวอร์ไม่ได้ติดกันกี่ครั้ง ถึงจะบังคับออกจากระบบ


def load_client_cfg():
    cfg = {"server": DEFAULT_SERVER, "last_user": ""}
    try:
        with open(CLIENT_CFG_FILE, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_client_cfg(cfg):
    try:
        with open(CLIENT_CFG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class ClientError(Exception):
    """error จากการเรียกเซิร์ฟเวอร์ status = รหัส HTTP (0 = ต่อเซิร์ฟเวอร์ไม่ได้)"""

    def __init__(self, message, status=0):
        super().__init__(message)
        self.message = message
        self.status = status


class ApiClient:
    """ตัวกลางคุยกับ backend ทุกอย่างผ่านคลาสนี้ (แอปไม่ต่อฐานข้อมูลตรงๆ)"""

    def __init__(self, base_url):
        self.base = base_url.strip().rstrip("/")
        self.token = None
        self.http = requests.Session()

    def _call(self, method, path, body=None, auth=True, timeout=8):
        headers = {}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"     # แนบ token ทุกครั้งที่ต้องล็อกอิน
        try:
            r = self.http.request(method, self.base + path, json=body, headers=headers, timeout=timeout)
        except requests.exceptions.RequestException:
            raise ClientError("เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ ตรวจที่อยู่เซิร์ฟเวอร์ และว่าเปิด backend อยู่", 0) from None
        try:
            data = r.json()
        except ValueError:
            data = {}
        if r.status_code >= 400:
            detail = data.get("detail") if isinstance(data, dict) else None
            if not isinstance(detail, str):
                detail = ("ข้อมูลที่ส่งไปไม่ครบ/ไม่ถูกต้อง" if r.status_code == 422
                          else f"เซิร์ฟเวอร์ตอบผิดปกติ ({r.status_code})")
            raise ClientError(detail, r.status_code)
        return data

    # --- สาธารณะ
    def health(self):
        return self._call("GET", "/health", auth=False, timeout=5)

    def register(self, username, password, nickname, birthday):
        return self._call("POST", "/register", {"username": username, "password": password,
                                                "nickname": nickname, "birthday": birthday}, auth=False)

    def login(self, username, password):
        d = self._call("POST", "/login", {"username": username, "password": password}, auth=False)
        self.token = d["token"]
        return d

    def reset_password(self, username, birthday, nickname, new_password):
        return self._call("POST", "/password/reset", {"username": username, "birthday": birthday,
                                                      "nickname": nickname, "new_password": new_password},
                          auth=False)

    # --- ต้องล็อกอิน
    def me(self):
        return self._call("GET", "/me")

    def logout(self):
        try:
            self._call("POST", "/logout", timeout=4)
        finally:
            self.token = None

    def change_password(self, old, new):
        return self._call("POST", "/change-password", {"old_password": old, "new_password": new})

    # --- ผู้ดูแล
    def admin_users(self):
        return self._call("GET", "/admin/users")

    def admin_set_active(self, uid, active):
        return self._call("POST", f"/admin/users/{uid}/active", {"active": active})

    def admin_reset_password(self, uid, new_password=""):
        return self._call("POST", f"/admin/users/{uid}/reset-password", {"new_password": new_password})

    def admin_delete(self, uid):
        return self._call("DELETE", f"/admin/users/{uid}")

    def admin_sync_sheet(self):
        return self._call("POST", "/admin/sync-sheet", timeout=45)


def run_bg(widget, fn, on_ok, on_err):
    """รัน fn (เรียกเซิร์ฟเวอร์) ใน thread แยก ไม่ให้หน้าต่างค้าง แล้วเรียก on_ok/on_err กลับใน thread ของ Tk"""
    box = {}

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
            pass                      # หน้าต่างถูกปิดไปแล้ว

    widget.after(60, check)


class DateField(tk.Frame):
    """เลือกวันเกิด วัน / เดือน / ปี (dropdown มุมมน)"""
    MONTHS = [
        "Jan (01)", "Feb (02)", "Mar (03)", "Apr (04)",
        "May (05)", "Jun (06)", "Jul (07)", "Aug (08)",
        "Sep (09)", "Oct (10)", "Nov (11)", "Dec (12)"
    ]

    def __init__(self, parent, theme=None):
        super().__init__(parent, bg=ui.pbg(parent))
        th = theme or ui.LOGIN
        this_year = date.today().year
        self.d = ui.RoundCombo(self, [f"{i:02d}" for i in range(1, 32)], th, width=84, placeholder="DD")
        self.m = ui.RoundCombo(self, self.MONTHS, th, width=124, placeholder="MM")
        self.y = ui.RoundCombo(self, [str(i) for i in range(this_year, 1949, -1)], th, width=104,
                               placeholder="YYYY")
        for i, w in enumerate((self.d, self.m, self.y)):
            w.pack(side="left", expand=True, fill="x", padx=(0 if i == 0 else 8, 0))

    def get(self):
        try:
            return date(int(self.y.get()), self.MONTHS.index(self.m.get()) + 1, int(self.d.get())).isoformat()
        except (ValueError, TypeError):
            return None

    def clear(self):
        for w in (self.d, self.m, self.y):
            w.set("")


class LoginWindow:
    """หน้าต่างเข้าสู่ระบบ: Sign In / Register / Forgot Password (ธีมคราม-ม่วง ปุ่มส้มพีช)"""

    def __init__(self):
        self.ccfg = load_client_cfg()
        self.result = None
        self.busy = False
        self.buttons, self.pw_entries = [], []
        self.th = ui.LOGIN
        self.root = tk.Tk()
        ui.begin(self.root)
        ui.setup_ttk(self.th)
        self.root.title("Fisch Client — Authentication")
        self.root.configure(bg=self.th.bg)
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.show_var = tk.BooleanVar(value=False)
        self.remember_var = tk.BooleanVar(value=True)
        self._lay_pending = False
        self.build()
        self.relayout()
        self.root.update_idletasks()
        w, h = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = max(10, (self.root.winfo_screenheight() - h) // 3)
        self.root.geometry(f"+{x}+{y}")

    # ---------- วาดพื้นหลังไล่สี + การ์ดมุมมนให้พอดีกับเนื้อหา (ปรับใหม่ทุกครั้งที่เปลี่ยนแท็บ)
    def relayout(self):
        self._lay_pending = False
        th = self.th
        try:
            P, M = ui.sc(26), ui.sc(22)
            cw, ch = self.card.winfo_reqwidth(), self.card.winfo_reqheight()
            W, H = cw + 2 * (P + M), ch + 2 * (P + M)
            self.cv.configure(width=W, height=H)
            self._bgph = ui.photo(ui.bg_image(W, H, th))
            self.cv.itemconfigure(self._bg, image=self._bgph)
            self._cph = ui.photo(ui.rr(cw + 2 * P, ch + 2 * P, ui.sc(28), fill=th.card, outline=th.card_line))
            self.cv.itemconfigure(self._cardimg, image=self._cph)
            self.cv.coords(self._cardimg, M, M)
            self.cv.coords(self._cardwin, M + P, M + P)
        except tk.TclError:
            pass

    def _on_card_cfg(self, _e=None):
        if not self._lay_pending:
            self._lay_pending = True
            self.root.after_idle(self.relayout)

    # ---------- UI Components
    def field(self, parent, label, hint="", show=""):
        ph = ui.spaced(label) + (f"   ·   {hint}" if hint else "")
        e = ui.RoundEntry(parent, self.th, placeholder=ph, show=show, justify="center", height=42,
                          font=(FONT_NAME, 9))
        e.pack(fill="x", pady=(0, 10))
        if show:
            self.pw_entries.append(e)
        return e

    def msg_label(self, parent):
        lbl = tk.Label(parent, text="", wraplength=ui.sc(330), justify="center", bg=self.th.card,
                       fg=self.th.muted, font=(FONT_NAME, 9))
        lbl.pack(pady=(2, 0))
        return lbl

    def action_btn(self, parent, text, cmd):
        b = ui.GButton(parent, text, cmd, kind="peach", theme=self.th, height=46, radius=16,
                       spaced_text=True, font=(FONT_NAME, 11, "bold"))
        b.pack(fill="x", pady=(12, 0))
        self.buttons.append(b)
        return b

    def toggles(self, parent, remember=False):
        row = tk.Frame(parent, bg=self.th.card)
        row.pack(fill="x", pady=(2, 4))
        ui.toggle_row(row, "Show password", self.show_var, self.th).pack(side="left")
        if remember:
            ui.toggle_row(row, "Remember me", self.remember_var, self.th).pack(side="right")

    def date_label(self, parent, text, hint=""):
        t = ui.spaced(text) + (f"   ·   {hint}" if hint else "")
        tk.Label(parent, text=t, bg=self.th.card, fg=self.th.muted, font=(FONT_NAME, 8)).pack(anchor="w",
                                                                                          pady=(0, 4))

    def build(self):
        th = self.th
        self.cv = tk.Canvas(self.root, bg=th.bg, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        self._bg = self.cv.create_image(0, 0, anchor="nw")
        self._cardimg = self.cv.create_image(0, 0, anchor="nw")
        self.card = tk.Frame(self.cv, bg=th.card)
        self._cardwin = self.cv.create_window(0, 0, window=self.card, anchor="nw")
        self.card.bind("<Configure>", self._on_card_cfg)
        self.show_var.trace_add("write", lambda *_: self.toggle_show())
        card = self.card

        tk.Frame(card, width=ui.sc(350), height=1, bg=th.card).pack()          # กำหนดความกว้างการ์ด
        self._av = ui.photo(ui.avatar_img(ui.sc(62), th))
        tk.Label(card, image=self._av, bg=th.card).pack(pady=(0, 10))
        tk.Label(card, text=ui.spaced("FISCH MACRO"), bg=th.card, fg=th.fg,
                 font=(FONT_NAME, 15, "bold")).pack()
        tk.Label(card, text="Secure account portal", bg=th.card, fg=th.muted,
                 font=(FONT_NAME, 9)).pack(pady=(2, 16))

        self.nb = ui.PillTabs(card, th, stack=False, spaced_text=True, gap=16)
        self.nb.pack(fill="x")

        # --- Tab 1: Sign In
        t1 = self.nb.add_page("SIGN IN")
        self.l_user = self.field(t1, "USERNAME", "ชื่อผู้ใช้")
        self.l_pw = self.field(t1, "PASSWORD", "รหัสผ่าน", "•")
        self.toggles(t1, remember=True)
        self.l_err = self.msg_label(t1)
        self.action_btn(t1, "LOGIN", self.do_login)

        # --- Tab 2: Register (Create Account)
        t2 = self.nb.add_page("REGISTER")
        self.r_user = self.field(t2, "USERNAME", "a-z, 0-9, 3-20 chars")
        self.r_pw = self.field(t2, "PASSWORD", "min. 6 characters", "•")
        self.r_pw2 = self.field(t2, "CONFIRM PASSWORD", "", "•")
        self.r_nick = self.field(t2, "NICKNAME", "ชื่อเล่น / Display Name")
        self.date_label(t2, "DATE OF BIRTH", "วันเกิด")
        self.r_bday = DateField(t2, th)
        self.r_bday.pack(fill="x", pady=(0, 8))
        self.toggles(t2)
        self.r_err = self.msg_label(t2)
        self.action_btn(t2, "CREATE ACCOUNT", self.do_register)

        # --- Tab 3: Forgot Password
        t3 = self.nb.add_page("FORGOT")
        tk.Label(t3, text="Verify your registered nickname and birthdate to reset your password.",
                 bg=th.card, fg=th.muted, font=(FONT_NAME, 9), wraplength=ui.sc(330),
                 justify="center").pack(pady=(0, 10))
        self.f_nick = self.field(t3, "NICKNAME", "ชื่อเล่นที่ใช้ตอนสมัคร")
        self.date_label(t3, "DATE OF BIRTH", "วันเกิด")
        self.f_bday = DateField(t3, th)
        self.f_bday.pack(fill="x", pady=(0, 10))
        self.f_user = self.field(t3, "USERNAME", "optional / ถ้าจำได้")
        self.f_pw = self.field(t3, "NEW PASSWORD", "รหัสผ่านใหม่", "•")
        self.f_pw2 = self.field(t3, "CONFIRM NEW PASSWORD", "", "•")
        self.toggles(t3)
        self.f_err = self.msg_label(t3)
        self.action_btn(t3, "RESET PASSWORD", self.do_reset)

        # --- Server connection section
        tk.Frame(card, height=1, bg=th.card_line).pack(fill="x", pady=(16, 10))
        tk.Label(card, text=ui.spaced("SERVER"), bg=th.card, fg=th.dim, font=(FONT_NAME, 8)).pack(anchor="w")
        row_s = tk.Frame(card, bg=th.card)
        row_s.pack(fill="x", pady=(5, 0))
        self.t_btn = ui.GButton(row_s, "TEST", self.do_test, theme=th, height=34, width=70, radius=12,
                                spaced_text=True)
        self.t_btn.pack(side="right", padx=(8, 0))
        self.buttons.append(self.t_btn)
        self.e_srv = ui.RoundEntry(row_s, th, height=34, radius=12, font=(FONT_NAME, 9), pad=12)
        self.e_srv.pack(side="left", fill="x", expand=True)
        self.e_srv.insert(0, self.ccfg.get("server", DEFAULT_SERVER))
        self.srv_lbl = tk.Label(card, text="", bg=th.card, fg=th.muted, font=(FONT_NAME, 8),
                                wraplength=ui.sc(330), justify="left")

        last = self.ccfg.get("last_user", "")
        if last:
            self.l_user.insert(0, last)
            self.l_pw.focus_set()
        else:
            self.l_user.focus_set()
        self.root.bind("<Return>", self.on_enter)

    # ---------- Helpers
    def toggle_show(self):
        ch = "" if self.show_var.get() else "•"
        for e in self.pw_entries:
            e.config(show=ch)

    def say(self, label, text, kind="err"):
        prefix = {"ok": "✓ ", "err": "✕ ", "info": "● "}.get(kind, "")
        th = self.th
        color = {"err": th.err, "ok": th.ok, "info": th.info}.get(kind, th.muted)
        label.config(text=f"{prefix}{text}" if text else "", fg=color)
        if label is self.srv_lbl:                       # บรรทัดสถานะเซิร์ฟเวอร์ โชว์เฉพาะตอนมีข้อความ
            if text:
                label.pack(anchor="w", pady=(6, 0))
            else:
                label.pack_forget()

    def set_busy(self, busy):
        self.busy = busy
        for b in self.buttons:
            b.config(state="disabled" if busy else "normal")

    def get_api(self, label):
        url = self.e_srv.get().strip()
        if not url:
            self.say(label, "Please enter server address.")
            return None
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
            self.e_srv.delete(0, "end")
            self.e_srv.insert(0, url)
        return ApiClient(url)

    def on_enter(self, _=None):
        if not self.busy:
            (self.do_login, self.do_register, self.do_reset)[self.nb.index("current")]()

    def finish(self, api, info):
        save_client_cfg({"server": api.base,
                         "last_user": info["username"] if self.remember_var.get() else ""})
        self.result = (api, info)
        self.root.destroy()

    # ---------- Actions
    def do_test(self):
        api = self.get_api(self.srv_lbl)
        if not api:
            return
        self.say(self.srv_lbl, "Testing server connection...", "info")
        self.set_busy(True)

        def ok(_):
            self.set_busy(False)
            self.say(self.srv_lbl, "Connected to backend server successfully.", "ok")

        def err(e):
            self.set_busy(False)
            self.say(self.srv_lbl, e.message, "err")

        run_bg(self.root, api.health, ok, err)

    def do_login(self):
        user, pw = self.l_user.get().strip(), self.l_pw.get()
        if not user or not pw:
            self.say(self.l_err, "Please enter your username and password.")
            return
        api = self.get_api(self.l_err)
        if not api:
            return
        self.say(self.l_err, "Signing in...", "info")
        self.set_busy(True)

        def ok(info):
            self.set_busy(False)
            self.finish(api, info)

        def err(e):
            self.set_busy(False)
            self.l_pw.delete(0, "end")
            self.say(self.l_err, e.message, "err")

        run_bg(self.root, lambda: api.login(user, pw), ok, err)

    def do_register(self):
        user, pw, pw2 = self.r_user.get().strip(), self.r_pw.get(), self.r_pw2.get()
        nick, bday = self.r_nick.get().strip(), self.r_bday.get()
        if not (user and pw and nick):
            self.say(self.r_err, "Please fill in all required fields.")
            return
        if pw != pw2:
            self.say(self.r_err, "Passwords do not match.")
            return
        if bday is None:
            self.say(self.r_err, "Please select a valid date of birth.")
            return
        api = self.get_api(self.r_err)
        if not api:
            return
        self.say(self.r_err, "Creating account...", "info")
        self.set_busy(True)

        def work():
            api.register(user, pw, nick, bday)
            return api.login(user, pw)

        def ok(info):
            self.set_busy(False)
            self.finish(api, info)

        def err(e):
            self.set_busy(False)
            self.say(self.r_err, e.message, "err")

        run_bg(self.root, work, ok, err)

    def do_reset(self):
        user, nick, bday = self.f_user.get().strip(), self.f_nick.get().strip(), self.f_bday.get()
        pw, pw2 = self.f_pw.get(), self.f_pw2.get()
        if not (nick and pw):
            self.say(self.f_err, "Please enter your nickname and new password.")
            return
        if bday is None:
            self.say(self.f_err, "Please select a valid date of birth.")
            return
        if pw != pw2:
            self.say(self.f_err, "New passwords do not match.")
            return
        api = self.get_api(self.f_err)
        if not api:
            return
        self.say(self.f_err, "Verifying credentials...", "info")
        self.set_busy(True)

        def ok(_):
            self.set_busy(False)
            for e in (self.f_nick, self.f_pw, self.f_pw2):
                e.delete(0, "end")
            self.f_bday.clear()
            self.say(self.f_err, "")
            self.l_user.delete(0, "end")
            self.l_user.insert(0, user or nick)
            self.l_pw.delete(0, "end")
            self.nb.select(0)
            self.say(self.l_err, "Password reset successful! Sign in with your new password.", "ok")
            self.l_pw.focus_set()

        def err(e):
            self.set_busy(False)
            self.say(self.f_err, e.message, "err")

        run_bg(self.root, lambda: api.reset_password(user, bday, nick, pw), ok, err)

    def run(self):
        self.root.mainloop()
        return self.result


class AccountDialog:
    """บัญชีของฉัน: ดู ID / เปลี่ยนรหัสผ่าน / (ผู้ดูแล) จัดการผู้ใช้ทั้งหมดและซิงค์ Google Sheet"""

    def __init__(self, parent, api, info, log):
        self.api, self.info, self.log = api, info, log
        self.uid = info.get("id")
        self.user = info.get("username", "")
        self.rows = {}
        is_admin = info.get("role") == "admin"
        th = TH
        top = self.top = tk.Toplevel(parent)
        top.title("บัญชีผู้ใช้")
        top.configure(bg=BG)
        top.resizable(False, False)
        top.attributes("-topmost", True)
        top.transient(parent)
        body = tk.Frame(top, bg=BG, padx=ui.sc(14), pady=ui.sc(12))
        body.pack()

        def section(title):
            c = ui.Card(body, title=title)
            c.pack(fill="x", pady=(0, 10))
            return c.body

        def entry(parent_, label, show=""):
            row = tk.Frame(parent_, bg=th.card)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, width=18, anchor="w", bg=th.card, fg=th.muted, font=FONT).pack(side="left")
            e = ui.RoundEntry(row, th, show=show, width=240, height=32, radius=10, font=(FONT_NAME, 9), pad=10)
            e.pack(side="left", fill="x", expand=True)
            return e

        # การ์ดโปรไฟล์
        pc = ui.Card(body, pad=(14, 12))
        pc.pack(fill="x", pady=(0, 10))
        self._av = ui.photo(ui.avatar_img(ui.sc(48), th))
        tk.Label(pc.body, image=self._av, bg=th.card).pack(side="left", padx=(0, 14))
        tf = tk.Frame(pc.body, bg=th.card)
        tf.pack(side="left")
        tk.Label(tf, text=info.get("nickname") or self.user, bg=th.card, fg=th.fg,
                 font=(FONT_NAME, 12, "bold")).pack(anchor="w")
        tk.Label(tf, text=f"ID {self.uid}   ·   {self.user}   ·   {'ผู้ดูแล' if is_admin else 'ผู้ใช้ทั่วไป'}",
                 bg=th.card, fg=th.muted, font=FONT).pack(anchor="w")

        s1 = section("เปลี่ยนรหัสผ่าน")
        self.e_old = entry(s1, "รหัสผ่านเดิม", "•")
        self.e_new = entry(s1, "รหัสผ่านใหม่", "•")
        self.e_new2 = entry(s1, "ยืนยันรหัสผ่านใหม่", "•")
        ui.GButton(s1, "เปลี่ยนรหัสผ่าน", self.change_pw, kind="primary", height=36).pack(fill="x", pady=(8, 0))
        self.msg1 = tk.Label(s1, text="", wraplength=500, justify="left", bg=th.card, fg=th.muted, font=FONT)
        self.msg1.pack(anchor="w", pady=(6, 0))

        if is_admin:
            s2 = section("ผู้ใช้ทั้งหมด (ผู้ดูแลเท่านั้น)")
            cols = (("id", "ID", 40), ("user", "ชื่อผู้ใช้", 95), ("nick", "ชื่อเล่น", 85),
                    ("bday", "วันเกิด", 80), ("role", "สิทธิ์", 55), ("status", "สถานะ", 55),
                    ("last", "ล็อกอินล่าสุด", 125))
            self.tree = ttk.Treeview(s2, columns=[c[0] for c in cols], show="headings",
                                     height=7, selectmode="browse")
            for key, title, width in cols:
                self.tree.heading(key, text=title)
                self.tree.column(key, width=width, anchor="w")
            self.tree.pack(fill="x")
            btns = tk.Frame(s2, bg=th.card)
            btns.pack(fill="x", pady=(10, 0))
            for i in range(3):
                btns.columnconfigure(i, weight=1, uniform="b")
            ui.GButton(btns, "ระงับ / เปิดใช้งาน", self.toggle_active).grid(
                row=0, column=0, sticky="ew", padx=(0, 6))
            ui.GButton(btns, "รีเซ็ตรหัสผ่าน", self.admin_reset).grid(row=0, column=1, sticky="ew", padx=(0, 6))
            ui.GButton(btns, "ลบผู้ใช้", self.delete_user, kind="stop").grid(row=0, column=2, sticky="ew")
            ui.GButton(btns, "รีเฟรช", self.reload).grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(6, 0))
            ui.GButton(btns, "ซิงค์ไป Google Sheet", self.sync_sheet, kind="primary").grid(
                row=1, column=1, columnspan=2, sticky="ew", pady=(6, 0))
            self.msg2 = tk.Label(s2, text="", wraplength=500, justify="left", bg=th.card, fg=th.muted, font=FONT)
            self.msg2.pack(anchor="w", pady=(8, 0))
            self.reload()

        ui.GButton(body, "ปิด", top.destroy, height=38).pack(fill="x")

    @staticmethod
    def say(label, text, ok=False):
        label.config(text=text, foreground=GREEN if ok else RED)

    # ---------- เปลี่ยนรหัสผ่านของตัวเอง
    def change_pw(self):
        old, new, new2 = self.e_old.get(), self.e_new.get(), self.e_new2.get()
        if new != new2:
            self.say(self.msg1, "รหัสผ่านใหม่ทั้งสองช่องไม่ตรงกัน")
            return

        def ok(_):
            for e in (self.e_old, self.e_new, self.e_new2):
                e.delete(0, "end")
            self.say(self.msg1, "เปลี่ยนรหัสผ่านแล้ว", ok=True)
            self.log("เปลี่ยนรหัสผ่านสำเร็จ")

        run_bg(self.top, lambda: self.api.change_password(old, new), ok,
               lambda e: self.say(self.msg1, e.message))

    # ---------- ผู้ดูแล
    def reload(self):
        run_bg(self.top, self.api.admin_users, self.fill, lambda e: self.say(self.msg2, e.message))

    def fill(self, users):
        self.rows = {u["id"]: u for u in users}
        self.tree.delete(*self.tree.get_children())
        for u in users:
            self.tree.insert("", "end", iid=str(u["id"]), values=(
                u["id"], u["username"], u["nickname"], u["birthday"],
                "ผู้ดูแล" if u["role"] == "admin" else "ผู้ใช้",
                "ใช้งาน" if u["active"] else "ระงับ", u["last_login"] or "-"))
        self.say(self.msg2, f"ผู้ใช้ทั้งหมด {len(users)} คน", ok=True)

    def selected(self):
        sel = self.tree.selection()
        if not sel:
            self.say(self.msg2, "เลือกผู้ใช้ในตารางก่อน")
            return None
        return self.rows.get(int(sel[0]))

    def after_action(self, text):
        self.say(self.msg2, text, ok=True)
        self.reload()

    def toggle_active(self):
        u = self.selected()
        if not u:
            return
        run_bg(self.top, lambda: self.api.admin_set_active(u["id"], not u["active"]),
               lambda _: self.after_action(f"{'ระงับ' if u['active'] else 'เปิดใช้งาน'} {u['username']} แล้ว"),
               lambda e: self.say(self.msg2, e.message))

    def admin_reset(self):
        u = self.selected()
        if not u:
            return
        pw = simpledialog.askstring(
            "รีเซ็ตรหัสผ่าน", f"ตั้งรหัสผ่านใหม่ให้ {u['username']} (อย่างน้อย 6 ตัว)\nเว้นว่าง = ให้ระบบสุ่มให้",
            parent=self.top)
        if pw is None:
            return                                   # กดยกเลิก

        def ok(d):
            messagebox.showinfo("รีเซ็ตรหัสผ่านแล้ว",
                                f"รหัสผ่านใหม่ของ {u['username']} คือ\n\n{d['new_password']}\n\n"
                                "แจ้งผู้ใช้ แล้วให้เปลี่ยนรหัสเองหลังเข้าสู่ระบบ", parent=self.top)
            self.after_action(f"รีเซ็ตรหัสผ่านของ {u['username']} แล้ว")

        run_bg(self.top, lambda: self.api.admin_reset_password(u["id"], pw), ok,
               lambda e: self.say(self.msg2, e.message))

    def delete_user(self):
        u = self.selected()
        if not u:
            return
        if not messagebox.askyesno("ลบผู้ใช้", f"ลบผู้ใช้ '{u['username']}' (ID {u['id']}) ถาวรใช่หรือไม่?",
                                   parent=self.top):
            return
        run_bg(self.top, lambda: self.api.admin_delete(u["id"]),
               lambda _: self.after_action(f"ลบ {u['username']} แล้ว"),
               lambda e: self.say(self.msg2, e.message))

    def sync_sheet(self):
        self.say(self.msg2, "กำลังซิงค์ไป Google Sheet...", ok=True)
        run_bg(self.top, self.api.admin_sync_sheet,
               lambda d: self.say(self.msg2, d["message"], ok=d["ok"]),
               lambda e: self.say(self.msg2, e.message))


# ---------------------------------------------------------------- GUI
class App:
    PREVIEW_W = 480
    MAX_SNAPS = 8

    def __init__(self, root, api=None, info=None):
        self.root = root
        self.api = api
        self.info = info or {}
        self.user = self.info.get("username", "")
        self.role = self.info.get("role", "user")
        self.uid = self.info.get("id", "-")
        self.nickname = self.info.get("nickname", "")
        self.logout_requested = False
        self.kicked = None                     # ข้อความ ถ้าถูกบังคับออกจากระบบ (โดย heartbeat)
        self.hb_stop = threading.Event()
        self.cfg = load_config()
        self.bot = None
        self.catches = 0
        self.started_at = None
        self.q = queue.Queue()
        self.photo = None
        self.pgrab = Grabber()
        self.snaps = []
        self.calib_open = False
        self.vars, self.types, self.bool_vars = {}, {}, {}

        root.title("Fisch Macro")
        root.configure(bg=BG)
        root.attributes("-topmost", True)
        root.resizable(False, False)
        ui.begin(root)
        ui.setup_ttk(TH)
        self.th = th = TH
        sc = ui.sc

        main = tk.Frame(root, bg=BG, padx=sc(14), pady=sc(12))
        main.grid()
        main.columnconfigure(0, weight=1)

        # ===== Header: โลโก้ + ชื่อ + สถิติ + ป้ายสถานะ
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
            side="left", pady=(6, 0))
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

        # ===== แถวปุ่มควบคุม
        ctl = tk.Frame(main, bg=BG)
        ctl.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        self.btn = ui.GButton(ctl, "▶  เริ่ม (F6)", self.toggle, kind="go", theme=th, height=40, width=150,
                              radius=12, font=(FONT_NAME, 10, "bold"))
        self.btn.pack(side="left")
        ui.GButton(ctl, "บันทึก", self.save, theme=th, height=40, width=86, radius=12).pack(side="left", padx=8)
        self.preview_var = tk.BooleanVar(value=True)
        ui.toggle_row(ctl, "Preview", self.preview_var, th).pack(side="left", padx=12)
        ui.GButton(ctl, "ออกจากระบบ", self.logout, theme=th, height=34, radius=12).pack(side="right")
        ui.GButton(ctl, "บัญชี", self.open_account, theme=th, height=34, width=72, radius=12).pack(
            side="right", padx=8)
        tk.Label(ctl, text=f"{self.nickname or self.user}  (ID {self.uid})", bg=BG, fg=MUTED, font=FONT).pack(
            side="right", padx=(0, 4))

        # ===== Preview
        pv = ui.Card(main, title="Preview")
        pv.grid(row=2, column=0, sticky="ew")
        self.preview_img = tk.Label(pv.body, bg=DARK, fg=MUTED, font=FONT, text="(เปิด Preview เพื่อดูภาพ)",
                                    width=64, height=3)
        self.preview_img.pack(fill="x")
        self.preview_txt = tk.Label(pv.body, text="", bg=th.card, fg=MUTED, font=FONT, anchor="w")
        self.preview_txt.pack(fill="x", pady=(6, 0))

        # ===== แท็บ
        nb = ui.PillTabs(main, th, stack=True)
        nb.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.build_calib_tab(nb)
        self.build_settings_tab(nb)
        self.build_log_tab(nb)

        # ===== แถบสถานะล่างสุด
        sb = ui.Card(main, pad=(14, 6), radius=12)
        sb.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        self.status_lbl = tk.Label(sb.body, text="พร้อมใช้งาน", bg=th.card, fg=MUTED, font=FONT)
        self.status_lbl.pack(side="left")
        tk.Label(sb.body, text="F7 หยุดฉุกเฉิน · F8 ถ่ายภาพ", bg=th.card, fg=th.dim, font=FONT).pack(side="right")

        self.hk = keyboard.GlobalHotKeys({
            "<f6>": lambda: self.root.after(0, self.toggle),
            "<f7>": lambda: self.root.after(0, self.stop),
            "<f8>": self.snapshot,          # ถ่ายทันทีใน thread ของ hotkey เพื่อให้ไวที่สุด
        })
        self.hk.start()
        if self.api is not None:
            threading.Thread(target=self.heartbeat, daemon=True).start()

        root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh_cal()
        self.update_snap_lbl()
        self.poll()
        self.update_preview()
        self.log("F8 ถ่ายภาพมินิเกม → เปิดหน้าสอบเทียบ → กดเริ่ม (F6)")

    # ---------- แท็บสอบเทียบ
    def make_chip(self, parent, title):
        th = self.th
        c = ui.Card(parent, pad=(10, 5), radius=11, fill=th.field, line=th.field_line)
        c.pack(side="left", padx=(0, 8))
        sw = tk.Label(c.body, width=2, bg="#000", highlightthickness=1, highlightbackground=th.field_line)
        sw.pack(side="left")
        tk.Label(c.body, text=title, bg=th.field, fg=FG, font=FONT).pack(side="left", padx=(6, 4))
        hx = tk.Label(c.body, text="", bg=th.field, fg=MUTED, font=("Consolas", 8))
        hx.pack(side="left")
        return sw, hx

    def build_calib_tab(self, nb):
        th = self.th
        page = nb.add_page("  สอบเทียบ  ")
        card = ui.Card(page, pad=(16, 14))
        card.pack(fill="both", expand=True)
        cal = card.body
        cal.columnconfigure(1, weight=1)
        self._badge = ui.photo(ui.badge_img(ui.sc(26), th))

        def step(r, num, text):
            tk.Label(cal, text=num, image=self._badge, compound="center", fg="white", bg=th.card,
                     font=(FONT_NAME, 9, "bold")).grid(row=r, column=0, sticky="nw", padx=(0, 10), pady=6)
            tk.Label(cal, text=text, justify="left", bg=th.card, fg=FG, font=FONT).grid(
                row=r, column=1, sticky="w", pady=4)

        step(0, "1", "ตอนมินิเกมโผล่ กด F8 ถ่ายภาพ 2-3 ครั้ง\n(ตอนแถบเป็นสีขาว และตอนเป็นสีน้ำตาล)")
        self.snap_lbl = tk.Label(cal, bg=th.card, fg=ACCENT, font=FONT_B)
        self.snap_lbl.grid(row=0, column=2, padx=10)
        ui.GButton(cal, "ล้างภาพ", self.clear_snaps, theme=th, height=32, width=96).grid(row=0, column=3)

        step(1, "2", "เปิดหน้าสอบเทียบ แล้วลากเลือกพื้นที่\nและคลิกเลือกสีบนภาพนิ่ง")
        ui.GButton(cal, "เปิดหน้าสอบเทียบ", self.open_calib, kind="primary", theme=th, height=34).grid(
            row=1, column=2, columnspan=2, sticky="ew", padx=(10, 0))

        step(2, "3", "ดูผลที่ช่อง Preview ด้านบน แล้วลองทดสอบ")
        ui.GButton(cal, "ทดสอบตรวจจับ", self.test_detect, theme=th, height=34).grid(
            row=2, column=2, columnspan=2, sticky="ew", padx=(10, 0))

        chips = tk.Frame(cal, bg=th.card)
        chips.grid(row=3, column=0, columnspan=4, sticky="w", pady=(12, 0))
        self.fish_sw, self.fish_hx = self.make_chip(chips, "ปลา")
        self.bar_sw, self.bar_hx = self.make_chip(chips, "แถบขาว")
        self.bar2_sw, self.bar2_hx = self.make_chip(chips, "แถบน้ำตาล")
        ui.GButton(chips, "ล้างสีน้ำตาล", self.clear_bar2, theme=th, height=30, radius=10).pack(side="left")

        self.region_lbl = tk.Label(cal, bg=th.card, fg=MUTED, font=FONT)
        self.region_lbl.grid(row=4, column=0, columnspan=4, sticky="w", pady=(10, 0))

    # ---------- แท็บตั้งค่า
    def add_field(self, parent, row, key):
        th = self.th
        label, typ, tip = FIELD_INFO[key]
        lb = tk.Label(parent, text=label, bg=th.card, fg=FG, font=FONT, anchor="w")
        lb.grid(row=row, column=0, sticky="w", pady=5)
        v = tk.StringVar(value=str(self.cfg[key]))
        self.vars[key], self.types[key] = v, typ
        lo, hi, st = SLIDER_RANGE[key]
        sl = ui.GSlider(parent, v, lo, hi, st, theme=th, width=130)
        sl.grid(row=row, column=1, padx=12)
        en = ui.RoundEntry(parent, th, textvariable=v, justify="center", width=66, height=28, radius=9,
                           font=(FONT_NAME, 9), pad=6)
        en.grid(row=row, column=2)
        for w in (lb, sl, en):
            Tip(w, tip)

    def build_settings_tab(self, nb):
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
            row=len(GROUP_TRACK), column=0, columnspan=3, sticky="ew", pady=(16, 0))
        tk.Label(g2.body, text="เอาเมาส์ชี้ช่องต่างๆ เพื่ออ่านคำอธิบาย", bg=th.card, fg=MUTED, font=FONT).grid(
            row=len(GROUP_TRACK) + 1, column=0, columnspan=3, sticky="w", pady=(8, 0))

        g3 = ui.Card(st, title="ตัวเลือก")
        g3.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        for i, (label, key, tip) in enumerate(CHECK_INFO):
            b = tk.BooleanVar(value=bool(self.cfg[key]))
            self.bool_vars[key] = b
            r = ui.toggle_row(g3.body, label, b, th)
            r.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 28), pady=5)
            Tip(r.text, tip)
            Tip(r.toggle, tip)

    # ---------- แท็บ Log
    def build_log_tab(self, nb):
        th = self.th
        page = nb.add_page("  Log  ")
        card = ui.Card(page, pad=(10, 10))
        card.pack(fill="both", expand=True)
        self.logbox = tk.Text(card.body, height=9, width=64, state="disabled", font=(FONT_NAME, 9), bg=DARK,
                              fg=FG, relief="flat", padx=10, pady=8, insertbackground=FG, highlightthickness=0)
        self.logbox.pack(fill="both", expand=True)
        for tag, color in (("err", RED), ("ok", GREEN), ("warn", AMBER), ("info", th.info), ("dim", MUTED)):
            self.logbox.tag_config(tag, foreground=color)

    # ---------- ตัวช่วย
    def log(self, msg):
        self.q.put(f"[{time.strftime('%H:%M:%S')}] {msg}")

    @staticmethod
    def log_tag(line):
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
        if self.kicked:                           # ถูกระงับ/ลบ/หมดอายุ/ขาดการเชื่อมต่อ -> ออกจากระบบ
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
        text, color = PHASES[self.bot.phase if running else "idle"]
        self.chip.config(text=f"●  {text}", bg=color, fg="white" if color == IDLE_COLOR else "#06202a")
        self.st_fish.config(text=str(self.catches))
        if running:
            s = int(time.time() - self.started_at)
            self.st_time.config(text=f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}")
            self.st_cycle.config(text=str(self.bot.cycle))
        self.root.after(200, self.poll)

    def refresh_cal(self):
        x, y, w, h = self.cfg["region"]
        self.region_lbl.config(text=f"พื้นที่จับภาพ:  x={x}  y={y}  กว้าง={w}  สูง={h}")
        for sw, hx, key in ((self.fish_sw, self.fish_hx, "fish_color"),
                            (self.bar_sw, self.bar_hx, "bar_color"),
                            (self.bar2_sw, self.bar2_hx, "bar_color2")):
            c = self.cfg.get(key)
            sw.config(bg=rgb_hex(c) if c else "#000")
            hx.config(text=rgb_hex(c) if c else "ยังไม่ได้เลือก")

    def clear_bar2(self):
        self.cfg["bar_color2"] = None
        self.refresh_cal()
        self.log("ล้างสีแถบน้ำตาลแล้ว")

    def cur_tol(self):
        try:
            return int(self.vars["tolerance"].get())
        except ValueError:
            return self.cfg["tolerance"]

    def read_settings(self):
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

    # ---------- Preview
    def update_preview(self):
        running = bool(self.bot and self.bot.is_alive())
        if running:
            # ระหว่างบอททำงานไม่จับภาพซ้ำ (กันแย่ง CPU) แสดงตัวเลขสดจากบอทแทน
            self.preview_txt.config(text=self.bot.live or "กำลังทำงาน...", foreground=ACCENT)
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
                         f"(แดง=ปลา  เขียว=แถบขาว  เหลือง=แถบน้ำตาล)")
            except Exception as e:
                self.preview_txt.config(text=f"preview error: {e}")
        elif not self.preview_var.get():
            self.preview_img.config(image="", text="(เปิด Preview เพื่อดูภาพ)", width=64, height=3)
            self.preview_txt.config(text="")
        self.root.after(150, self.update_preview)

    # ---------- ภาพนิ่งสำหรับสอบเทียบ
    def snapshot(self):
        """ถูกเรียกจาก hotkey F8 (อยู่ใน thread ของ pynput)"""
        if self.calib_open:
            return
        try:
            img = ImageGrab.grab().convert("RGB")      # จอหลัก (พิกัดเริ่มที่ 0,0 เหมือนที่บอทใช้)
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

        # ---- แถบเครื่องมือ
        bar = tk.Frame(canvas, bg=PANEL, padx=10, pady=6, highlightthickness=1, highlightbackground=ACCENT)
        row1 = tk.Frame(bar, bg=PANEL)
        row1.pack()
        hint = tk.Label(bar, bg=PANEL, fg=AMBER, font=("Tahoma", 10))
        hint.pack(anchor="w", pady=(4, 0))

        def rb(text, val):
            tk.Radiobutton(row1, text=text, variable=mode, value=val, bg=PANEL, fg=FG,
                           selectcolor=PANEL2, activebackground=PANEL, activeforeground=ACCENT,
                           font=("Tahoma", 10, "bold"), highlightthickness=0).pack(side="left")

        def sw():
            l = tk.Label(row1, width=2, relief="solid", bd=1)
            l.pack(side="left", padx=(0, 10))
            return l

        def tbtn(text, cmd, **kw):
            b = tk.Button(row1, text=text, command=cmd, bg=PANEL2, fg=FG, activebackground=LINE,
                          activeforeground=FG, relief="flat", padx=8, **kw)
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
        spin = tk.Spinbox(row1, from_=0, to=150, width=4, textvariable=self.vars["tolerance"],
                          command=lambda: render(), bg=PANEL2, fg=FG, buttonbackground=PANEL2,
                          insertbackground=FG, relief="flat")
        spin.pack(side="left", padx=(3, 10))
        spin.bind("<KeyRelease>", lambda e: render())
        tk.Checkbutton(row1, text="ดูผลจับสี", variable=overlay, command=lambda: render(),
                       bg=PANEL, fg=FG, selectcolor=PANEL2, activebackground=PANEL,
                       activeforeground=ACCENT, highlightthickness=0).pack(side="left", padx=(0, 10))
        done = tk.Button(row1, text="เสร็จ (Esc)", command=lambda: close(), bg="#16a34a", fg="white",
                         activebackground=GREEN, activeforeground="white", relief="flat", padx=10,
                         font=("Tahoma", 9, "bold"))
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

    # ---------- ควบคุมบอท
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
        self.bot = Bot(self.cfg, self.log, self.add_catch, self.on_finish)
        self.bot.start()
        self.btn.config(text="■  หยุด (F6)", style="Stop.TButton")

    def stop(self):
        if self.bot and self.bot.is_alive():
            self.bot.stop()
            self.log("กำลังหยุด...")

    def add_catch(self):
        self.catches += 1

    def on_finish(self):
        try:
            self.root.after(0, self._finished)
        except Exception:
            pass                       # หน้าต่างถูกปิดไปแล้ว (ออกจากระบบ/ปิดโปรแกรม)

    def _finished(self):
        self.btn.config(text="▶  เริ่ม (F6)", style="Go.TButton")
        self.log("หยุดการทำงานแล้ว")

    # ---------- บัญชี / เซิร์ฟเวอร์
    def heartbeat(self):
        """thread เบื้องหลัง: ถามเซิร์ฟเวอร์เป็นระยะว่าบัญชียังใช้งานได้ไหม"""
        fails = 0
        while not self.hb_stop.wait(HEARTBEAT_SECS):
            try:
                self.api.me()
                fails = 0
            except ClientError as e:
                if e.status in (401, 403):            # หมดอายุ / ถูกลบ / ถูกระงับ
                    self.kicked = e.message
                    return
                fails += 1                            # ต่อเซิร์ฟเวอร์ไม่ได้ชั่วคราว ให้โอกาสหลายครั้ง
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
                    api.logout()                      # บอกเซิร์ฟเวอร์ให้ยกเลิก token
                except Exception:
                    pass
            threading.Thread(target=bye, daemon=True).start()
        self.close()

    def close(self):
        self.hb_stop.set()
        self.stop()
        try:
            self.hk.stop()
        except Exception:
            pass
        self.root.destroy()


def main():
    """ต้องล็อกอินผ่านเซิร์ฟเวอร์ก่อนถึงจะเปิดหน้าต่างหลักได้ ออกจากระบบแล้วกลับมาหน้าล็อกอินอีกครั้ง"""
    while True:
        login = LoginWindow().run()
        if not login:
            break                                     # ปิดหน้าล็อกอิน = ออกจากโปรแกรม
        api, info = login
        root = tk.Tk()
        app = App(root, api, info)
        root.mainloop()
        if not app.logout_requested:
            break


if __name__ == "__main__":
    main()