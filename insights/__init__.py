"""Life-area insights and coaching."""

from insights.engine import (
    Insight,
    analyze_all,
    analyze_practice_consistency,
    analyze_practice_symptom_correlations,
    category_insight,
    format_guidance_report,
    format_insight_line,
    top_insights,
)

__all__ = [
    "Insight",
    "analyze_all",
    "analyze_practice_consistency",
    "analyze_practice_symptom_correlations",
    "category_insight",
    "format_guidance_report",
    "format_insight_line",
    "top_insights",
]
