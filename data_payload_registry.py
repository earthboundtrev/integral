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
    registered = registered_top_level_key_names()
    for key, value in source.items():
        if key in consumed_set or key in registered:
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
