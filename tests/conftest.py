"""Shared pytest hooks — keep Tk modal dialogs from blocking headless runs (#173/#174)."""

from __future__ import annotations

import sys
import tkinter as tk

import pytest


def pump_tk(root: tk.Misc, steps: int = 25) -> None:
    """Process pending Tk events (chunked dashboard builds use after_idle)."""
    for _ in range(steps):
        try:
            root.update_idletasks()
            root.update()
        except tk.TclError:
            break


@pytest.fixture(autouse=True)
def _isolated_user_data_home(tmp_path, monkeypatch):
    """Never touch the developer's real home directory during pytest."""
    home = tmp_path / "pytest-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    if sys.platform == "win32":
        appdata = tmp_path / "AppData" / "Roaming"
        appdata.mkdir(parents=True)
        monkeypatch.setenv("APPDATA", str(appdata))


@pytest.fixture(autouse=True)
def _stub_modal_messageboxes(monkeypatch):
    import tkinter.messagebox as messagebox

    monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr(messagebox, "showwarning", lambda *args, **kwargs: None)
    monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: None)
    monkeypatch.setattr(messagebox, "askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr(messagebox, "askokcancel", lambda *args, **kwargs: True)
    monkeypatch.setattr(messagebox, "askretrycancel", lambda *args, **kwargs: True)
