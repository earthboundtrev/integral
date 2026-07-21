"""Pre-configured Life Domain templates (SPEC-317).

Templates reuse the existing category schema (``checklist`` + ``metrics``) so applying
one simply merges pre-filled domains into ``tracker.categories``. Add a new key to
``DOMAIN_TEMPLATES`` to ship another pack — no UI changes required.
"""

from __future__ import annotations

from typing import Any

DOMAIN_TEMPLATES: dict[str, dict[str, Any]] = {
    "gut_healing": {
        "title": "Gut Healing Starter Pack",
        "description": (
            "Holistic gut/mucosal healing: digestion, movement, diet, breathwork, "
            "supplements, recovery, and overall progress."
        ),
        "domains": {
            "Gut Health / Digestion": {
                "checklist": [
                    "No gluten today",
                    "No processed sugar",
                    "Bone broth / gut-support food",
                    "Adequate hydration",
                ],
                "metrics": [
                    {"name": "Gas / bloating (lower = better)", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Stomach comfort", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Bowel regularity", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            "Physical Practices & Movement": {
                "checklist": [
                    "Five Tibetan Rites completed",
                    "Walk / low-intensity movement",
                    "Mobility / stretching",
                ],
                "metrics": [
                    {"name": "Energy after practice", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Movement minutes", "type": "number", "unit": "min", "default": 0},
                ],
            },
            "Nutrition & Diet Adherence": {
                "checklist": [
                    "Followed protocol meals",
                    "No trigger foods",
                    "Ate slowly / mindfully",
                ],
                "metrics": [
                    {"name": "Diet adherence", "type": "number", "unit": "%", "default": 0},
                ],
            },
            "Breathwork & Mindfulness": {
                "checklist": [
                    "Breathwork session",
                    "Meditation / mindfulness",
                    "Vagus-nerve / relaxation practice",
                ],
                "metrics": [
                    {"name": "Minutes practiced", "type": "number", "unit": "min", "default": 0},
                    {"name": "Calm / regulation", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            "Supplements": {
                "checklist": [
                    "Morning stack",
                    "Evening stack",
                    "Probiotic / L-glutamine (as prescribed)",
                ],
                "metrics": [
                    {"name": "Adherence", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            "Energy & Recovery": {
                "checklist": [
                    "7+ hours sleep",
                    "Rest / downtime",
                    "Sunlight exposure",
                ],
                "metrics": [
                    {"name": "Sleep hours", "type": "number", "unit": "hrs", "default": 0},
                    {"name": "Morning energy", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            "Overall Healing Progress": {
                "checklist": [
                    "Symptom check-in logged",
                    "Noted wins / setbacks",
                ],
                "metrics": [
                    {"name": "Overall well-being", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
        },
    },
}


def list_templates() -> list[dict[str, Any]]:
    """Summaries for a picker UI (id, title, description, domain_count)."""
    return [
        {
            "id": template_id,
            "title": template["title"],
            "description": template["description"],
            "domain_count": len(template["domains"]),
        }
        for template_id, template in DOMAIN_TEMPLATES.items()
    ]


def get_template(template_id: str) -> dict[str, Any] | None:
    return DOMAIN_TEMPLATES.get(template_id)


def _copy_domain(definition: dict[str, Any]) -> dict[str, Any]:
    return {
        "checklist": [str(item) for item in definition.get("checklist", [])],
        "metrics": [dict(metric) for metric in definition.get("metrics", [])],
    }


def apply_template(
    categories: dict[str, Any] | None,
    template_id: str,
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Merge a template's domains into ``categories`` (non-destructive).

    Returns ``(new_categories, added, skipped)``. Existing domain names are never
    overwritten — they are reported in ``skipped``. New domains are deep-copied so the
    template dict is not shared with live state.
    """
    template = DOMAIN_TEMPLATES.get(template_id)
    if template is None:
        raise KeyError(f"Unknown template: {template_id}")
    result = dict(categories or {})
    added: list[str] = []
    skipped: list[str] = []
    for name, definition in template["domains"].items():
        if name in result:
            skipped.append(name)
            continue
        result[name] = _copy_domain(definition)
        added.append(name)
    return result, added, skipped
