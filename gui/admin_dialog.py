"""
gui/admin_dialog.py - User account and admin management dialog.

Owned by Member 69030208 (นายฤทธิพร วงค์ป้อม — GUI & DB Integration).
Allows password change, user status management, admin reset, and Google Sheet sync.
"""
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable, Dict, Optional

import ui_kit as ui
from gui.client import ApiClient, run_bg
from gui.widgets import FONT, FONT_NAME

GREEN = "#22c55e"
RED = "#ef4444"


class AccountDialog:
    """User account management and administrator panel modal."""

    def __init__(self, parent: tk.Widget, api: ApiClient, info: Dict[str, Any], log_fn: Optional[Callable[[str], None]] = None):
        self.api = api
        self.info = info or {}
        self.log = log_fn or (lambda msg: None)
        self.uid = self.info.get("id")
        self.user = self.info.get("username", "")
        self.rows: Dict[int, dict] = {}
        is_admin = self.info.get("role") == "admin"
        th = ui.MAIN
        self.th = th
        top = self.top = tk.Toplevel(parent)
        top.title("บัญชีผู้ใช้")
        top.configure(bg=th.bg)
        top.resizable(False, False)
        top.attributes("-topmost", True)
        top.transient(parent)
        body = tk.Frame(top, bg=th.bg, padx=ui.sc(14), pady=ui.sc(12))
        body.pack()

        def section(title: str) -> tk.Frame:
            c = ui.Card(body, title=title)
            c.pack(fill="x", pady=(0, 10))
            return c.body

        def entry(parent_: tk.Widget, label: str, show: str = "") -> ui.RoundEntry:
            row = tk.Frame(parent_, bg=th.card)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, width=18, anchor="w", bg=th.card, fg=th.muted, font=FONT).pack(side="left")
            e = ui.RoundEntry(row, th, show=show, width=240, height=32, radius=10, font=(FONT_NAME, 9), pad=10)
            e.pack(side="left", fill="x", expand=True)
            return e

        # Profile card
        pc = ui.Card(body, pad=(14, 12))
        pc.pack(fill="x", pady=(0, 10))
        self._av = ui.photo(ui.avatar_img(ui.sc(48), th))
        tk.Label(pc.body, image=self._av, bg=th.card).pack(side="left", padx=(0, 14))
        tf = tk.Frame(pc.body, bg=th.card)
        tf.pack(side="left")
        tk.Label(
            tf, text=self.info.get("nickname") or self.user, bg=th.card, fg=th.fg, font=(FONT_NAME, 12, "bold")
        ).pack(anchor="w")
        tk.Label(
            tf,
            text=f"ID {self.uid}   ·   {self.user}   ·   {'ผู้ดูแล' if is_admin else 'ผู้ใช้ทั่วไป'}",
            bg=th.card,
            fg=th.muted,
            font=FONT,
        ).pack(anchor="w")

        # Change password section
        s1 = section("เปลี่ยนรหัสผ่าน")
        self.e_old = entry(s1, "รหัสผ่านเดิม", "•")
        self.e_new = entry(s1, "รหัสผ่านใหม่", "•")
        self.e_new2 = entry(s1, "ยืนยันรหัสผ่านใหม่", "•")
        ui.GButton(s1, "เปลี่ยนรหัสผ่าน", self.change_pw, kind="primary", height=36).pack(fill="x", pady=(8, 0))
        self.msg1 = tk.Label(s1, text="", wraplength=500, justify="left", bg=th.card, fg=th.muted, font=FONT)
        self.msg1.pack(anchor="w", pady=(6, 0))

        # Admin only section
        if is_admin:
            s2 = section("ผู้ใช้ทั้งหมด (ผู้ดูแลเท่านั้น)")
            cols = (
                ("id", "ID", 40),
                ("user", "ชื่อผู้ใช้", 95),
                ("nick", "ชื่อเล่น", 85),
                ("bday", "วันเกิด", 80),
                ("role", "สิทธิ์", 55),
                ("status", "สถานะ", 55),
                ("last", "ล็อกอินล่าสุด", 125),
            )
            self.tree = ttk.Treeview(s2, columns=[c[0] for c in cols], show="headings", height=7, selectmode="browse")
            for key, title, width in cols:
                self.tree.heading(key, text=title)
                self.tree.column(key, width=width, anchor="w")
            self.tree.pack(fill="x")
            btns = tk.Frame(s2, bg=th.card)
            btns.pack(fill="x", pady=(10, 0))
            for i in range(3):
                btns.columnconfigure(i, weight=1, uniform="b")
            ui.GButton(btns, "ระงับ / เปิดใช้งาน", self.toggle_active).grid(
                row=0, column=0, sticky="ew", padx=(0, 6)
            )
            ui.GButton(btns, "รีเซ็ตรหัสผ่าน", self.admin_reset).grid(
                row=0, column=1, sticky="ew", padx=(0, 6)
            )
            ui.GButton(btns, "ลบผู้ใช้", self.delete_user, kind="stop").grid(row=0, column=2, sticky="ew")
            ui.GButton(btns, "รีเฟรช", self.reload).grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(6, 0))
            ui.GButton(btns, "ซิงค์ไป Google Sheet", self.sync_sheet, kind="primary").grid(
                row=1, column=1, columnspan=2, sticky="ew", pady=(6, 0)
            )
            self.msg2 = tk.Label(s2, text="", wraplength=500, justify="left", bg=th.card, fg=th.muted, font=FONT)
            self.msg2.pack(anchor="w", pady=(8, 0))
            self.reload()

        ui.GButton(body, "ปิด", top.destroy, height=38).pack(fill="x")

    @staticmethod
    def say(label: tk.Label, text: str, ok: bool = False) -> None:
        label.config(text=text, foreground=GREEN if ok else RED)

    def change_pw(self) -> None:
        old, new, new2 = self.e_old.get(), self.e_new.get(), self.e_new2.get()
        if new != new2:
            self.say(self.msg1, "รหัสผ่านใหม่ทั้งสองช่องไม่ตรงกัน")
            return

        def ok(_):
            for e in (self.e_old, self.e_new, self.e_new2):
                e.delete(0, "end")
            self.say(self.msg1, "เปลี่ยนรหัสผ่านแล้ว", ok=True)
            self.log("เปลี่ยนรหัสผ่านสำเร็จ")

        run_bg(self.top, lambda: self.api.change_password(old, new), ok, lambda e: self.say(self.msg1, e.message))

    def reload(self) -> None:
        run_bg(self.top, self.api.admin_users, self.fill, lambda e: self.say(self.msg2, e.message))

    def fill(self, users: list) -> None:
        self.rows = {u["id"]: u for u in users}
        self.tree.delete(*self.tree.get_children())
        for u in users:
            self.tree.insert(
                "",
                "end",
                iid=str(u["id"]),
                values=(
                    u["id"],
                    u["username"],
                    u["nickname"],
                    u["birthday"],
                    "ผู้ดูแล" if u["role"] == "admin" else "ผู้ใช้",
                    "ใช้งาน" if u["active"] else "ระงับ",
                    u["last_login"] or "-",
                ),
            )
        self.say(self.msg2, f"ผู้ใช้ทั้งหมด {len(users)} คน", ok=True)

    def selected(self) -> Optional[dict]:
        sel = self.tree.selection()
        if not sel:
            self.say(self.msg2, "เลือกผู้ใช้ในตารางก่อน")
            return None
        return self.rows.get(int(sel[0]))

    def after_action(self, text: str) -> None:
        self.say(self.msg2, text, ok=True)
        self.reload()

    def toggle_active(self) -> None:
        u = self.selected()
        if not u:
            return
        run_bg(
            self.top,
            lambda: self.api.admin_set_active(u["id"], not u["active"]),
            lambda _: self.after_action(f"{'ระงับ' if u['active'] else 'เปิดใช้งาน'} {u['username']} แล้ว"),
            lambda e: self.say(self.msg2, e.message),
        )

    def admin_reset(self) -> None:
        u = self.selected()
        if not u:
            return
        pw = simpledialog.askstring(
            "รีเซ็ตรหัสผ่าน",
            f"ตั้งรหัสผ่านใหม่ให้ {u['username']} (อย่างน้อย 6 ตัว)\nเว้นว่าง = ให้ระบบสุ่มให้",
            parent=self.top,
        )
        if pw is None:
            return

        def ok(d):
            messagebox.showinfo(
                "รีเซ็ตรหัสผ่านแล้ว",
                f"รหัสผ่านใหม่ของ {u['username']} คือ\n\n{d['new_password']}\n\n"
                "แจ้งผู้ใช้ แล้วให้เปลี่ยนรหัสเองหลังเข้าสู่ระบบ",
                parent=self.top,
            )
            self.after_action(f"รีเซ็ตรหัสผ่านของ {u['username']} แล้ว")

        run_bg(self.top, lambda: self.api.admin_reset_password(u["id"], pw), ok, lambda e: self.say(self.msg2, e.message))

    def delete_user(self) -> None:
        u = self.selected()
        if not u:
            return
        if not messagebox.askyesno(
            "ลบผู้ใช้", f"ลบผู้ใช้ '{u['username']}' (ID {u['id']}) ถาวรใช่หรือไม่?", parent=self.top
        ):
            return
        run_bg(
            self.top,
            lambda: self.api.admin_delete(u["id"]),
            lambda _: self.after_action(f"ลบ {u['username']} แล้ว"),
            lambda e: self.say(self.msg2, e.message),
        )

    def sync_sheet(self) -> None:
        self.say(self.msg2, "กำลังซิงค์ไป Google Sheet...", ok=True)
        run_bg(
            self.top,
            self.api.admin_sync_sheet,
            lambda d: self.say(self.msg2, d["message"], ok=d["ok"]),
            lambda e: self.say(self.msg2, e.message),
        )
