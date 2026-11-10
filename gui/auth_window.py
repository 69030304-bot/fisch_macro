"""
gui/auth_window.py - Authentication window (Sign In, Register, Forgot Password).

Owned by Member 69030208 (นายฤทธิพร วงค์ป้อม — GUI & DB Integration)
in collaboration with Member 69030377 (นางสาวพิชชาภา ภูววิไลเมธา — UX/UI Design).
Applies LOGIN theme (indigo/peach) and non-blocking asynchronous requests.
"""
import sys
import tkinter as tk
from typing import Optional, Tuple

import ui_kit as ui
from gui.client import (
    ApiClient,
    ClientError,
    DEFAULT_SERVER,
    load_client_cfg,
    run_bg,
    save_client_cfg,
)
from gui.widgets import DateField, FONT_NAME


class LoginWindow:
    """Modern modal dialog for user authentication: Sign In, Register, Forgot Password."""

    def __init__(self):
        self.ccfg = load_client_cfg()
        self.result: Optional[Tuple[ApiClient, dict]] = None
        self.busy = False
        self.buttons = []
        self.pw_entries = []
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

    def relayout(self):
        """Draw gradient background and rounded card matching current tab contents."""
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

    def field(self, parent, label, hint="", show=""):
        ph = ui.spaced(label) + (f"   ·   {hint}" if hint else "")
        e = ui.RoundEntry(
            parent, self.th, placeholder=ph, show=show, justify="center", height=42, font=(FONT_NAME, 9)
        )
        e.pack(fill="x", pady=(0, 10))
        if show:
            self.pw_entries.append(e)
        return e

    def msg_label(self, parent):
        lbl = tk.Label(
            parent,
            text="",
            wraplength=ui.sc(330),
            justify="center",
            bg=self.th.card,
            fg=self.th.muted,
            font=(FONT_NAME, 9),
        )
        lbl.pack(pady=(2, 0))
        return lbl

    def action_btn(self, parent, text, cmd):
        b = ui.GButton(
            parent,
            text,
            cmd,
            kind="peach",
            theme=self.th,
            height=46,
            radius=16,
            spaced_text=True,
            font=(FONT_NAME, 11, "bold"),
        )
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
        tk.Label(parent, text=t, bg=self.th.card, fg=self.th.muted, font=(FONT_NAME, 8)).pack(
            anchor="w", pady=(0, 4)
        )

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

        tk.Frame(card, width=ui.sc(350), height=1, bg=th.card).pack()
        self._av = ui.photo(ui.avatar_img(ui.sc(62), th))
        tk.Label(card, image=self._av, bg=th.card).pack(pady=(0, 10))
        tk.Label(card, text=ui.spaced("FISCH MACRO"), bg=th.card, fg=th.fg, font=(FONT_NAME, 15, "bold")).pack()
        tk.Label(card, text="Secure account portal", bg=th.card, fg=th.muted, font=(FONT_NAME, 9)).pack(
            pady=(2, 16)
        )

        self.nb = ui.PillTabs(card, th, stack=False, spaced_text=True, gap=16)
        self.nb.pack(fill="x")

        # --- Tab 1: Sign In
        t1 = self.nb.add_page("SIGN IN")
        self.l_user = self.field(t1, "USERNAME", "ชื่อผู้ใช้")
        self.l_pw = self.field(t1, "PASSWORD", "รหัสผ่าน", "•")
        self.toggles(t1, remember=True)
        self.l_err = self.msg_label(t1)
        self.action_btn(t1, "LOGIN", self.do_login)

        # --- Tab 2: Register
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
        tk.Label(
            t3,
            text="Verify your registered nickname and birthdate to reset your password.",
            bg=th.card,
            fg=th.muted,
            font=(FONT_NAME, 9),
            wraplength=ui.sc(330),
            justify="center",
        ).pack(pady=(0, 10))
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
        self.t_btn = ui.GButton(
            row_s, "TEST", self.do_test, theme=th, height=34, width=70, radius=12, spaced_text=True
        )
        self.t_btn.pack(side="right", padx=(8, 0))
        self.buttons.append(self.t_btn)
        self.e_srv = ui.RoundEntry(row_s, th, height=34, radius=12, font=(FONT_NAME, 9), pad=12)
        self.e_srv.pack(side="left", fill="x", expand=True)
        self.e_srv.insert(0, self.ccfg.get("server", DEFAULT_SERVER))
        self.srv_lbl = tk.Label(
            card, text="", bg=th.card, fg=th.muted, font=(FONT_NAME, 8), wraplength=ui.sc(330), justify="left"
        )

        last = self.ccfg.get("last_user", "")
        if last:
            self.l_user.insert(0, last)
            self.l_pw.focus_set()
        else:
            self.l_user.focus_set()
        self.root.bind("<Return>", self.on_enter)

    def toggle_show(self):
        ch = "" if self.show_var.get() else "•"
        for e in self.pw_entries:
            e.config(show=ch)

    def say(self, label, text, kind="err"):
        prefix = {"ok": "✓ ", "err": "✕ ", "info": "● "}.get(kind, "")
        th = self.th
        color = {"err": th.err, "ok": th.ok, "info": th.info}.get(kind, th.muted)
        label.config(text=f"{prefix}{text}" if text else "", fg=color)
        if label is self.srv_lbl:
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
        save_client_cfg({
            "server": api.base,
            "last_user": info["username"] if self.remember_var.get() else "",
        })
        self.result = (api, info)
        self.root.destroy()

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

    def run(self) -> Optional[Tuple[ApiClient, dict]]:
        """Start the Tkinter event loop and return (api, user_info) if login succeeded."""
        self.root.mainloop()
        return self.result
