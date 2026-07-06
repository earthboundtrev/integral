from collections.abc import Mapping
from typing import Any


CRITERIA_FIELD_TO_PERFORMANCE_FIELD = {
    "min_rating": "rating",
}


def meets_mastery(criteria: Mapping[str, Any], performance: Mapping[str, Any]) -> bool:
    """Return whether performance meets every numeric mastery threshold."""
    for criteria_field, required_value in criteria.items():
        if not isinstance(required_value, int | float):
            continue
        performance_field = CRITERIA_FIELD_TO_PERFORMANCE_FIELD.get(
            criteria_field,
            criteria_field,
        )
        actual_value = performance.get(performance_field)
        if not isinstance(actual_value, int | float):
            return False
        if actual_value < required_value:
            return False
    return True
