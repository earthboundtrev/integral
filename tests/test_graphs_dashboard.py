from graphs import (
    DEFAULT_DASHBOARD_COUNT,
    category_rating_stats,
    normalize_graph_settings,
    resolve_dashboard_categories,
    short_category_label,
)


def test_normalize_graph_settings_defaults():
    assert normalize_graph_settings(None) == {"dashboard_categories": None}
    assert normalize_graph_settings({}) == {"dashboard_categories": None}


def test_normalize_graph_settings_keeps_valid_list():
    settings = normalize_graph_settings({"graphs": {"dashboard_categories": ["Body & Presence", "Money/Freedom"]}})
    assert settings["dashboard_categories"] == ["Body & Presence", "Money/Freedom"]


def test_category_rating_stats():
    entries = {
        "2026-07-01": {"Body & Presence": {"rating": 8}, "Money/Freedom": {"rating": 6}},
        "2026-07-02": {"Body & Presence": {"rating": 7}},
    }
    categories = {"Body & Presence": {}, "Money/Freedom": {}, "Learning & Intellectual Growth": {}}
    stats = category_rating_stats(entries, categories)
    assert stats["Body & Presence"]["count"] == 2
    assert stats["Body & Presence"]["average"] == 7.5
    assert stats["Money/Freedom"]["count"] == 1
    assert stats["Learning & Intellectual Growth"]["count"] == 0


def test_resolve_dashboard_categories_auto_picks_most_logged():
    entries = {
        f"2026-07-{day:02d}": {"Body & Presence": {"rating": 8}}
        for day in range(1, 6)
    }
    entries["2026-07-06"] = {"Money/Freedom": {"rating": 5}}
    categories = {
        "Body & Presence": {},
        "Money/Freedom": {},
        "Home & Environment": {},
    }
    visible, hidden = resolve_dashboard_categories(entries, categories, None, default_count=1)
    assert visible == ["Body & Presence"]
    assert hidden == ["Money/Freedom", "Home & Environment"]


def test_resolve_dashboard_categories_respects_pinned_order():
    categories = {"A": {}, "B": {}, "C": {}}
    visible, hidden = resolve_dashboard_categories({}, categories, ["C", "A"], default_count=8)
    assert visible == ["C", "A"]
    assert hidden == ["B"]


def test_resolve_dashboard_categories_filters_unknown_pins():
    categories = {"A": {}, "B": {}}
    visible, hidden = resolve_dashboard_categories({}, categories, ["A", "Missing", "B"], default_count=8)
    assert visible == ["A", "B"]
    assert hidden == []


def test_short_category_label():
    assert short_category_label("Burnout Prevention & Energy Management") == "Burnout Prevention"
    assert short_category_label("Money/Freedom") == "Money"


def test_default_dashboard_count_is_eight():
    assert DEFAULT_DASHBOARD_COUNT == 8
