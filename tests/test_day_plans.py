from datetime import date

import day_plans


def test_upsert_and_load_plan():
    plans = day_plans.empty_day_plans()
    plans = day_plans.upsert_plan(
        plans,
        "2099-01-15",
        day_intention="Focus on career and fitness.",
        fitness_note="CC1 Push",
        categories={"Body & Presence": {"notes": "Morning workout", "rating": 7}},
        created_on="2099-01-14",
    )
    loaded = day_plans.plan_for_date(plans, "2099-01-15")
    assert loaded is not None
    assert loaded["day_intention"] == "Focus on career and fitness."
    assert loaded["categories"]["Body & Presence"]["rating"] == 7


def test_compare_plan_aligned_when_logged_meets_targets():
    plan = {
        "day_intention": "Stay steady.",
        "fitness_note": "",
        "categories": {
            "Body & Presence": {"notes": "Workout", "rating": 7},
        },
    }
    actual = {
        "Body & Presence": {"rating": 8, "notes": "Did CC push", "checklist": {}},
    }
    result = day_plans.compare_plan_to_actual(plan, actual, all_categories=["Body & Presence"])
    assert result["has_plan"] is True
    assert result["categories"][0]["status"] == "aligned"


def test_compare_plan_not_logged():
    plan = {
        "day_intention": "",
        "fitness_note": "",
        "categories": {"Money/Freedom": {"notes": "Review budget", "rating": 6}},
    }
    result = day_plans.compare_plan_to_actual(plan, {}, all_categories=["Money/Freedom"])
    assert result["categories"][0]["status"] == "not_logged"


def test_reject_past_plan_dates():
    plans = day_plans.empty_day_plans()
    try:
        day_plans.upsert_plan(plans, "2000-01-01", day_intention="Too late")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_tomorrow_from():
    assert day_plans.tomorrow_from(date(2099, 6, 1)) == date(2099, 6, 2)
