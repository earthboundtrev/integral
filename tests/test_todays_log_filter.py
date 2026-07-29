"""Tests for Today's Log domain filter / pins / settings (#54, #56)."""

from todays_log import (
    CATEGORY_SHORT_LABELS,
    MAX_PINNED_DOMAINS,
    apply_todays_log_settings,
    filter_todays_log_categories,
    normalize_todays_log_settings,
    toggle_pinned_domain,
)


NAMES = [
    "Body & Presence",
    "Creative/Mental Work",
    "Money/Freedom",
    "Emotional Wellbeing",
]


def test_filter_empty_query_returns_all_preserving_unlogged_first():
    logged = {"Body & Presence", "Money/Freedom"}
    result = filter_todays_log_categories(NAMES, logged_names=logged)
    assert result == [
        "Creative/Mental Work",
        "Emotional Wellbeing",
        "Body & Presence",
        "Money/Freedom",
    ]


def test_filter_by_short_label_and_full_name():
    assert filter_todays_log_categories(NAMES, query="body") == ["Body & Presence"]
    assert filter_todays_log_categories(NAMES, query="money") == ["Money/Freedom"]
    assert filter_todays_log_categories(NAMES, query="Creative/Mental") == [
        "Creative/Mental Work"
    ]


def test_filter_status_unlogged_and_logged():
    logged = {"Body & Presence"}
    assert filter_todays_log_categories(
        NAMES, status="unlogged", logged_names=logged
    ) == [
        "Creative/Mental Work",
        "Money/Freedom",
        "Emotional Wellbeing",
    ]
    assert filter_todays_log_categories(
        NAMES, status="logged", logged_names=logged
    ) == ["Body & Presence"]


def test_filter_combines_query_and_status():
    logged = {"Body & Presence", "Emotional Wellbeing"}
    assert filter_todays_log_categories(
        NAMES, query="e", status="unlogged", logged_names=logged
    ) == ["Creative/Mental Work", "Money/Freedom"]


def test_filter_unknown_status_falls_back_to_all():
    logged = {"Money/Freedom"}
    result = filter_todays_log_categories(
        NAMES, status="weird", logged_names=logged
    )
    assert result[0] == "Body & Presence"
    assert result[-1] == "Money/Freedom"


def test_filter_uses_custom_short_labels():
    labels = {**CATEGORY_SHORT_LABELS, "Money/Freedom": "Cash"}
    assert filter_todays_log_categories(
        NAMES, query="cash", short_labels=labels
    ) == ["Money/Freedom"]


def test_filter_pins_sort_first_then_unlogged():
    logged = {"Body & Presence"}
    result = filter_todays_log_categories(
        NAMES,
        logged_names=logged,
        pinned_names=["Money/Freedom", "Body & Presence"],
    )
    assert result[:2] == ["Money/Freedom", "Body & Presence"]
    assert result[2:] == ["Creative/Mental Work", "Emotional Wellbeing"]


def test_normalize_and_toggle_pins():
    settings = normalize_todays_log_settings({})
    assert settings["pinned_domains"] == []
    settings = apply_todays_log_settings({}, {"pinned_domains": NAMES + NAMES})
    assert settings["todays_log"]["pinned_domains"] == NAMES[:MAX_PINNED_DOMAINS]

    updated, err = toggle_pinned_domain({}, "Body & Presence", valid_names=set(NAMES))
    assert err is None
    assert updated["todays_log"]["pinned_domains"] == ["Body & Presence"]
    updated, err = toggle_pinned_domain(updated, "Body & Presence", valid_names=set(NAMES))
    assert err is None
    assert updated["todays_log"]["pinned_domains"] == []

    five = [
        "Body & Presence",
        "Creative/Mental Work",
        "Money/Freedom",
        "Emotional Wellbeing",
        "Career & Vocation",
    ]
    filled = apply_todays_log_settings({}, {"pinned_domains": five})
    assert len(filled["todays_log"]["pinned_domains"]) == MAX_PINNED_DOMAINS
    _, err = toggle_pinned_domain(
        filled,
        "Home & Environment",
        valid_names=set(five) | {"Home & Environment"},
    )
    assert err is not None
    assert "up to" in err.lower()

    stale = apply_todays_log_settings(
        {},
        {"pinned_domains": ["Gone Domain", "Body & Presence"]},
    )
    updated, err = toggle_pinned_domain(
        stale,
        "Money/Freedom",
        valid_names={"Body & Presence", "Money/Freedom"},
    )
    assert err is None
    assert updated["todays_log"]["pinned_domains"] == ["Body & Presence", "Money/Freedom"]
