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

Modularized in Phase 2-6:
- Core automation & state machine -> core/
- Fishing operations & workflow -> automation/
- Screen capture & CV detection -> vision/
- Database models & repositories -> data/
- Desktop GUI & presentation -> gui/
Preserves 100% backward compatibility for all imports and batch scripts.
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
from tkinter import messagebox, simpledialog, ttk

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageGrab, ImageTk

try:
    from pynput import keyboard
except ImportError:
    keyboard = None

try:
    import mss
except ImportError:
    mss = None

try:
    import winsound
except ImportError:
    winsound = None

import ui_kit as ui

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
from data.config import ConfigManager

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

_config_manager = ConfigManager(CONFIG_FILE, DEFAULTS)


def load_config():
    return _config_manager.load()


def save_config(cfg):
    _config_manager.save(cfg)


def rgb_hex(c):
    if not c:
        return "#000000"
    return "#%02x%02x%02x" % tuple(int(v) for v in c)


# ---------------------------------------------------------------- จับภาพ + ตรวจจับ (via vision)
from vision import (
    BAR_GAP,
    FISH_GAP,
    Grabber,
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

        start = time.time()
        last_t = start
        misses = 0

        while not self.stopped() and time.time() - start < cfg["reel_timeout"]:
            t = time.time()
            dt = t - last_t
            last_t = t
            self.check_failsafe()

            arr = self.grabber.grab(region, stride=stride)
            f_runs, b_runs, *_ = analyze(arr, cfg)
            fx, bx = centers(f_runs, b_runs)

            bw = measure(b_runs)
            if bw:
                bar_w = bw if bar_w is None else 0.85 * bar_w + 0.15 * bw

            if fx is None and bx is None:
                misses += 1
                if misses > 10:
                    break
            else:
                misses = 0

            fx_p, f_vx = ft.update(fx, t, lat)
            bx_p, b_vx = bt.update(bx, t, 0.0)

            half = (bar_w or 80) / 2.0
            u = ctrl.compute(fx_p, bx_p, f_vx, b_vx, half, dt=dt)
            press = modulator.step(u)
            self.hold(press)

            err_disp = (fx_p - bx_p) if (fx_p is not None and bx_p is not None) else 0.0
            self.live = f"ดึงปลา: err={err_disp:+.0f}px  u={u:.2f}  {'[กด]' if press else '[ปล่อย]'}"

            if cfg["trace"]:
                trace.append((t - start, fx, bx, fx_p, bx_p, f_vx, b_vx, half, u, 1 if press else 0))

            time.sleep(0.006)

        self.hold(False)
        self.phase = "rest"
        self.live = "จบมินิเกม"
        self.log("จบมินิเกม")

        if cfg["trace"] and trace:
            try:
                with open(TRACE_FILE, "w", newline="", encoding="utf-8") as fp:
                    w = csv.writer(fp)
                    w.writerow(["t", "fish_raw", "bar_raw", "fish_pred", "bar_pred",
                                "fish_vx", "bar_vx", "half_bar", "u", "pressed"])
                    w.writerows(trace)
                self.log(f"บันทึก trace: {len(trace)} เฟรม")
            except Exception as e:
                self.log(f"บันทึก trace ไม่ได้: {e}")

    def run(self):
        self.log("บอทเริ่มทำงาน")
        self.grabber = Grabber()

        if self.cfg["start_delay"] > 0:
            self.phase = "start"
            for left in range(self.cfg["start_delay"], 0, -1):
                if self.stopped():
                    break
                self.live = f"เริ่มใน {left} วินาที... (สลับไปหน้าต่างเกม)"
                self.log(f"นับถอยหลัง: {left}")
                self.wait(1.0)

        if not self.stopped() and self.cfg["equip_on_start"]:
            tap(self.cfg["rod_slot"])
            self.log(f"กดช่องเบ็ด ({self.cfg['rod_slot']})")
            self.wait(0.5)

        try:
            while not self.stopped():
                self.cycle += 1
                self.log(f"--- รอบที่ {self.cycle} ---")
                self.cast()
                if self.stopped():
                    break
                if self.wait_for_bite():
                    self.log("มินิเกมเริ่ม!")
                    self.reel()
                    self.on_catch()
                else:
                    self.log("รอปลากินหมดเวลา เหวี่ยงใหม่")
                if self.stopped():
                    break
                self.phase = "rest"
                self.live = f"พัก {self.cfg['loop_delay']} วิ ก่อนรอบถัดไป"
                self.wait(self.cfg["loop_delay"])
        finally:
            self.hold(False)
            self.phase = "idle"
            self.live = "หยุดทำงานแล้ว"
            if self.grabber:
                try:
                    self.grabber.close()
                except Exception:
                    pass
            self.on_finish()


# ---------------------------------------------------------------- สไตล์ / การตั้งค่า UI
TH = ui.MAIN
BG = TH.bg
FG = TH.fg
MUTED = TH.muted
ACCENT = TH.accent
DARK = "#0b1220"
PANEL = TH.card
PANEL2 = TH.field
LINE = TH.field_line
AMBER = TH.warn
GREEN = TH.ok
RED = TH.err

FONT_NAME = ui.FONT_NAME
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


# ---------------------------------------------------------------- GUI (via gui package)
from gui import (
    AccountDialog,
    ApiClient,
    App,
    ClientError,
    CLIENT_CFG_FILE,
    DateField,
    DEFAULT_SERVER,
    LoginWindow,
    MacroDashboard,
    Tip,
    load_client_cfg,
    run_bg,
    save_client_cfg,
)


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
