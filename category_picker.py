"""Category Combobox typeahead (name + short-label match)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from todays_log import CATEGORY_SHORT_LABELS


def filter_category_choices(
    names: list[str],
    query: str,
    *,
    short_labels: dict[str, str] | None = None,
    allow_blank: bool = False,
) -> list[str]:
    """Return domain names matching query (substring on full name or short label)."""
    labels = short_labels if short_labels is not None else CATEGORY_SHORT_LABELS
    base = list(names)
    if allow_blank and "" not in base:
        base = [""] + base

    needle = query.strip().lower()
    if not needle:
        return base

    matched: list[str] = []
    for name in base:
        if name == "":
            continue
        blob = f"{name} {labels.get(name, name)}".lower()
        if needle in blob:
            matched.append(name)
    if allow_blank and "" in base:
        return [""] + matched
    return matched


def resolve_category_name(
    raw: str,
    names: list[str],
    *,
    short_labels: dict[str, str] | None = None,
    allow_blank: bool = False,
) -> str | None:
    """Map typed Combobox text to a canonical category name (or '' if blank allowed)."""
    text = (raw or "").strip()
    if not text:
        return "" if allow_blank else None
    if text in names:
        return text
    labels = short_labels if short_labels is not None else CATEGORY_SHORT_LABELS
    lowered = text.lower()
    for name in names:
        if name.lower() == lowered:
            return name
        if labels.get(name, "").lower() == lowered:
            return name
    return None


def bind_category_typeahead(
    combo: ttk.Combobox,
    names: list[str],
    *,
    allow_blank: bool = False,
    short_labels: dict[str, str] | None = None,
) -> None:
    """Enable typing to narrow Combobox values (leaves state normal, not readonly)."""
    full = filter_category_choices(
        names, "", allow_blank=allow_blank, short_labels=short_labels
    )
    combo.configure(values=full, state="normal")

    def on_key(_event=None) -> None:
        current = combo.get()
        filtered = filter_category_choices(
            names, current, allow_blank=allow_blank, short_labels=short_labels
        )
        combo["values"] = filtered if filtered else full

    combo.bind("<KeyRelease>", on_key)
