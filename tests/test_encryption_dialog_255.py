"""Security dialog encryption saves (#255)."""

from __future__ import annotations

import tkinter as tk
from unittest.mock import patch

import pytest

pytest.importorskip("cryptography", reason="cryptography required for encryption dialog tests")

import paths
import personal_dev_tracker
from integral_dialogs import show_security_dialog
from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file
from vault import is_encrypted_file, load_data_file


@pytest.fixture(autouse=True)
def _sync_tracker_data_file(monkeypatch):
    monkeypatch.setattr(personal_dev_tracker, "DATA_FILE", paths.data_file())


@pytest.fixture
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


def _walk_widgets(parent: tk.Misc):
    yield parent
    for child in parent.winfo_children():
        yield from _walk_widgets(child)


def _click_button(root: tk.Misc, label_fragment: str) -> None:
    for widget in _walk_widgets(root):
        if widget.winfo_class() != "TButton":
            continue
        try:
            if label_fragment in str(widget.cget("text")):
                widget.invoke()
                return
        except tk.TclError:
            continue
    raise AssertionError(f"button containing {label_fragment!r} not found")


def _messagebox_calls(request: pytest.FixtureRequest) -> list[tuple[str, tuple, dict]]:
    return getattr(request.node, "_integral_messagebox_calls", [])


def _had_showinfo_title(request: pytest.FixtureRequest, title: str) -> bool:
    for name, args, _kwargs in _messagebox_calls(request):
        if name == "showinfo" and args and args[0] == title:
            return True
    return False


def _had_showerror(request: pytest.FixtureRequest) -> bool:
    return any(name == "showerror" for name, _args, _kwargs in _messagebox_calls(request))


def _load_tracker_encrypted(tk_root: tk.Tk, passphrase: str):
    payload = _minimal_v2_payload()
    payload["settings"]["encryption_enabled"] = True
    _seed_data_file(payload, encrypted=True, passphrase=passphrase)

    def _unlock(tracker):
        tracker.vault_passphrase = passphrase
        return True

    with patch("personal_dev_tracker.prompt_vault_unlock", side_effect=_unlock):
        return personal_dev_tracker.PersonalDevelopmentTracker(tk_root)


def test_enable_failure_shows_error_and_rolls_back(tk_root, request):
    data_path = _seed_data_file(_minimal_v2_payload())
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    plain_before = open(data_path, encoding="utf-8").read()

    with patch(
        "integral_dialogs.simpledialog.askstring",
        side_effect=["session-pass", "session-pass"],
    ):
        with patch("personal_dev_tracker.save_data_file", side_effect=OSError("save blocked")):
            show_security_dialog(tracker)
            _click_button(tk_root, "Enable encryption")

    assert not tracker.settings.get("encryption_enabled")
    assert tracker.vault_passphrase is None
    assert not is_encrypted_file(data_path)
    assert open(data_path, encoding="utf-8").read() == plain_before
    assert _had_showerror(request)
    assert not _had_showinfo_title(request, "Enabled")


def test_disable_failure_shows_error_and_rolls_back(tk_root, request):
    passphrase = "keep-me"
    data_path = paths.data_file()
    tracker = _load_tracker_encrypted(tk_root, passphrase)
    session_pass = tracker.vault_passphrase
    encrypted_before = open(data_path, encoding="utf-8").read()

    with patch("integral_dialogs.simpledialog.askstring", return_value="typed-unlock-only"):
        with patch("personal_dev_tracker.save_data_file", side_effect=OSError("save blocked")):
            show_security_dialog(tracker)
            _click_button(tk_root, "Disable encryption")

    assert tracker.settings.get("encryption_enabled") is True
    assert tracker.vault_passphrase == session_pass
    assert open(data_path, encoding="utf-8").read() == encrypted_before
    assert _had_showerror(request)
    assert not _had_showinfo_title(request, "Disabled")


def test_change_passphrase_failure_restores_old_passphrase(tk_root, request):
    old_pass = "old-pass"
    tracker = _load_tracker_encrypted(tk_root, old_pass)
    data_path = paths.data_file()
    tracker.vault_passphrase = old_pass

    with patch(
        "integral_dialogs.simpledialog.askstring",
        side_effect=[old_pass, "new-pass", "new-pass"],
    ):
        with patch("personal_dev_tracker.save_data_file", side_effect=OSError("save blocked")):
            show_security_dialog(tracker)
            _click_button(tk_root, "Change passphrase")

    assert tracker.vault_passphrase == old_pass
    load_data_file(data_path, old_pass)
    assert _had_showerror(request)
    assert not _had_showinfo_title(request, "Updated")


def test_enable_success_persists_before_confirmation(tk_root, request):
    data_path = _seed_data_file(_minimal_v2_payload())
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    passphrase = "persist-pass"

    with patch(
        "integral_dialogs.simpledialog.askstring",
        side_effect=[passphrase, passphrase],
    ):
        show_security_dialog(tracker)
        _click_button(tk_root, "Enable encryption")

    assert tracker.settings.get("encryption_enabled") is True
    assert is_encrypted_file(data_path)
    load_data_file(data_path, passphrase)
    assert _had_showinfo_title(request, "Enabled")


def test_change_passphrase_success_persists_before_confirmation(tk_root, request):
    old_pass = "old-pass"
    new_pass = "new-pass"
    tracker = _load_tracker_encrypted(tk_root, old_pass)
    data_path = paths.data_file()
    tracker.vault_passphrase = old_pass

    with patch(
        "integral_dialogs.simpledialog.askstring",
        side_effect=[old_pass, new_pass, new_pass],
    ):
        show_security_dialog(tracker)
        _click_button(tk_root, "Change passphrase")

    assert tracker.vault_passphrase == new_pass
    load_data_file(data_path, new_pass)
    with pytest.raises(Exception):
        load_data_file(data_path, old_pass)
    assert _had_showinfo_title(request, "Updated")
