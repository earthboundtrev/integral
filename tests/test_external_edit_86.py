"""Tests for external editor helper (#86 Grammarly / Tk limitation)."""

from __future__ import annotations

from pathlib import Path

import external_edit


def test_write_and_read_temp_text_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = external_edit.write_temp_text("Hello from Integral\nLine 2", suffix=".txt")
    assert Path(path).is_file()
    assert external_edit.read_text_file(path) == "Hello from Integral\nLine 2"
    Path(path).unlink(missing_ok=True)


def test_open_path_requires_existing_file(tmp_path: Path):
    missing = tmp_path / "nope.txt"
    try:
        external_edit.open_path_with_default_app(str(missing))
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass


def test_grammarly_blurb_mentions_tkinter():
    assert "Tkinter" in external_edit.GRAMMARLY_LIMITATION_BLURB
    assert "Grammarly" in external_edit.GRAMMARLY_LIMITATION_BLURB
