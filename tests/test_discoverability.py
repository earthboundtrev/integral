"""Tests for Go to… filter and category typeahead helpers (#56)."""

from category_picker import filter_category_choices
from goto_ui import filter_goto_destinations


def test_filter_category_choices_matches_short_label_and_blank():
    names = ["Body & Presence", "Money/Freedom"]
    assert filter_category_choices(names, "body") == ["Body & Presence"]
    assert filter_category_choices(names, "money") == ["Money/Freedom"]
    assert filter_category_choices(names, "", allow_blank=True)[0] == ""
    assert filter_category_choices(names, "body", allow_blank=True) == ["", "Body & Presence"]


def test_resolve_category_name_accepts_short_label():
    from category_picker import resolve_category_name

    names = ["Body & Presence", "Money/Freedom"]
    assert resolve_category_name("body", names) == "Body & Presence"
    assert resolve_category_name("nope", names) is None
    assert resolve_category_name("", names, allow_blank=True) == ""


def test_filter_goto_destinations_by_label_and_keywords():
    destinations = [
        {
            "label": "Export",
            "group": "Data",
            "keywords": "export csv",
            "action": lambda: None,
        },
        {
            "label": "Log Body",
            "group": "Log",
            "keywords": "Body & Presence body domain",
            "action": lambda: None,
        },
        {
            "label": "Journal",
            "group": "Nav",
            "keywords": "journal write",
            "action": lambda: None,
        },
    ]
    assert [d["label"] for d in filter_goto_destinations(destinations, "")] == [
        "Export",
        "Log Body",
        "Journal",
    ]
    assert [d["label"] for d in filter_goto_destinations(destinations, "csv")] == ["Export"]
    assert [d["label"] for d in filter_goto_destinations(destinations, "body")] == ["Log Body"]
