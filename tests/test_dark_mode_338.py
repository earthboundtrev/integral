"""TCheckbutton / TRadiobutton label and indicator maps (#338)."""

from __future__ import annotations

import tkinter as tk

import pytest
from tkinter import ttk

from theme import LIGHT, apply_theme, get_theme, is_forbidden_chrome_background
from tests.conftest import create_tk_root

# Clam defaults that must not appear on checkbox/radio labels (#338).
_CLAM_FORBIDDEN_LABEL_BG = frozenset(
    {"#eeebe7", "#EEEbe7", "#dcdad5", "#DCDAD5", "#ececec", "#ECECEC", "#d9d9d9", "#D9D9D9"}
)

_CHECKABLE_STYLES = ("TCheckbutton", "TRadiobutton")

_ENABLED_LABEL_STATES: tuple[tuple[str, ...], ...] = (
    (),
    ("selected",),
    ("active",),
    ("active", "selected"),
    ("pressed",),
    ("pressed", "selected"),
    ("focus",),
    ("focus", "selected"),
)

_DISABLED_LABEL_STATES: tuple[tuple[str, ...], ...] = (
    ("disabled",),
    ("disabled", "selected"),
)

_INDICATOR_STATES: tuple[tuple[str, ...], ...] = (
    (),
    ("active",),
    ("selected",),
    ("pressed",),
    ("disabled",),
    ("active", "selected"),
    ("pressed", "selected"),
    ("focus", "selected"),
    ("disabled", "selected"),
)


def _style_map_entries(root: tk.Misc, style_name: str, option: str) -> list[tuple[tuple[str, ...], str]]:
    """Return (state_tuple, color) pairs from the live ttk style map."""
    raw = root.tk.call("ttk::style", "map", style_name, f"-{option}")
    if not raw:
        return []
    out: list[tuple[tuple[str, ...], str]] = []
    i = 0
    n = len(raw)
    while i < n:
        spec = raw[i]
        color = str(raw[i + 1])
        states = getattr(spec, "states", None)
        if states:
            state = tuple(str(s) for s in states)
        else:
            text = str(spec).strip()
            state = tuple(text.split()) if text else ()
        out.append((state, color))
        i += 2
    return out


def _map_values_for_state(
    entries: list[tuple[tuple[str, ...], str]],
    state: tuple[str, ...],
) -> list[str]:
    """Colors from map entries whose state set matches ``state`` (order preserved)."""
    want = frozenset(state)
    return [color for entry_state, color in entries if frozenset(entry_state) == want]


@pytest.fixture
def tk_root():
    root = create_tk_root()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


@pytest.mark.parametrize("dark", [False, True], ids=["light", "dark"])
@pytest.mark.parametrize("widget_style", _CHECKABLE_STYLES)
def test_label_stays_on_theme_tokens_in_every_state(tk_root, dark: bool, widget_style: str) -> None:
    theme = get_theme(dark)
    apply_theme(tk_root, theme)
    style = ttk.Style(tk_root)
    for state in _ENABLED_LABEL_STATES:
        bg = style.lookup(widget_style, "background", state)
        fg = style.lookup(widget_style, "foreground", state)
        assert bg == theme["bg"], (widget_style, state, bg)
        assert fg == theme["fg"], (widget_style, state, fg)
        assert bg not in _CLAM_FORBIDDEN_LABEL_BG, (widget_style, state, bg)
        assert not is_forbidden_chrome_background(bg), (widget_style, state, bg)


@pytest.mark.parametrize("dark", [False, True], ids=["light", "dark"])
@pytest.mark.parametrize("widget_style", _CHECKABLE_STYLES)
def test_disabled_label_uses_disabled_fg(tk_root, dark: bool, widget_style: str) -> None:
    theme = get_theme(dark)
    apply_theme(tk_root, theme)
    style = ttk.Style(tk_root)
    for state in _DISABLED_LABEL_STATES:
        assert style.lookup(widget_style, "background", state) == theme["bg"]
        assert style.lookup(widget_style, "foreground", state) == theme["disabled"]
        assert style.lookup(widget_style, "indicatorbackground", state) == theme["surface_alt"]
        assert style.lookup(widget_style, "indicatorforeground", state) == theme["disabled"]
        assert style.lookup(widget_style, "upperbordercolor", state) == theme["disabled"]


@pytest.mark.parametrize("dark", [False, True], ids=["light", "dark"])
@pytest.mark.parametrize("widget_style", _CHECKABLE_STYLES)
def test_style_map_covers_label_and_indicator_options(tk_root, dark: bool, widget_style: str) -> None:
    theme = get_theme(dark)
    apply_theme(tk_root, theme)
    for option in (
        "background",
        "foreground",
        "indicatorbackground",
        "indicatorforeground",
        "upperbordercolor",
        "lowerbordercolor",
        "focuscolor",
    ):
        entries = _style_map_entries(tk_root, widget_style, option)
        assert entries, f"{widget_style} missing style.map for -{option}"
    style = ttk.Style(tk_root)
    assert style.lookup(widget_style, "focuscolor") == theme["accent"]
    focus_hits = _map_values_for_state(
        _style_map_entries(tk_root, widget_style, "focuscolor"),
        ("focus",),
    )
    assert theme["accent"] in focus_hits


@pytest.mark.parametrize("dark", [False, True], ids=["light", "dark"])
@pytest.mark.parametrize("widget_style", _CHECKABLE_STYLES)
def test_indicator_map_not_clam_defaults(tk_root, dark: bool, widget_style: str) -> None:
    """Assert painted map targets, not only configure/lookup resting values (#338)."""
    theme = get_theme(dark)
    apply_theme(tk_root, theme)
    style = ttk.Style(tk_root)
    ind_bg_map = _style_map_entries(tk_root, widget_style, "indicatorbackground")
    selected_fill = [
        color
        for state, color in ind_bg_map
        if "selected" in state and "disabled" not in state
    ]
    assert theme["accent"] in selected_fill

    for _state, color in ind_bg_map:
        assert color.lower() != "#5895bc", (widget_style, color)
    assert style.lookup(widget_style, "indicatorbackground", ()) == theme["surface"]

    assert style.lookup(widget_style, "upperbordercolor", ("active",)) == theme["accent"]
    assert style.lookup(widget_style, "indicatorbackground", ("pressed",)) == theme["surface_alt"]
    assert style.lookup(widget_style, "indicatorforeground", ("selected",)) == theme["on_accent"]