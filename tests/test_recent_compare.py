"""SPEC-212 / #74 — recent exercise session compare helpers."""

from dataclasses import replace
from datetime import date, timedelta

from progression.models import WorkoutSession, WorkoutSet
from progression import recent_compare as rc


def _session(day: str, sid: str = "s1") -> WorkoutSession:
    return WorkoutSession(id=sid, date=day, notes="")


def _set(
    session_id: str,
    exercise_id: str = "ex1",
    *,
    sets=3,
    reps=10,
    hold_seconds=None,
    weight_kg=None,
    form_quality=8,
    set_id: str = "w1",
) -> WorkoutSet:
    return WorkoutSet(
        id=set_id,
        session_id=session_id,
        exercise_id=exercise_id,
        sets=sets,
        reps=reps,
        hold_seconds=hold_seconds,
        weight_kg=weight_kg,
        form_quality=form_quality,
    )


class _FakeRepo:
    def __init__(self, sessions: list[WorkoutSession], sets_by_session: dict[str, list[WorkoutSet]]):
        self._sessions = sessions
        self._sets = sets_by_session

    def list_workout_sessions(self, limit: int = 50) -> list[WorkoutSession]:
        return list(self._sessions)[:limit]

    def list_sessions_for_exercise_between(
        self,
        exercise_id: str,
        *,
        start_date: str,
        end_date: str,
        limit: int = 100,
    ) -> list[WorkoutSession]:
        out = []
        for session in self._sessions:
            if session.date < start_date or session.date > end_date:
                continue
            if any(
                (s.exercise_id or "") == exercise_id
                for s in (self._sets.get(session.id) or [])
            ):
                out.append(session)
            if len(out) >= limit:
                break
        return out

    def list_workout_sets(self, session_id: str) -> list[WorkoutSet]:
        return list(self._sets.get(session_id) or [])


def test_aggregate_sums_sets_and_takes_max_load():
    session = _session("2026-08-01")
    sets = [
        _set("s1", sets=2, reps=8, weight_kg=20, set_id="a"),
        _set("s1", sets=1, reps=10, weight_kg=25, set_id="b"),
    ]
    snap = rc.aggregate_exercise_sets(session, sets)
    assert snap is not None
    assert snap.sets == 3
    assert snap.reps == 10
    assert snap.weight_kg == 25
    assert snap.rows == 2


def test_recent_window_filters_and_orders_newest_first():
    today = date(2026, 8, 3)
    days = {
        "old": (today - timedelta(days=10)).isoformat(),
        "in": (today - timedelta(days=2)).isoformat(),
        "edge": (today - timedelta(days=6)).isoformat(),
        "future": (today + timedelta(days=1)).isoformat(),
    }
    sessions = [
        _session(days["future"], "sf"),
        _session(days["in"], "si"),
        _session(days["edge"], "se"),
        _session(days["old"], "so"),
    ]
    sets = {
        "sf": [_set("sf", set_id="1")],
        "si": [_set("si", set_id="2", weight_kg=30)],
        "se": [_set("se", set_id="3", weight_kg=20)],
        "so": [_set("so", set_id="4", weight_kg=10)],
    }
    # repo returns newest first
    repo = _FakeRepo(sessions, sets)
    snaps = rc.recent_exercise_snapshots(
        repo, "ex1", as_of=today.isoformat(), window_days=7
    )
    assert [s.session_id for s in snaps] == ["si", "se"]
    assert snaps[0].weight_kg == 30


def test_compare_prefers_weight_then_reps_then_hold():
    newer = rc.ExerciseSessionSnapshot("a", "2026-08-02", sets=3, reps=10, weight_kg=40)
    older = rc.ExerciseSessionSnapshot("b", "2026-08-01", sets=3, reps=12, weight_kg=35)
    cue = rc.compare_to_prior(newer, older)
    assert cue.direction == "up"
    assert cue.metric == "weight_kg"
    assert "weight" in cue.label

    flat = rc.compare_to_prior(newer, replace(older, weight_kg=40, reps=10))
    assert flat.direction == "flat"

    weight_tie_reps_up = rc.compare_to_prior(
        rc.ExerciseSessionSnapshot("a", "2026-08-02", reps=12, weight_kg=40),
        rc.ExerciseSessionSnapshot("b", "2026-08-01", reps=10, weight_kg=40),
    )
    assert weight_tie_reps_up.direction == "up"
    assert weight_tie_reps_up.metric == "reps"

    down_reps = rc.compare_to_prior(
        rc.ExerciseSessionSnapshot("a", "2026-08-02", reps=8),
        rc.ExerciseSessionSnapshot("b", "2026-08-01", reps=10),
    )
    assert down_reps.direction == "down"
    assert down_reps.metric == "reps"

    hold_up = rc.compare_to_prior(
        rc.ExerciseSessionSnapshot("a", "2026-08-02", hold_seconds=40),
        rc.ExerciseSessionSnapshot("b", "2026-08-01", hold_seconds=30),
    )
    assert hold_up.direction == "up"
    assert hold_up.metric == "hold_seconds"


def test_progress_cues_align_with_newest_first_window():
    snaps = [
        rc.ExerciseSessionSnapshot("a", "2026-08-03", weight_kg=50),
        rc.ExerciseSessionSnapshot("b", "2026-08-02", weight_kg=45),
        rc.ExerciseSessionSnapshot("c", "2026-08-01", weight_kg=45),
    ]
    cues = rc.progress_cues_for_snapshots(snaps)
    assert cues[0].direction == "up"
    assert cues[1].direction == "flat"
    assert cues[2].direction == "none"
    assert "First" in cues[2].label


def test_format_snapshot_card_scannable():
    text = rc.format_snapshot_card(
        rc.ExerciseSessionSnapshot(
            "a",
            "2026-08-01",
            sets=3,
            reps=10,
            weight_kg=20,
            form_quality=8,
        )
    )
    assert text.startswith("2026-08-01")
    assert "3 sets" in text
    assert "10 reps" in text
    assert "20 kg" in text


def test_invalid_as_of_returns_no_snapshots():
    today = date(2026, 8, 3)
    repo = _FakeRepo(
        [_session(today.isoformat(), "s1")],
        {"s1": [_set("s1")]},
    )
    assert rc.recent_exercise_snapshots(repo, "ex1", as_of="2026-08-") == []
    assert rc.is_valid_as_of("2026-08-03")
    assert not rc.is_valid_as_of("2026-08-")


def test_recent_window_not_starved_by_newer_unrelated_sessions():
    """Backdated as_of still finds in-window sets even with many newer sessions."""
    as_of = date(2026, 7, 1)
    newer = [
        _session((as_of + timedelta(days=i + 1)).isoformat(), f"n{i}")
        for i in range(30)
    ]
    target = _session((as_of - timedelta(days=1)).isoformat(), "target")
    sessions = newer + [target]
    sets = {s.id: [_set(s.id, exercise_id="other", set_id=f"o{s.id}")] for s in newer}
    sets["target"] = [_set("target", exercise_id="ex1", weight_kg=15, set_id="t1")]
    repo = _FakeRepo(sessions, sets)
    snaps = rc.recent_exercise_snapshots(
        repo, "ex1", as_of=as_of.isoformat(), window_days=7
    )
    assert [s.session_id for s in snaps] == ["target"]
