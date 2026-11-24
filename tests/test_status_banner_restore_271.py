"""Persistent restore success banner layout (#271)."""

from __future__ import annotations

import tkinter as tk

from status_banner import StatusBanner


def test_persistent_success_actions_below():
    root = tk.Tk()
    root.withdraw()
    host = tk.Frame(root)
    host.pack(fill=tk.X)
    theme = {
        "success_bg": "#ECFDF5",
        "success": "#047857",
        "card_border": "#D8DCE3",
    }
    banner = StatusBanner(host, theme)
    banner.show_success(
        "Restored. Your previous data was saved to /example/path.zip",
        subtitle="Protected by your vault passphrase.",
        undo_label="Undo restore",
        undo_callback=lambda: None,
        extra_actions=[("Open folder", lambda: None)],
        auto_hide_ms=0,
        actions_below=True,
        closable=True,
    )
    root.update_idletasks()
    assert banner._frame is not None
    assert banner._auto_hide_ms == 0
    root.destroy()