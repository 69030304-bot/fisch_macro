"""
tests/conftest.py - Pytest fixtures and environment configuration.

Provides a persistent session-level Tkinter root to prevent
multiple Tcl interpreter initialization/destruction crashes (SIGABRT)
on Linux X11/Xvfb runners.
"""
import pytest
import tkinter as tk


@pytest.fixture(scope="session")
def tk_root():
    """
    Session-level headless Tkinter root instance.
    Guarantees a single Tcl/Tk interpreter per process.
    """
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception:
        root = None
    yield root
    if root is not None:
        try:
            root.destroy()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def clean_tk_window(tk_root):
    """
    Ensures any leftover child widgets or Toplevel windows are destroyed
    between test executions while keeping the root interpreter intact.
    """
    yield
    if tk_root is not None:
        try:
            for child in list(tk_root.winfo_children()):
                try:
                    child.destroy()
                except Exception:
                    pass
            tk_root.update_idletasks()
        except Exception:
            pass
