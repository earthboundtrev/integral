"""Today's Log helpers — domain filter, pinned favorites (settings.todays_log)."""

from __future__ import annotations

MAX_PINNED_DOMAINS = 5

# Short labels for filter matching (kept here so helpers stay UI-free).
CATEGORY_SHORT_LABELS = {
    "Money/Freedom": "Money",
    "Career & Vocation": "Career",
    "Body & Presence": "Body",
    "Burnout Prevention & Energy Management": "Energy",
    "Creative/Mental Work": "Creative",
    "Learning & Intellectual Growth": "Learning",
    "Family/Logistics": "Family",
    "Relationships & Social Connection": "Relationships",
    "Home & Environment": "Home",
    "Search Practice": "Search",
    "Spiritual Development": "Spiritual",
    "Emotional Wellbeing": "Emotional",
    "Community & Service": "Community",
    "Cultural Life & Heritage": "Culture",
    "What You Have Eaten": "Food",
    "Art You Have Consumed": "Art",
    "General Reading": "Reading",
    "Content You Have Consumed": "Content",
}


def default_todays_log_settings() -> dict:
    return {"pinned_domains": []}


def normalize_todays_log_settings(settings: dict | None) -> dict:
    base = default_todays_log_settings()
    if not isinstance(settings, dict):
        return base
    raw = settings.get("todays_log")
    if not isinstance(raw, dict):
        return base
    pinned_raw = raw.get("pinned_domains")
    if not isinstance(pinned_raw, list):
        pinned_raw = []
    pinned: list[str] = []
    seen: set[str] = set()
    for item in pinned_raw:
        name = str(item).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        pinned.append(name)
        if len(pinned) >= MAX_PINNED_DOMAINS:
            break
    return {"pinned_domains": pinned}


def apply_todays_log_settings(settings: dict | None, patch: dict | None = None) -> dict:
    out = dict(settings or {})
    current = normalize_todays_log_settings(out)
    if isinstance(patch, dict):
        if "pinned_domains" in patch:
            current = normalize_todays_log_settings({"todays_log": {"pinned_domains": patch["pinned_domains"]}})
        else:
            current = {**current, **{k: v for k, v in patch.items() if k != "pinned_domains"}}
            current = normalize_todays_log_settings({"todays_log": current})
    out["todays_log"] = current
    return out


def pinned_domains(settings: dict | None) -> list[str]:
    return list(normalize_todays_log_settings(settings)["pinned_domains"])


def toggle_pinned_domain(
    settings: dict | None,
    name: str,
    *,
    valid_names: set[str] | frozenset[str] | None = None,
) -> tuple[dict, str | None]:
    """
    Pin or unpin a domain. Returns (updated_settings, error_message_or_None).
    """
    name = str(name).strip()
    if not name:
        return dict(settings or {}), "Pick a domain to pin."
    if valid_names is not None and name not in valid_names:
        return dict(settings or {}), "Unknown domain."

    current = pinned_domains(settings)
    if valid_names is not None:
        current = [n for n in current if n in valid_names]
    if name in current:
        current = [n for n in current if n != name]
    else:
        if len(current) >= MAX_PINNED_DOMAINS:
            return (
                dict(settings or {}),
                f"You can pin up to {MAX_PINNED_DOMAINS} domains. Unpin one first.",
            )
        current = current + [name]
    return apply_todays_log_settings(settings, {"pinned_domains": current}), None


def prune_pinned_domains(
    settings: dict | None,
    valid_names: set[str] | frozenset[str] | list[str],
) -> dict:
    """Drop pinned names that are no longer categories."""
    valid = set(valid_names)
    current = [n for n in pinned_domains(settings) if n in valid]
    return apply_todays_log_settings(settings, {"pinned_domains": current})


def filter_todays_log_categories(
    category_names: list[str],
    *,
    query: str = "",
    status: str = "all",
    logged_names: set[str] | frozenset[str] | None = None,
    short_labels: dict[str, str] | None = None,
    pinned_names: list[str] | None = None,
) -> list[str]:
    """Filter/sort domain names for the Today's Log button grid (pure, UI-safe)."""
    labels = short_labels if short_labels is not None else CATEGORY_SHORT_LABELS
    logged = logged_names or set()
    needle = query.strip().lower()
    status_key = (status or "all").strip().lower()
    if status_key not in {"all", "unlogged", "logged"}:
        status_key = "all"

    name_set = set(category_names)
    pinned = [n for n in (pinned_names or []) if n in name_set]

    matched: list[str] = []
    for name in category_names:
        is_logged = name in logged
        if status_key == "unlogged" and is_logged:
            continue
        if status_key == "logged" and not is_logged:
            continue
        if needle:
            blob = f"{name} {labels.get(name, name)}".lower()
            if needle not in blob:
                continue
        matched.append(name)

    matched_set = set(matched)
    pinned_matched = [n for n in pinned if n in matched_set]
    pinned_set = set(pinned_matched)
    rest = [n for n in matched if n not in pinned_set]

    if status_key == "all":
        unlogged = [name for name in rest if name not in logged]
        already = [name for name in rest if name in logged]
        rest = unlogged + already
    return pinned_matched + rest
