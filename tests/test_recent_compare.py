"""SPEC-212 / SPEC-213 — recent exercise session + volume compare helpers."""

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

    def list_sessions_for_exercise_upto(
        self,
        exercise_id: str,
        *,
        end_date: str,
        limit: int = 40,
    ) -> list[WorkoutSession]:
        out = []
        for session in self._sessions:
            if session.date > end_date:
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


def test_volume_1x11_reps():
    score, kind = rc.compute_volume_score(sets=1, reps=11)
    assert score == 11
    assert kind == "reps"


def test_volume_weighted():
    score, kind = rc.compute_volume_score(sets=3, reps=10, weight_kg=20)
    assert score == 600
    assert kind == "weighted"


def test_aggregate_sums_volume_across_rows():
    session = _session("2026-08-01")
    sets = [
        _set("s1", sets=2, reps=8, weight_kg=20, set_id="a"),
        _set("s1", sets=1, reps=10, weight_kg=25, set_id="b"),
    ]
    snap = rc.aggregate_exercise_sets(session, sets)
    assert snap is not None
    assert snap.sets == 3
    # 20*2*8 + 25*1*10 = 320 + 250
    assert snap.volume == 570
    assert snap.volume_kind == "weighted"


def test_compare_volume_up_vs_last():
    draft = rc.snapshot_from_draft(sets=1, reps=11)
    prior = rc.snapshot_from_draft(sets=1, reps=10, session_id="old", date_str="2026-07-01")
    cue = rc.compare_volume_to_prior(draft, prior)
    assert cue.direction == "up"
    assert cue.metric == "volume"
    assert "↑" in cue.label


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
    repo = _FakeRepo(sessions, sets)
    snaps = rc.recent_exercise_snapshots(
        repo, "ex1", as_of=today.isoformat(), window_days=7
    )
    assert [s.session_id for s in snaps] == ["si", "se"]
    assert snaps[0].weight_kg == 30


def test_history_includes_older_than_week():
    today = date(2026, 8, 3)
    old = (today - timedelta(days=30)).isoformat()
    sessions = [
        _session(today.isoformat(), "new"),
        _session(old, "old"),
    ]
    sets = {
        "new": [_set("new", sets=1, reps=10, set_id="n")],
        "old": [_set("old", sets=1, reps=8, set_id="o")],
    }
    repo = _FakeRepo(sessions, sets)
    hist = rc.exercise_history_snapshots(repo, "ex1", as_of=today.isoformat())
    assert [s.session_id for s in hist] == ["new", "old"]
    week = rc.recent_exercise_snapshots(
        repo, "ex1", as_of=today.isoformat(), window_days=7
    )
    assert [s.session_id for s in week] == ["new"]


def test_compare_prefers_volume_over_raw_metrics():
    newer = rc.ExerciseSessionSnapshot(
        "a", "2026-08-02", sets=1, reps=12, weight_kg=40, volume=480, volume_kind="weighted"
    )
    older = rc.ExerciseSessionSnapshot(
        "b", "2026-08-01", sets=1, reps=10, weight_kg=40, volume=400, volume_kind="weighted"
    )
    cue = rc.compare_to_prior(newer, older)
    assert cue.direction == "up"
    assert cue.metric == "volume"


def test_progress_cues_align_with_newest_first_window():
    snaps = [
        rc.ExerciseSessionSnapshot(
            "a", "2026-08-03", volume=50, volume_kind="reps", reps=50, sets=1
        ),
        rc.ExerciseSessionSnapshot(
            "b", "2026-08-02", volume=45, volume_kind="reps", reps=45, sets=1
        ),
        rc.ExerciseSessionSnapshot(
            "c", "2026-08-01", volume=45, volume_kind="reps", reps=45, sets=1
        ),
    ]
    cues = rc.progress_cues_for_snapshots(snaps)
    assert cues[0].direction == "up"
    assert cues[1].direction == "flat"
    assert cues[2].direction == "none"


def test_format_snapshot_card_includes_volume():
    text = rc.format_snapshot_card(
        rc.snapshot_from_draft(sets=1, reps=11, date_str="2026-08-01")
    )
    assert text.startswith("2026-08-01")
    assert "11 rep·vol" in text


def test_invalid_as_of_returns_no_snapshots():
    today = date(2026, 8, 3)
    repo = _FakeRepo(
        [_session(today.isoformat(), "s1")],
        {"s1": [_set("s1")]},
    )
    assert rc.recent_exercise_snapshots(repo, "ex1", as_of="2026-08-") == []
    assert rc.exercise_history_snapshots(repo, "ex1", as_of="2026-08-") == []
    assert rc.is_valid_as_of("2026-08-03")
    assert not rc.is_valid_as_of("2026-08-")


def test_hold_preferred_over_default_reps():
    score, kind = rc.compute_volume_score(sets=1, reps=10, hold_seconds=40)
    assert kind == "hold"
    assert score == 40
    body = rc.snapshot_from_draft(sets=1, reps=11)
    weighted = rc.snapshot_from_draft(sets=1, reps=10, weight_kg=20)
    cue = rc.compare_volume_to_prior(weighted, body)
    assert cue.direction == "none"
    mixed = rc.compare_to_prior(weighted, body)
    assert mixed.direction == "none"
    assert "kinds differ" in mixed.label.lower()


def test_snapshot_from_pending_items_sums_queue():
    snap = rc.snapshot_from_pending_items(
        [
            {"sets": 1, "reps": 10},
            {"sets": 1, "reps": 5},
        ]
    )
    assert snap.volume == 15
    assert snap.volume_kind == "reps"


def test_recent_window_not_starved_by_newer_unrelated_sessions():
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
