"""Tests for Today's Log domain filter / sort helpers (#54)."""

from personal_dev_tracker import CATEGORY_SHORT_LABELS, filter_todays_log_categories


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
