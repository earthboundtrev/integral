"""Security dialog encryption saves (#255)."""

from __future__ import annotations

import os
import sys
import threading
import time
import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("cryptography", reason="cryptography required for encryption dialog tests")

import paths
import personal_dev_tracker
import vault
from integral_dialogs import show_security_dialog
from tests.conftest import pump_tk, pump_tk_until
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


def test_disable_final_replace_failure_restores_data_file(tk_root, request):
    passphrase = "keep-me"
    data_path = paths.data_file()
    tracker = _load_tracker_encrypted(tk_root, passphrase)
    before_bytes = open(data_path, "rb").read()
    real_replace = os.replace

    def replacing(src, dst):
        if str(src).endswith(".tmp"):
            raise OSError("final replace failed")
        return real_replace(src, dst)

    with patch("vault.os.replace", side_effect=replacing):
        with patch("integral_dialogs.simpledialog.askstring", return_value=passphrase):
            show_security_dialog(tracker)
            _click_button(tk_root, "Disable encryption")

    tmp_path = f"{data_path}.tmp"
    assert not os.path.exists(tmp_path)
    assert open(data_path, "rb").read() == before_bytes
    assert _had_showerror(request)
    assert not _had_showinfo_title(request, "Disabled")


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


def test_enable_confirm_cancel_is_not_mismatch(tk_root, request):
    _seed_data_file(_minimal_v2_payload())
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)

    with patch(
        "integral_dialogs.simpledialog.askstring",
        side_effect=["chosen-pass", None],
    ):
        show_security_dialog(tracker)
        _click_button(tk_root, "Enable encryption")

    assert not tracker.settings.get("encryption_enabled")
    assert not any(
        name == "showerror" and args and args[0] == "Mismatch"
        for name, args, _kwargs in _messagebox_calls(request)
    )


def test_enable_then_disable_reopen_does_not_prompt_unlock(tk_root):
    passphrase = "round-trip"
    data_path = _seed_data_file(_minimal_v2_payload())
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)

    with patch(
        "integral_dialogs.simpledialog.askstring",
        side_effect=[passphrase, passphrase],
    ):
        show_security_dialog(tracker)
        _click_button(tk_root, "Enable encryption")

    tracker = _load_tracker_encrypted(tk_root, passphrase)
    tracker.vault_passphrase = passphrase
    with patch("integral_dialogs.simpledialog.askstring", return_value=passphrase):
        show_security_dialog(tracker)
        _click_button(tk_root, "Disable encryption")

    assert not is_encrypted_file(data_path)
    bak_path = f"{data_path}.bak"
    assert not os.path.exists(bak_path) or not is_encrypted_file(bak_path)

    tk_root.destroy()
    root2 = tk.Tk()
    root2.withdraw()
    try:
        unlock = MagicMock(side_effect=AssertionError("unlock prompt must not run"))
        with patch("personal_dev_tracker.prompt_vault_unlock", unlock):
            personal_dev_tracker.PersonalDevelopmentTracker(root2)
        unlock.assert_not_called()
    finally:
        try:
            root2.destroy()
        except tk.TclError:
            pass


def test_enable_waits_for_slow_in_flight_save(tk_root, request):
    data_path = _seed_data_file(_minimal_v2_payload())
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    passphrase = "after-async"

    real_save = vault.save_data_file

    def slow_save(path, payload, *, encrypted, passphrase):
        time.sleep(4)
        return real_save(path, payload, encrypted=encrypted, passphrase=passphrase)

    tracker.entries["2026-11-11"] = {"Body & Presence": {"rating": 3}}
    windows_exe_ci = (
        sys.platform == "win32" and os.environ.get("INTEGRAL_WINDOWS_EXE_CI") == "1"
    )
    if windows_exe_ci:
        # GHA windows-latest: vault I/O in a daemon thread while Tk pumps can fatal-exit
        # the process (0x80000003). Simulate in-flight save on the UI thread instead.
        tracker._save_idle_event.clear()
        tracker._save_write_in_progress = True

        def _release_in_progress() -> None:
            tracker._save_write_in_progress = False
            tracker._save_idle_event.set()

        tk_root.after(3000, _release_in_progress)
        pump_tk(tk_root, steps=5)
        assert tracker._save_write_in_progress
    else:
        with patch("personal_dev_tracker.save_data_file", side_effect=slow_save):
            tracker.save_data(flush=False)
        assert pump_tk_until(tk_root, lambda: tracker._save_write_in_progress, timeout_s=2.0)

    with patch(
        "integral_dialogs.simpledialog.askstring",
        side_effect=[passphrase, passphrase],
    ):
        show_security_dialog(tracker)
        _click_button(tk_root, "Enable encryption")

    assert tracker.settings.get("encryption_enabled") is True
    assert _had_showinfo_title(request, "Enabled")
    assert not tracker._save_write_in_progress
    tracker.save_data(flush=True)
    pump_tk(tk_root, steps=3)
    assert not tracker._save_write_in_progress


def test_double_submit_encryption_ignored(tk_root, request):
    data_path = _seed_data_file(_minimal_v2_payload())
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    passphrase = "once-only"
    flush_calls = {"n": 0}
    real_save = personal_dev_tracker.PersonalDevelopmentTracker.save_data

    def counting_save(self, *args, **kwargs):
        if kwargs.get("flush"):
            flush_calls["n"] += 1
        return real_save(self, *args, **kwargs)

    show_security_dialog(tracker)
    btn = next(
        w
        for w in _walk_widgets(tk_root)
        if w.winfo_class() == "TButton" and "Enable encryption" in str(w.cget("text"))
    )
    ask_values = [passphrase, passphrase]

    def askstring(*_args, **_kwargs):
        value = ask_values.pop(0)
        tk_root.after(1, btn.invoke)
        return value

    with patch("integral_dialogs.simpledialog.askstring", side_effect=askstring):
        with patch.object(personal_dev_tracker.PersonalDevelopmentTracker, "save_data", counting_save):
            btn.invoke()
            pump_tk(tk_root, steps=10)

    assert is_encrypted_file(data_path)
    assert flush_calls["n"] == 1
