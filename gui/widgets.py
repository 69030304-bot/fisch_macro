"""
gui/widgets.py - Specialized compound UI widgets and tooltip helpers for Fisch Macro.

Owned by Member 69030208 (นายฤทธิพร วงค์ป้อม — GUI & DB Integration)
in collaboration with Member 69030377 (นางสาวพิชชาภา ภูววิไลเมธา — UX/UI Design).
"""
import sys
import tkinter as tk
from datetime import date
from typing import Optional

import ui_kit as ui

FONT_NAME = "Segoe UI" if sys.platform == "win32" else "Tahoma"
FONT = (FONT_NAME, 9)


class Tip:
    """Non-intrusive tooltip popup displayed on widget hover."""

    def __init__(self, widget: tk.Widget, text: str, theme: Optional[ui.Theme] = None):
        self.w = widget
        self.text = text
        self.tw: Optional[tk.Toplevel] = None
        self.th = theme or ui.MAIN
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def show(self, _event=None) -> None:
        if self.tw:
            return
        try:
            x = self.w.winfo_rootx() + 14
            y = self.w.winfo_rooty() + self.w.winfo_height() + 4
            self.tw = tw = tk.Toplevel(self.w)
            tw.wm_overrideredirect(True)
            tw.attributes("-topmost", True)
            tw.wm_geometry(f"+{x}+{y}")
            tk.Label(
                tw,
                text=self.text,
                bg=self.th.tip_bg,
                fg=self.th.fg,
                justify="left",
                font=FONT,
                padx=10,
                pady=6,
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=self.th.tip_line,
                wraplength=300,
            ).pack()
        except tk.TclError:
            pass

    def hide(self, _event=None) -> None:
        if self.tw:
            try:
                self.tw.destroy()
            except tk.TclError:
                pass
            self.tw = None


class DateField(tk.Frame):
    """Compound rounded dropdown selector for Date of Birth (Day / Month / Year)."""

    MONTHS = [
        "Jan (01)", "Feb (02)", "Mar (03)", "Apr (04)",
        "May (05)", "Jun (06)", "Jul (07)", "Aug (08)",
        "Sep (09)", "Oct (10)", "Nov (11)", "Dec (12)"
    ]

    def __init__(self, parent: tk.Widget, theme: Optional[ui.Theme] = None):
        super().__init__(parent, bg=ui.pbg(parent))
        th = theme or ui.LOGIN
        this_year = date.today().year
        self.d = ui.RoundCombo(self, [f"{i:02d}" for i in range(1, 32)], th, width=84, placeholder="DD")
        self.m = ui.RoundCombo(self, self.MONTHS, th, width=124, placeholder="MM")
        self.y = ui.RoundCombo(
            self,
            [str(i) for i in range(this_year, 1949, -1)],
            th,
            width=104,
            placeholder="YYYY",
        )
        for i, w in enumerate((self.d, self.m, self.y)):
            w.pack(side="left", expand=True, fill="x", padx=(0 if i == 0 else 8, 0))

    def get(self) -> Optional[str]:
        """Validate and return ISO format 'YYYY-MM-DD', or None if invalid."""
        try:
            day_str = self.d.get().strip()
            month_str = self.m.get().strip()
            year_str = self.y.get().strip()
            if not day_str or not month_str or not year_str:
                return None
            m_idx = self.MONTHS.index(month_str) + 1
            d = date(int(year_str), m_idx, int(day_str))
            return d.isoformat()
        except (ValueError, TypeError):
            return None

    def clear(self) -> None:
        """Reset dropdown selections."""
        for w in (self.d, self.m, self.y):
            w.set("")
