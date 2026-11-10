"""
ui_kit.py - ชุดวิดเจ็ตหน้าตาใหม่ของ Fisch Macro (วาดมุมมน/ไล่สีด้วย Pillow ลงบน Canvas)

มี 2 ธีม:
  MAIN  = หน้าต่างหลัก   (กรมท่าเข้ม + ไล่สีเขียวน้ำทะเล/ม่วง)
  LOGIN = หน้าล็อกอิน    (คราม/ม่วงเข้ม + ปุ่มส้มพีช)

วิดเจ็ตทั้งหมดใช้ tkinter ล้วน + Pillow + numpy (ไม่ต้องลงอะไรเพิ่ม)
ข้อควรรู้: วิดเจ็ตที่วางในการ์ด (Card) ต้องใช้ card.body เป็นตัวแม่ เพื่อให้สีพื้นตรงกัน
"""
import math
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

import numpy as np
from PIL import Image, ImageDraw, ImageTk

FONT_NAME = "Segoe UI" if sys.platform == "win32" else "Tahoma"


class Theme:
    def __init__(self, **kw):
        self.__dict__.update(kw)


MAIN = Theme(
    name="main",
    bg="#0e1427", card="#161f3a", card_line="#2a3760",
    field="#1d2848", field_line="#34457a", field_focus="#2de0c0",
    fg="#e8eefc", muted="#8593b4", dim="#566486",
    accent="#2de0c0", ok="#34d399", warn="#fbbf24", err="#ff7b8a", info="#5fd4ff",
    sel1="#13a6d1", sel2="#1fdcae",
    on1="#13a6d1", on2="#1fdcae", off1="#6a4cf0", off2="#8f6cff",
    track="#3b4775", fill="#1fdcae", ring="#8a6cff", knob="#eef0ff",
    tip_bg="#1b2545", tip_line="#2de0c0",
    btn={
        "primary": ("#13a6d1", "#1fdcae", "#ffffff", "#5ae6cc"),
        "go": ("#0fae86", "#34e0a1", "#ffffff", "#6af0c0"),
        "stop": ("#e5484d", "#ff7d6e", "#ffffff", "#ff9a8f"),
        "purple": ("#6a4cf0", "#9a78ff", "#ffffff", "#b8a2ff"),
        "ghost": (None, None, "#e8eefc", "#3a4a82"),
    },
)

LOGIN = Theme(
    name="login",
    bg="#1f1a63", bg_grad=("#4a3fc8", "#150f4a"), card="#262183", card_line="#4f4ac4",
    field="#2d2a94", field_line="#6f6ee8", field_focus="#cfcfff",
    fg="#ffffff", muted="#bdbbf8", dim="#9895e6",
    accent="#ffb27c", ok="#7ff0c4", warn="#ffd27c", err="#ff93a0", info="#cfcfff",
    sel1="#837ff7", sel2="#5f5be4",
    on1="#f27a6b", on2="#fcbc7c", off1="#4b46c2", off2="#6f6ee8",
    track="#4a46b8", fill="#ffb27c", ring="#ffb27c", knob="#ffffff",
    tip_bg="#2d2a94", tip_line="#cfcfff",
    btn={
        "peach": ("#f27a6b", "#fcbc7c", "#ffffff", "#ffd1ae"),
        "primary": ("#f27a6b", "#fcbc7c", "#ffffff", "#ffd1ae"),
        "ghost": (None, None, "#ffffff", "#6f6ee8"),
    },
)

# ---------------------------------------------------------------- ตัวช่วยพื้นฐาน
_SCALE = [None]


def begin(root):
    """เรียกทุกครั้งที่สร้างหน้าต่าง Tk ใหม่ (ตั้งค่าสเกลตามความละเอียดหน้าจอ)"""
    try:
        _SCALE[0] = max(1.0, root.winfo_fpixels("1i") / 96.0)
    except Exception:
        _SCALE[0] = 1.0


def sc(v):
    """แปลงหน่วย px ตามสเกลหน้าจอ (จอ 125%/150% จะได้ไม่เล็กเกินไป)"""
    return int(round(v * (_SCALE[0] or 1.0)))


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(c1, c2, t):
    a, b = _rgb(c1), _rgb(c2)
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


def lighten(c, t):
    return mix(c, "#ffffff", t)


def darken(c, t):
    return mix(c, "#000000", t)


def spaced(text):
    """เว้นระยะตัวอักษรนิดๆ แบบหัวข้อตัวพิมพ์ใหญ่ในดีไซน์ (ใช้ thin space)"""
    return "\u2009".join(text)


def pbg(w, default="#000000"):
    try:
        return w.cget("bg")
    except tk.TclError:
        return default


def label(parent, text="", kind="fg", theme=None, font=None, **kw):
    """tk.Label สีตามธีม kind: fg / muted / accent / dim / ok / err / warn / info"""
    th = theme or MAIN
    fonts = {"accent": (FONT_NAME, 10, "bold")}
    return tk.Label(parent, text=text, bg=pbg(parent), fg=getattr(th, kind, th.fg),
                    font=font or fonts.get(kind, (FONT_NAME, 9)), **kw)


# ---------------------------------------------------------------- วาดรูป (Pillow)
_CACHE = {}


def _cache_put(key, img):
    if len(_CACHE) > 600:
        _CACHE.clear()
    _CACHE[key] = img
    return img


def _grad(w, h, c1, c2, direction="h"):
    a, b = np.array(_rgb(c1), float), np.array(_rgb(c2), float)
    if direction == "h":
        t = np.linspace(0, 1, w)[None, :, None]
    elif direction == "v":
        t = np.linspace(0, 1, h)[:, None, None]
    else:
        t = ((np.linspace(0, 1, w)[None, :] + np.linspace(0, 1, h)[:, None]) / 2)[:, :, None]
    arr = np.broadcast_to(a + (b - a) * t, (h, w, 3))
    return Image.fromarray(np.ascontiguousarray(arr).astype(np.uint8), "RGB")


def rr(w, h, r, fill=None, grad=None, outline=None, ow=1, direction="h", ss=4):
    """รูปสี่เหลี่ยมมุมมน (ขอบเรียบ anti-alias) พื้นทึบหรือไล่สี + เส้นขอบ"""
    w, h = max(2, int(w)), max(2, int(h))
    key = ("rr", w, h, round(r, 1), fill, grad, outline, ow, direction)
    if key in _CACHE:
        return _CACHE[key]
    W, H, R = w * ss, h * ss, min(r, w / 2, h / 2) * ss
    if grad:
        base = _grad(W, H, grad[0], grad[1], direction).convert("RGBA")
    else:
        base = Image.new("RGBA", (W, H), _rgb(fill or "#000000") + (255,))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W - 1, H - 1), R, fill=255)
    base.putalpha(mask)
    if outline:
        ring = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(ring)
        d.rounded_rectangle((0, 0, W - 1, H - 1), R, fill=255)
        o = ow * ss
        d.rounded_rectangle((o, o, W - 1 - o, H - 1 - o), max(R - o, 0), fill=0)
        base.paste(Image.new("RGBA", (W, H), _rgb(outline) + (255,)), (0, 0), ring)
    return _cache_put(key, base.resize((w, h), Image.LANCZOS))


def photo(img):
    return ImageTk.PhotoImage(img)


def toggle_img(on, w, h, th):
    key = ("tg", on, w, h, th.name)
    if key in _CACHE:
        return _CACHE[key]
    ss = 4
    track = rr(w, h, h / 2, grad=(th.on1, th.on2) if on else (th.off1, th.off2))
    knob = Image.new("RGBA", (w * ss, h * ss), (238, 240, 255, 0))
    d = ImageDraw.Draw(knob)
    m = 3 * ss
    dia = h * ss - 2 * m
    x0 = (w * ss - m - dia) if on else m
    d.ellipse((x0, m, x0 + dia, m + dia), fill=_rgb(th.knob) + (255,))
    out = track.copy()
    out.alpha_composite(knob.resize((w, h), Image.LANCZOS))
    return _cache_put(key, out)


def slider_img(w, h, frac, th):
    key = ("sl", w, h, round(frac, 3), th.name)
    if key in _CACHE:
        return _CACHE[key]
    ss = 4
    W, H = w * ss, h * ss
    kr = H / 2 - ss
    cx = kr + frac * (W - 2 * kr)
    tr = max(4, int(h * 0.28)) * ss
    cy = H / 2
    img = Image.new("RGBA", (W, H), _rgb(th.track) + (0,))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((kr, cy - tr / 2, W - kr, cy + tr / 2), tr / 2, fill=_rgb(th.track) + (255,))
    if cx > kr:
        d.rounded_rectangle((kr, cy - tr / 2, cx, cy + tr / 2), tr / 2, fill=_rgb(th.fill) + (255,))
    d.ellipse((cx - kr, cy - kr, cx + kr, cy + kr), fill=_rgb(th.ring) + (255,))
    ir = kr - 3.2 * ss
    d.ellipse((cx - ir, cy - ir, cx + ir, cy + ir), fill=_rgb(th.knob) + (255,))
    return _cache_put(key, img.resize((w, h), Image.LANCZOS))


def badge_img(num_size, th):
    """วงกลมไล่สี (ใส่เลขขั้นตอน)"""
    key = ("bd", num_size, th.name)
    if key in _CACHE:
        return _CACHE[key]
    return _cache_put(key, rr(num_size, num_size, num_size / 2, grad=(th.sel1, th.sel2), direction="d"))


def fish_logo(size, th):
    """โลโก้ปลาเล็กๆ (วาดด้วย Pillow)"""
    key = ("logo", size, th.name)
    if key in _CACHE:
        return _CACHE[key]
    ss = 4
    base = rr(size * ss, size * ss, size * ss * 0.28, grad=(th.sel1, th.sel2), direction="d", ss=1)
    d = ImageDraw.Draw(base)
    S = size * ss
    d.ellipse((S * .16, S * .32, S * .70, S * .68), fill=(255, 255, 255, 255))
    d.polygon([(S * .62, S * .5), (S * .86, S * .30), (S * .86, S * .70)], fill=(255, 255, 255, 255))
    d.ellipse((S * .27, S * .42, S * .35, S * .50), fill=_rgb(th.sel1) + (255,))
    return _cache_put(key, base.resize((size, size), Image.LANCZOS))


def avatar_img(size, th):
    """ไอคอนผู้ใช้สี่เหลี่ยมมุมมนไล่สีม่วง (เหมือนการ์ดโปรไฟล์ในดีไซน์)"""
    key = ("av", size, th.name)
    if key in _CACHE:
        return _CACHE[key]
    base = rr(size * 4, size * 4, size * 4 * 0.30, grad=("#c58bff", "#7a73ff"), direction="d", ss=1)
    d = ImageDraw.Draw(base)
    S = size * 4
    d.ellipse((S * .36, S * .20, S * .64, S * .48), fill=(255, 255, 255, 255))
    d.pieslice((S * .22, S * .50, S * .78, S * 1.02), 180, 360, fill=(255, 255, 255, 255))
    return _cache_put(key, base.resize((size, size), Image.LANCZOS))


def bg_image(w, h, th):
    """พื้นหลังไล่สีเฉียง + แสงฟุ้งเบาๆ มุมซ้ายบน (หน้าล็อกอิน)"""
    key = ("bgimg", w, h, th.name)
    if key in _CACHE:
        return _CACHE[key]
    g = np.array(_grad(w, h, th.bg_grad[0], th.bg_grad[1], "d"), float)
    yy, xx = np.mgrid[0:h, 0:w]
    glow = np.exp(-(((xx - w * .15) / (w * .55)) ** 2 + ((yy - h * .05) / (h * .45)) ** 2))[:, :, None]
    g = g + (np.array([150, 140, 255]) - g) * glow * 0.22
    glow2 = np.exp(-(((xx - w * .95) / (w * .5)) ** 2 + ((yy - h * 1.0) / (h * .4)) ** 2))[:, :, None]
    g = g + (np.array([120, 90, 230]) - g) * glow2 * 0.18
    return _cache_put(key, Image.fromarray(np.clip(g, 0, 255).astype(np.uint8), "RGB"))


def setup_ttk(th):
    """ธีมของวิดเจ็ต ttk ที่ยังใช้อยู่ (ตาราง Treeview ในหน้าบัญชี)"""
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("Treeview", background=th.field, fieldbackground=th.field, foreground=th.fg,
                borderwidth=1, bordercolor=th.field_line, lightcolor=th.field_line, darkcolor=th.field_line,
                rowheight=sc(24), font=(FONT_NAME, 9))
    s.map("Treeview", background=[("selected", th.sel2)], foreground=[("selected", "#ffffff")])
    s.configure("Treeview.Heading", background=th.card, foreground=th.muted, relief="flat",
                borderwidth=0, font=(FONT_NAME, 9, "bold"), padding=(6, 4))
    s.map("Treeview.Heading", background=[("active", th.field)])
    s.configure("Vertical.TScrollbar", background=th.field_line, troughcolor=th.card,
                bordercolor=th.card, arrowcolor=th.fg, lightcolor=th.field_line, darkcolor=th.field_line)


# ---------------------------------------------------------------- ปุ่มไล่สี
class GButton(tk.Canvas):
    """ปุ่มมุมมนไล่สี  kind: primary / go / stop / purple / peach / ghost
    ใช้แทน ttk.Button ได้: config(text=..., style=..., state=...), command=..."""
    STYLE_MAP = {"TButton": "ghost", "Accent.TButton": "primary", "Go.TButton": "go", "Stop.TButton": "stop"}

    def __init__(self, parent, text="", command=None, kind="ghost", style=None, theme=None,
                 height=34, width=None, font=None, spaced_text=False, radius=10):
        self.th = theme or MAIN
        self._kind = self.STYLE_MAP.get(style, kind) if style else kind
        self._text, self._cmd, self._spaced = text, command, spaced_text
        self._font = font or (FONT_NAME, 9, "bold")
        self._r = sc(radius)
        self._state, self._hover, self._press = "normal", False, False
        h = sc(height)
        w = sc(width) if width else tkfont.Font(font=self._font).measure(self._disp()) + sc(40)
        super().__init__(parent, width=w, height=h, bg=pbg(parent), highlightthickness=0, bd=0,
                         cursor="hand2")
        self._item = self.create_image(0, 0, anchor="nw")
        self._txt = self.create_text(0, 0, text=self._disp(), font=self._font)
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False, press=False))
        self.bind("<ButtonPress-1>", lambda e: self._set(press=True))
        self.bind("<ButtonRelease-1>", self._release)

    def _disp(self):
        return spaced(self._text) if self._spaced else self._text

    def _set(self, hover=None, press=None):
        if hover is not None:
            self._hover = hover
        if press is not None:
            self._press = press
        self._draw()

    def _release(self, e):
        was = self._press
        self._set(press=False)
        inside = 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height()
        if was and inside and self._state != "disabled" and self._cmd:
            self._cmd()

    def _draw(self):
        try:
            w, h = max(self.winfo_width(), 4), max(self.winfo_height(), 4)
            th = self.th
            c1, c2, fg, ol = th.btn.get(self._kind, th.btn["ghost"])
            if self._state == "disabled":
                img, fg = rr(w, h, self._r, fill=th.field, outline=th.field_line), th.dim
            elif c1 is None:
                fill = th.field
                if self._press:
                    fill = darken(fill, .2)
                elif self._hover:
                    fill = lighten(fill, .08)
                img = rr(w, h, self._r, fill=fill, outline=lighten(ol, .3) if self._hover else ol)
            else:
                if self._press:
                    c1, c2 = darken(c1, .15), darken(c2, .15)
                elif self._hover:
                    c1, c2 = lighten(c1, .12), lighten(c2, .12)
                img = rr(w, h, self._r, grad=(c1, c2), outline=ol)
            self._photo = photo(img)
            self.itemconfigure(self._item, image=self._photo)
            self.coords(self._txt, w / 2, h / 2 + (1 if self._press else 0))
            self.itemconfigure(self._txt, text=self._disp(), fill=fg)
        except tk.TclError:
            pass

    def configure(self, cnf=None, **kw):
        if cnf:
            kw.update(cnf)
        if not kw:
            return super().configure()
        redraw = False
        if "text" in kw:
            self._text, redraw = kw.pop("text"), True
        if "style" in kw:
            self._kind, redraw = self.STYLE_MAP.get(kw.pop("style"), "ghost"), True
        if "kind" in kw:
            self._kind, redraw = kw.pop("kind"), True
        if "state" in kw:
            self._state = kw.pop("state")
            kw["cursor"] = "arrow" if self._state == "disabled" else "hand2"
            redraw = True
        if "command" in kw:
            self._cmd = kw.pop("command")
        if kw:
            super().configure(**kw)
        if redraw:
            self._draw()

    config = configure


# ---------------------------------------------------------------- การ์ดมุมมน
class Card(tk.Canvas):
    """กรอบมุมมนมีเส้นขอบบางๆ ใส่ของใน card.body (ใช้ pack/grid อะไรก็ได้)
    ขยายตามเนื้อหา และขยายตามความกว้างที่ผู้จัดวางให้"""

    def __init__(self, parent, theme=None, pad=(14, 12), radius=14, fill=None, line=None, title=None):
        self.th = theme or MAIN
        self.fill = fill or self.th.card
        self.line = self.th.card_line if line is None else line
        self.r, self.px, self.py = sc(radius), sc(pad[0]), sc(pad[1])
        super().__init__(parent, bg=pbg(parent), highlightthickness=0, bd=0, width=sc(20), height=sc(20))
        self._bg = self.create_image(0, 0, anchor="nw")
        self._outer = tk.Frame(self, bg=self.fill)
        self._win = self.create_window(self.px, self.py, window=self._outer, anchor="nw")
        if title:
            tk.Label(self._outer, text=title, bg=self.fill, fg=self.th.accent,
                     font=(FONT_NAME, 10, "bold")).pack(anchor="w", pady=(0, 8))
        self.body = tk.Frame(self._outer, bg=self.fill)
        self.body.pack(fill="both", expand=True)
        self._pend = False
        self.bind("<Configure>", self._on_cfg)
        self._outer.bind("<Configure>", self._on_body)

    def _on_cfg(self, e):
        self.itemconfigure(self._win, width=max(1, e.width - 2 * self.px))
        self._photo = photo(rr(e.width, e.height, self.r, fill=self.fill, outline=self.line))
        self.itemconfigure(self._bg, image=self._photo)

    def _on_body(self, _e):
        if not self._pend:
            self._pend = True
            self.after_idle(self._fit)

    def _fit(self):
        self._pend = False
        try:
            self.configure(height=self._outer.winfo_reqheight() + 2 * self.py,
                           width=self._outer.winfo_reqwidth() + 2 * self.px)
        except tk.TclError:
            pass


class StatCard(Card):
    """ช่องสถิติเล็กๆ (ตัวเลขใหญ่ + คำอธิบาย) config(text=...) เปลี่ยนตัวเลข"""

    def __init__(self, parent, caption, value="0", theme=None):
        super().__init__(parent, theme=theme, pad=(14, 6), radius=12, fill=(theme or MAIN).field,
                         line=(theme or MAIN).field_line)
        th = self.th
        self.val = tk.Label(self.body, text=value, bg=self.fill, fg=th.fg, font=(FONT_NAME, 13, "bold"))
        self.val.pack()
        tk.Label(self.body, text=caption, bg=self.fill, fg=th.muted, font=(FONT_NAME, 8)).pack()

    def configure(self, cnf=None, **kw):
        if "text" in kw:
            self.val.config(text=kw.pop("text"))
        if cnf or kw:
            super().configure(cnf, **kw)

    config = configure


# ---------------------------------------------------------------- ชิปสถานะ (pill)
class Chip(tk.Canvas):
    """ป้ายสถานะทรงเม็ดยา config(text=, bg=, fg=)"""

    def __init__(self, parent, text="", color="#566486", fg="#ffffff", theme=None):
        self.th = theme or MAIN
        self._t, self._c, self._f = text, color, fg
        self._font = (FONT_NAME, 9, "bold")
        super().__init__(parent, bg=pbg(parent), highlightthickness=0, bd=0)
        self._item = self.create_image(0, 0, anchor="nw")
        self._txt = self.create_text(0, 0, font=self._font)
        self._draw()

    def _draw(self):
        f = tkfont.Font(font=self._font)
        w, h = f.measure(self._t) + sc(28), sc(26)
        super().configure(width=w, height=h)
        self._photo = photo(rr(w, h, h / 2, fill=self._c, outline=lighten(self._c, .25)))
        self.itemconfigure(self._item, image=self._photo)
        self.coords(self._txt, w / 2, h / 2)
        self.itemconfigure(self._txt, text=self._t, fill=self._f)

    def configure(self, cnf=None, **kw):
        new = (kw.get("text", self._t), kw.get("bg", self._c), kw.get("fg", self._f))
        if new != (self._t, self._c, self._f):
            self._t, self._c, self._f = new
            self._draw()

    config = configure


# ---------------------------------------------------------------- แท็บแบบ pill
class PillTabs(tk.Frame):
    """แท็บแบบแคปซูล (เหมือน Menu 01 | Selected | Inactive ในดีไซน์)
    page = tabs.add_page("ชื่อ") แล้วใส่ของลงใน page   |  stack=True = ทุกหน้าสูงเท่ากัน หน้าต่างไม่กระโดด"""

    def __init__(self, parent, theme=None, height=36, stack=True, on_change=None, spaced_text=False, gap=10):
        self.th = theme or MAIN
        bg = pbg(parent)
        super().__init__(parent, bg=bg)
        self._h, self._stack, self._cb, self._sp = sc(height), stack, on_change, spaced_text
        self.bar = tk.Canvas(self, height=self._h, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.bar.pack(fill="x")
        self.body = tk.Frame(self, bg=bg)
        self.body.pack(fill="both", expand=True, pady=(sc(gap), 0))
        self.body.columnconfigure(0, weight=1)
        self._items, self.sel, self._hv = [], 0, None
        self._img_o = self._img_s = None
        self.bar.bind("<Configure>", lambda e: self._draw())
        self.bar.bind("<Motion>", self._motion)
        self.bar.bind("<Leave>", lambda e: self._hover(None))
        self.bar.bind("<Button-1>", self._click)

    def add_page(self, text):
        f = tk.Frame(self.body, bg=pbg(self.body))
        self._items.append((text, f))
        if self._stack:
            f.grid(row=0, column=0, sticky="nsew")
        if len(self._items) == 1:
            self.select(0)
        else:
            self._show()
        self._draw()
        return f

    def _show(self):
        for i, (_, f) in enumerate(self._items):
            if self._stack:
                if i == self.sel:
                    f.tkraise()
            elif i == self.sel:
                f.pack(fill="both", expand=True)
            else:
                f.pack_forget()

    def select(self, i):
        if isinstance(i, int) and 0 <= i < len(self._items):
            self.sel = i
            self._show()
            self._draw()
            if self._cb:
                self._cb(i)

    def index(self, _what="current"):
        return self.sel

    def _seg(self, x):
        n = max(len(self._items), 1)
        return min(n - 1, max(0, int(x / max(self.bar.winfo_width(), 1) * n)))

    def _motion(self, e):
        self._hover(self._seg(e.x))

    def _hover(self, i):
        if i != self._hv:
            self._hv = i
            self._draw()

    def _click(self, e):
        self.select(self._seg(e.x))

    def _draw(self):
        try:
            W, H, th = self.bar.winfo_width(), self._h, self.th
            n = len(self._items)
            if W < 10 or n == 0:
                return
            self.bar.delete("all")
            self._o = photo(rr(W, H, H / 2, fill=th.field, outline=th.field_line))
            self.bar.create_image(0, 0, anchor="nw", image=self._o)
            m = sc(3)
            sw = (W - 2 * m) / n
            x0 = m + self.sel * sw
            self._s = photo(rr(int(sw), H - 2 * m, (H - 2 * m) / 2, grad=(th.sel1, th.sel2),
                               outline=lighten(th.sel2, .3)))
            self.bar.create_image(int(x0), m, anchor="nw", image=self._s)
            f = (FONT_NAME, 9, "bold")
            for i, (t, _) in enumerate(self._items):
                col = "#ffffff" if i == self.sel else (th.fg if i == self._hv else th.muted)
                self.bar.create_text(m + sw * i + sw / 2, H / 2, text=spaced(t.strip()) if self._sp else t.strip(),
                                     fill=col, font=f)
        except tk.TclError:
            pass


# ---------------------------------------------------------------- สวิตช์ ON/OFF
class Toggle(tk.Canvas):
    def __init__(self, parent, variable=None, theme=None, command=None):
        self.th = theme or MAIN
        self.var = variable if variable is not None else tk.BooleanVar(value=False)
        self._cmd = command
        w, h = sc(44), sc(24)
        super().__init__(parent, width=w, height=h, bg=pbg(parent), highlightthickness=0, bd=0, cursor="hand2")
        self._tw, self._thh = w, h
        self._item = self.create_image(0, 0, anchor="nw")
        self.bind("<Button-1>", self._click)
        self.var.trace_add("write", lambda *_: self._draw())
        self._draw()

    def _click(self, _e=None):
        self.var.set(not self.var.get())
        if self._cmd:
            self._cmd()

    def _draw(self):
        try:
            self._photo = photo(toggle_img(bool(self.var.get()), self._tw, self._thh, self.th))
            self.itemconfigure(self._item, image=self._photo)
        except tk.TclError:
            pass


def toggle_row(parent, text, variable, theme=None, font=None):
    """สวิตช์ + ข้อความ (คลิกข้อความก็สลับได้) คืนค่า frame"""
    th = theme or MAIN
    f = tk.Frame(parent, bg=pbg(parent))
    t = Toggle(f, variable, th)
    t.pack(side="left")
    lb = tk.Label(f, text=text, bg=pbg(parent), fg=th.fg, font=font or (FONT_NAME, 9), cursor="hand2")
    lb.pack(side="left", padx=(8, 0))
    lb.bind("<Button-1>", lambda e: t._click())
    f.toggle, f.text = t, lb
    return f


# ---------------------------------------------------------------- สไลเดอร์
class GSlider(tk.Canvas):
    """สไลเดอร์ผูกกับ StringVar/DoubleVar (พิมพ์ในช่องตัวเลขก็ขยับตาม)"""

    def __init__(self, parent, variable, lo, hi, step=1, theme=None, width=130, height=22):
        self.th = theme or MAIN
        self.var, self.lo, self.hi, self.step = variable, float(lo), float(hi), float(step)
        self.dec = 0 if step >= 1 else max(0, int(round(-math.log10(step))))
        super().__init__(parent, width=sc(width), height=sc(height), bg=pbg(parent),
                         highlightthickness=0, bd=0, cursor="hand2")
        self._item = self.create_image(0, 0, anchor="nw")
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Button-1>", self._drag)
        self.bind("<B1-Motion>", self._drag)
        variable.trace_add("write", lambda *_: self._draw())

    def _frac(self):
        try:
            v = float(self.var.get())
        except (ValueError, tk.TclError):
            v = self.lo
        return min(1.0, max(0.0, (v - self.lo) / (self.hi - self.lo)))

    def _drag(self, e):
        w = max(self.winfo_width(), 2)
        kr = w and self.winfo_height() / 2
        f = min(1.0, max(0.0, (e.x - kr) / max(w - 2 * kr, 1)))
        v = round((self.lo + f * (self.hi - self.lo)) / self.step) * self.step
        v = min(self.hi, max(self.lo, v))
        self.var.set(f"{v:.{self.dec}f}")

    def _draw(self):
        try:
            w, h = max(self.winfo_width(), 4), max(self.winfo_height(), 4)
            self._photo = photo(slider_img(w, h, self._frac(), self.th))
            self.itemconfigure(self._item, image=self._photo)
        except tk.TclError:
            pass


# ---------------------------------------------------------------- ช่องกรอกมุมมน
class RoundEntry(tk.Canvas):
    """ช่องกรอกมุมมน (ใช้แทน ttk.Entry: get / insert / delete / focus_set / config(show=))
    placeholder = ข้อความจางๆ เมื่อว่างและยังไม่ได้โฟกัส"""

    def __init__(self, parent, theme=None, placeholder="", show="", justify="left", width=None,
                 height=40, font=None, textvariable=None, radius=14, fill=None, spaced_ph=False, pad=14):
        self.th = th = theme or MAIN
        self._fill = fill or th.field
        self._h, self._r, self._pad = sc(height), sc(radius), sc(pad)
        self._just, self._focus = justify, False
        font = font or (FONT_NAME, 10)
        super().__init__(parent, width=sc(width) if width else sc(200), height=self._h, bg=pbg(parent),
                         highlightthickness=0, bd=0)
        self._bgi = self.create_image(0, 0, anchor="nw")
        self.entry = tk.Entry(self, bd=0, relief="flat", highlightthickness=0, bg=self._fill, fg=th.fg,
                              insertbackground=th.fg, font=font, justify=justify, show=show,
                              textvariable=textvariable, selectbackground=th.sel2, selectforeground="#ffffff")
        self._win = self.create_window(self._pad, self._h // 2, window=self.entry, anchor="w")
        self.ph = tk.Label(self, text=spaced(placeholder) if spaced_ph else placeholder, bg=self._fill,
                           fg=th.dim, font=font, cursor="xterm")
        self.ph.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.bind("<Configure>", self._cfg)
        self.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.entry.bind("<FocusIn>", lambda e: self._focused(True), add="+")
        self.entry.bind("<FocusOut>", lambda e: self._focused(False), add="+")
        self.entry.bind("<KeyRelease>", lambda e: self._sync(), add="+")
        if textvariable is not None:
            textvariable.trace_add("write", lambda *_: self._sync())
        self._sync()

    def _cfg(self, e):
        self.itemconfigure(self._win, width=max(10, e.width - 2 * self._pad))
        self._paint()
        self._sync()
        if not self._focus:
            self.entry.xview_moveto(0)

    def _place_ph(self):
        if not self.ph.cget("text"):
            return
        if self._just == "center":
            self.ph.place(relx=.5, rely=.5, anchor="center")
        else:
            self.ph.place(x=self._pad, rely=.5, anchor="w")

    def _paint(self):
        w, h = max(self.winfo_width(), 4), self._h
        th = self.th
        self._photo = photo(rr(w, h, self._r, fill=self._fill,
                               outline=th.field_focus if self._focus else th.field_line,
                               ow=2 if self._focus else 1))
        self.itemconfigure(self._bgi, image=self._photo)

    def _focused(self, f):
        self._focus = f
        self._paint()
        self._sync()

    def _sync(self):
        if self.entry.get() or self._focus:
            self.ph.place_forget()
        else:
            self._place_ph()
            self.ph.lift()

    # --- API เหมือน Entry
    def get(self):
        return self.entry.get()

    def insert(self, i, s):
        self.entry.insert(i, s)
        self._sync()

    def delete(self, a, b=None):
        self.entry.delete(a, b)
        self._sync()

    def focus_set(self):
        self.entry.focus_set()

    def configure(self, cnf=None, **kw):
        if cnf:
            kw.update(cnf)
        if not kw:
            return super().configure()
        for k in ("show", "state"):
            if k in kw:
                self.entry.configure(**{k: kw.pop(k)})
        if kw:
            super().configure(**kw)

    config = configure


# ---------------------------------------------------------------- กล่องเลือก (dropdown) มุมมน
class RoundCombo(tk.Canvas):
    """dropdown มุมมน (วัน/เดือน/ปี) get() / set() / values"""

    def __init__(self, parent, values, theme=None, width=100, height=40, placeholder="", radius=14, font=None):
        self.th = th = theme or MAIN
        self.values, self._val, self._ph = list(values), "", placeholder
        self._h, self._r = sc(height), sc(radius)
        self._font = font or (FONT_NAME, 10)
        self._pop, self._open_state = None, False
        super().__init__(parent, width=sc(width), height=self._h, bg=pbg(parent), highlightthickness=0, bd=0,
                         cursor="hand2")
        self._bgi = self.create_image(0, 0, anchor="nw")
        self._txt = self.create_text(0, 0, anchor="center", font=self._font)
        self._arr = self.create_text(0, 0, text="▾", anchor="e", fill=th.muted, font=(FONT_NAME, 10))
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Button-1>", self._toggle)

    def get(self):
        return self._val

    def set(self, v):
        self._val = v
        self._draw()

    def _draw(self):
        try:
            w, h, th = max(self.winfo_width(), 4), self._h, self.th
            self._photo = photo(rr(w, h, self._r, fill=th.field,
                                   outline=th.field_focus if self._open_state else th.field_line,
                                   ow=2 if self._open_state else 1))
            self.itemconfigure(self._bgi, image=self._photo)
            self.coords(self._txt, w / 2 - sc(6), h / 2)
            self.coords(self._arr, w - sc(10), h / 2)
            self.itemconfigure(self._txt, text=self._val or self._ph, fill=th.fg if self._val else th.dim)
        except tk.TclError:
            pass

    def _toggle(self, _e=None):
        if self._pop:
            self._close()
            return
        th = self.th
        top = self._pop = tk.Toplevel(self)
        top.wm_overrideredirect(True)
        try:
            top.attributes("-topmost", True)
        except tk.TclError:
            pass
        lb = tk.Listbox(top, bd=0, highlightthickness=1, highlightbackground=th.field_focus,
                        highlightcolor=th.field_focus, bg=th.card, fg=th.fg, selectbackground=th.sel2,
                        selectforeground="#ffffff", activestyle="none", font=self._font, exportselection=False,
                        height=min(7, len(self.values)))
        for v in self.values:
            lb.insert("end", v)
        lb.pack(fill="both", expand=True)
        top.update_idletasks()
        w, h = max(self.winfo_width(), sc(80)), top.winfo_reqheight()
        top.geometry(f"{w}x{h}+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height() + 2}")
        if self._val in self.values:
            i = self.values.index(self._val)
            lb.selection_set(i)
            lb.see(i)
        lb.bind("<ButtonRelease-1>", lambda e: self._pick(lb, e))
        lb.bind("<Return>", lambda e: self._pick(lb, e))
        lb.bind("<Escape>", lambda e: self._close())
        lb.bind("<FocusOut>", lambda e: self.after(80, self._close))
        self._open_state = True
        self._draw()
        lb.focus_force()

    def _pick(self, lb, e):
        i = lb.nearest(e.y) if e.type == tk.EventType.ButtonRelease else (lb.curselection() or [0])[0]
        if 0 <= i < len(self.values):
            self._val = self.values[i]
        self._close()

    def _close(self):
        if self._pop:
            try:
                self._pop.destroy()
            except tk.TclError:
                pass
            self._pop = None
        self._open_state = False
        self._draw()
