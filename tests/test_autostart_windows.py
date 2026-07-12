"""Tests for Windows autostart helpers."""

from __future__ import annotations

import autostart_windows as auto


def test_launch_command_contains_quotes(monkeypatch):
    monkeypatch.setattr(auto, "is_frozen", lambda: True)
    monkeypatch.setattr(auto.sys, "executable", r"C:\Apps\Integral\Integral.exe")
    assert auto.launch_command() == r'"C:\Apps\Integral\Integral.exe"'


def test_launch_command_dev_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(auto, "is_frozen", lambda: False)
    monkeypatch.setattr(auto.sys, "executable", r"C:\Python\python.exe")
    cmd = auto.launch_command()
    assert "python.exe" in cmd
    assert "personal_dev_tracker.py" in cmd


def test_set_enabled_round_trip(monkeypatch):
    store: dict[str, str] = {}

    class FakeKey:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_create_key(_hive, _path):
        return FakeKey()

    def fake_open_key(_hive, _path, *_args, **_kwargs):
        return FakeKey()

    def fake_set(_key, name, _reserved, _type, value):
        store[name] = value

    def fake_query(_key, name):
        if name not in store:
            raise OSError("missing")
        return store[name], 1

    def fake_delete(_key, name):
        store.pop(name, None)

    monkeypatch.setattr(auto, "is_supported", lambda: True)
    monkeypatch.setattr(auto, "launch_command", lambda: '"Integral.exe"')
    import winreg

    monkeypatch.setattr(winreg, "CreateKeyEx", fake_create_key)
    monkeypatch.setattr(winreg, "OpenKey", fake_open_key)
    monkeypatch.setattr(winreg, "SetValueEx", fake_set)
    monkeypatch.setattr(winreg, "QueryValueEx", fake_query)
    monkeypatch.setattr(winreg, "DeleteValue", fake_delete)
    monkeypatch.setattr(winreg, "HKEY_CURRENT_USER", object())
    monkeypatch.setattr(winreg, "KEY_SET_VALUE", 2)
    monkeypatch.setattr(winreg, "REG_SZ", 1)

    auto.set_enabled(True)
    assert store.get(auto.VALUE_NAME) == '"Integral.exe"'
    assert auto.is_enabled() is True
    auto.set_enabled(False)
    assert auto.VALUE_NAME not in store
    assert auto.is_enabled() is False


def test_normalize_adds_residency_flags():
    from notifications import normalize_notification_settings

    settings = normalize_notification_settings({})
    assert settings["notifications"]["minimize_on_close"] is False
    assert settings["notifications"]["start_with_windows"] is False
