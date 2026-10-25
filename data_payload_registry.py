"""Single registry for persisted top-level keys in data.json (#177)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

SCHEMA_VERSION = 2

# Stable key order for saves (O(number of keys); values are references, not deep-copied).
REGISTERED_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "schema_version",
    "categories",
    "entries",
    "settings",
    "sessions",
    "milestones",
    "journal",
    "creative_projects",
    "youtube_history",
    "day_plans",
    "todos",
    "practices",
    "program_state",
    "user_levels",
)

_TRACKER_ATTR: dict[str, str] = {
    key: key for key in REGISTERED_TOP_LEVEL_KEYS if key != "schema_version"
}

# Test-only extensions (parity / round-trip); cleared between tests.
_EPHEMERAL: dict[str, str] = {}

# Registered keys loaded outside hydrate_registered_from_migrated (ordering / side effects).
_LOAD_SPECIAL_KEYS: frozenset[str] = frozenset(
    {"schema_version", "categories", "entries", "settings", "sessions"}
)

# Keys applied by hydrate_registered_from_migrated (must stay in sync with REGISTERED_TOP_LEVEL_KEYS).
_HYDRATE_KEYS: tuple[str, ...] = tuple(
    key
    for key in REGISTERED_TOP_LEVEL_KEYS
    if key not in _LOAD_SPECIAL_KEYS
)


def validate_registry_key_name(name: str) -> None:
    """Reject keys that collide with backup restore stripping (integral_io.restore_backup_to_path)."""
    if name.startswith("backup_"):
        raise ValueError(
            f"Top-level data.json key '{name}' cannot use the reserved backup_ prefix"
        )


def registered_top_level_key_names(*, include_ephemeral: bool = True) -> frozenset[str]:
    keys = set(REGISTERED_TOP_LEVEL_KEYS)
    if include_ephemeral:
        keys.update(_EPHEMERAL)
    return frozenset(keys)


def register_ephemeral_top_level_key(name: str, attribute: str) -> None:
    """Register an extra persisted key (tests only)."""
    validate_registry_key_name(name)
    if name in REGISTERED_TOP_LEVEL_KEYS:
        raise ValueError(f"Key already registered: {name}")
    _EPHEMERAL[name] = attribute


def clear_ephemeral_top_level_keys() -> None:
    _EPHEMERAL.clear()


def partition_top_level(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    registered = registered_top_level_key_names()
    known: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    for key, value in data.items():
        if key in registered:
            known[key] = value
        else:
            extra[key] = value
    return known, extra


def extract_extra_top_level(migrated: dict[str, Any]) -> dict[str, Any]:
    return partition_top_level(migrated)[1]


def carry_forward_unknown_keys(
    source: dict[str, Any],
    target: dict[str, Any],
    *,
    consumed: Iterable[str],
) -> dict[str, Any]:
    """Preserve forward-compatible keys when building a new v2 dict from schema v1."""
    consumed_set = frozenset(consumed)
    for key, value in source.items():
        if key in consumed_set:
            continue
        if key not in target:
            target[key] = value
    return target


def build_known_top_level_payload(
    tracker: Any,
    *,
    schema_version: int = SCHEMA_VERSION,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"schema_version": schema_version}
    for key in REGISTERED_TOP_LEVEL_KEYS:
        if key == "schema_version":
            continue
        attr = _TRACKER_ATTR[key]
        payload[key] = getattr(tracker, attr)
    for key, attr in _EPHEMERAL.items():
        payload[key] = getattr(tracker, attr, None)
    return payload


def apply_ephemeral_from_migrated(tracker: Any, migrated: dict[str, Any]) -> None:
    for key, attr in _EPHEMERAL.items():
        if key in migrated:
            setattr(tracker, attr, migrated[key])


def _hydrate_normalizers() -> dict[str, Any]:
    import creative_projects
    import day_plans
    import journal
    import practices
    import todos
    import youtube_takeout

    from milestones import merge_milestones

    def _user_levels(raw: Any) -> dict:
        return dict(raw) if isinstance(raw, dict) else {}

    return {
        "milestones": merge_milestones,
        "journal": journal.normalize_journal,
        "creative_projects": creative_projects.normalize_creative_projects,
        "youtube_history": youtube_takeout.normalize_youtube_history,
        "day_plans": day_plans.normalize_day_plans,
        "todos": todos.normalize_todos,
        "practices": practices.normalize_practices,
        "program_state": lambda raw: raw if isinstance(raw, dict) else {},
        "user_levels": _user_levels,
    }


def hydrate_registered_from_migrated(tracker: Any, migrated: dict[str, Any]) -> None:
    """Load registered top-level keys that do not need pre-migration side effects."""
    normalizers = _hydrate_normalizers()
    for key in _HYDRATE_KEYS:
        normalizer = normalizers[key]
        setattr(tracker, _TRACKER_ATTR[key], normalizer(migrated.get(key)))


def merge_extra_top_level_into_payload(
    payload: dict[str, Any],
    extra: dict[str, Any],
) -> dict[str, Any]:
    registered = registered_top_level_key_names()
    for key, value in extra.items():
        if key not in registered:
            payload[key] = value
    return payload


def assert_load_registry_parity() -> None:
    """Every registered key must be loaded via load_data (special or hydrate)."""
    covered = set(_LOAD_SPECIAL_KEYS) | set(_HYDRATE_KEYS)
    expected = set(REGISTERED_TOP_LEVEL_KEYS)
    if covered != expected:
        missing = expected - covered
        extra = covered - expected
        raise AssertionError(
            f"Load registry parity failed: missing={missing!r}, extra={extra!r}"
        )


def assert_payload_registry_parity() -> None:
    """Fail when _payload key wiring drifts from REGISTERED_TOP_LEVEL_KEYS."""

    class _Stub:
        categories = {}
        entries = {}
        settings = {}
        sessions: list = []
        milestones: list = []
        journal = {}
        creative_projects = {}
        youtube_history = {}
        day_plans = {}
        todos = {}
        practices = {}
        program_state = {}
        user_levels = {}

    stub = _Stub()
    for _key, attr in _EPHEMERAL.items():
        setattr(stub, attr, None)

    built = set(build_known_top_level_payload(stub).keys())
    expected = set(REGISTERED_TOP_LEVEL_KEYS) | set(_EPHEMERAL)
    if built != expected:
        missing = expected - built
        extra = built - expected
        raise AssertionError(
            f"Registry parity failed: missing in build={missing!r}, extra in build={extra!r}"
        )


for _registered_key in REGISTERED_TOP_LEVEL_KEYS:
    if _registered_key != "schema_version":
        validate_registry_key_name(_registered_key)
