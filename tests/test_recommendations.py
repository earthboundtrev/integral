from recommendations import build_recommendations
from progression.db import FitnessRepository
from progression.seed_loader import seed_all_fitness
from storage import get_default_categories


def test_recommendations_suggest_unlogged_categories():
    categories = get_default_categories()
    recs = build_recommendations({}, categories)
    assert any("Log today's entry" in rec for rec in recs)


def test_recommendations_include_fitness_available(tmp_path):
    repo = FitnessRepository(str(tmp_path / "fitness.db"))
    seed_all_fitness(repo)
    from progression.engine import record_performance

    record_performance(repo, "cc1_push_01", {"sets": 3, "reps": 50})
    categories = get_default_categories()
    recs = build_recommendations({}, categories, repo)
    assert any("Incline Push-ups" in rec or "Fitness:" in rec for rec in recs)


def test_life_balance_figure_builds():
    import charts

    categories = get_default_categories()
    entries = {
        "2026-06-01": {name: {"rating": 7} for name in categories},
    }
    fig = charts.build_life_balance_figure(entries, categories)
    assert fig is not None
