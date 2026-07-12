"""Tests for creative writing document windows (SPEC-303)."""

from __future__ import annotations

import creative_projects as cp
import creative_ui as cui


def test_count_words_and_chars_empty():
    assert cui.count_words_and_chars("") == (0, 0)
    assert cui.count_words_and_chars("   ") == (0, 3)


def test_count_words_and_chars_basic():
    words, chars = cui.count_words_and_chars("one two three")
    assert words == 3
    assert chars == 13


def test_format_doc_status():
    text = cui.format_doc_status("Saved", "hello world")
    assert text.startswith("Saved ·")
    assert "2 words" in text
    assert "11 characters" in text


def test_role_label():
    assert cui.role_label(cp.DOC_INSPIRATION) == "Inspiration"
    assert cui.role_label(cp.DOC_MANUSCRIPT) == "Manuscript"


def test_document_window_key():
    assert cui.document_window_key("abc", cp.DOC_INSPIRATION) == ("abc", cp.DOC_INSPIRATION)


def test_flush_open_document_windows_empty():
    cui._open_doc_windows.clear()
    assert cui.flush_open_document_windows() == 0
    assert cui.open_document_windows_count() == 0


def test_flush_saves_dirty_entries():
    cui._open_doc_windows.clear()
    calls = {"n": 0}

    def save() -> None:
        calls["n"] += 1
        dirty["value"] = False

    dirty = {"value": True}
    cui._open_doc_windows[("p1", cp.DOC_MANUSCRIPT)] = {
        "window": None,
        "dirty": dirty,
        "save": save,
    }
    assert cui.flush_open_document_windows() == 1
    assert calls["n"] == 1
    dirty["value"] = False
    assert cui.flush_open_document_windows() == 0
    cui._open_doc_windows.clear()
