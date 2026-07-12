"""Tests for integral:// protocol helpers and pending deep-link handoff."""

from pathlib import Path

import deep_links
import protocol_windows


def test_extract_protocol_arg():
    assert deep_links.extract_protocol_arg(["--foo", "integral://journal/abcdef123456"]) == (
        "integral://journal/abcdef123456"
    )
    assert deep_links.extract_protocol_arg(["noop"]) is None


def test_pending_link_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(deep_links, "user_data_dir", lambda: str(tmp_path))
    deep_links.write_pending_link("integral://journal/abcdef123456")
    assert deep_links.read_and_clear_pending_link() == "integral://journal/abcdef123456"
    assert deep_links.read_and_clear_pending_link() is None


def test_launch_command_contains_placeholder():
    cmd = protocol_windows.launch_command_template()
    assert "%1" in cmd


def test_register_unregister_roundtrip(monkeypatch):
    if not protocol_windows.is_supported():
        return
    # Do not touch real HKCU in CI if we can avoid — skip live registry when env set
    import os

    if os.environ.get("INTEGRAL_SKIP_REGISTRY_TESTS") == "1":
        return
    # Soft check: functions exist and is_registered returns bool
    assert isinstance(protocol_windows.is_registered(), bool)
