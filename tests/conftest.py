"""Shared pytest hooks — keep Tk modal dialogs from blocking headless runs (#173/#174)."""

from __future__ import annotations

import tkinter as tk

import pytest

import paths


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
    """Never touch the developer's real ~/.integral during pytest."""
    home = tmp_path / "integral-user-data"
    home.mkdir()
    monkeypatch.setattr(paths, "user_data_dir", lambda: str(home))


@pytest.fixture(autouse=True)
def _stub_modal_messageboxes(monkeypatch):
    import tkinter.messagebox as messagebox

    monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr(messagebox, "showwarning", lambda *args, **kwargs: None)
    monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: None)
    monkeypatch.setattr(messagebox, "askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr(messagebox, "askokcancel", lambda *args, **kwargs: True)
    monkeypatch.setattr(messagebox, "askretrycancel", lambda *args, **kwargs: True)
