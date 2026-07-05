"""Life-area intelligence — detect patterns and suggest maintenance/progression actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from insights.playbooks import get_actions


@dataclass
class Insight:
    severity: str  # action | watch | positive | info
    category: str | None
    title: str
    message: str
    suggested_actions: list[str] = field(default_factory=list)
    priority: int = 50

    def sort_key(self) -> tuple[int, int]:
        order = {"action": 0, "watch": 1, "info": 2, "positive": 3}
        return (order.get(self.severity, 9), self.priority)


def _parse_date(date_str: str) -> date | None:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def _date_range(end: date, days: int) -> list[str]:
    return [(end - timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(days - 1, -1, -1)]


def _ratings_for_category(entries: dict, category: str, dates: list[str]) -> list[float]:
    values: list[float] = []
    for date_str in dates:
        entry = entries.get(date_str, {}).get(category)
        if not entry or entry.get("rating") is None:
            continue
        try:
            values.append(float(entry["rating"]))
        except (TypeError, ValueError):
            continue
    return values


def _days_since_logged(entries: dict, category: str, today: date) -> int | None:
    latest: date | None = None
    for date_str, cats in entries.items():
        if category not in cats:
            continue
        day = _parse_date(date_str)
        if day and (latest is None or day > latest):
            latest = day
    if latest is None:
        return None
    return (today - latest).days


def _checklist_completion_rate(entries: dict, category: str, cat_def: dict, dates: list[str]) -> tuple[int, int]:
    done = 0
    total = 0
    for date_str in dates:
        entry = entries.get(date_str, {}).get(category)
        if not entry:
            continue
        for item in cat_def.get("checklist", []):
            total += 1
            if entry.get("checklist", {}).get(item):
                done += 1
    return done, total


def _rarely_checked_items(entries: dict, category: str, cat_def: dict, dates: list[str]) -> list[str]:
    rare: list[str] = []
    for item in cat_def.get("checklist", []):
        checks = 0
        opportunities = 0
        for date_str in dates:
            entry = entries.get(date_str, {}).get(category)
            if not entry:
                continue
            opportunities += 1
            if entry.get("checklist", {}).get(item):
                checks += 1
        if opportunities >= 3 and checks == 0:
            rare.append(item)
        elif opportunities >= 5 and checks / opportunities < 0.2:
            rare.append(item)
    return rare


def _metric_trend(entries: dict, category: str, metric_name: str, dates: list[str]) -> str:
    values: list[float] = []
    for date_str in dates:
        entry = entries.get(date_str, {}).get(category)
        if not entry:
            continue
        raw = entry.get("metrics", {}).get(metric_name)
        if raw is None:
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue
    if len(values) < 3:
        return "insufficient_data"
    first_half = values[: len(values) // 2]
    second_half = values[len(values) // 2 :]
    if not first_half or not second_half:
        return "insufficient_data"
    delta = (sum(second_half) / len(second_half)) - (sum(first_half) / len(first_half))
    if delta > 0.5:
        return "improving"
    if delta < -0.5:
        return "declining"
    return "stable"


def analyze_category(
    category: str,
    cat_def: dict,
    entries: dict,
    today: date,
) -> list[Insight]:
    insights: list[Insight] = []
    today_str = today.strftime("%Y-%m-%d")
    last_7 = _date_range(today, 7)
    last_14 = _date_range(today, 14)
    prior_7 = _date_range(today - timedelta(days=7), 7)

    logged_today = category in entries.get(today_str, {})
    days_since = _days_since_logged(entries, category, today)

    if days_since is None:
        insights.append(
            Insight(
                severity="watch",
                category=category,
                title="Never logged",
                message=f"You haven't logged {category} yet. Starting is the hardest part on low-energy days.",
                suggested_actions=get_actions(category, "neglected"),
                priority=20,
            )
        )
        return insights

    if days_since >= 7:
        insights.append(
            Insight(
                severity="action",
                category=category,
                title="Maintenance gap",
                message=f"No log in {days_since} days — this area may be slipping while life continues.",
                suggested_actions=get_actions(category, "neglected"),
                priority=10,
            )
        )
    elif not logged_today and days_since == 1:
        insights.append(
            Insight(
                severity="watch",
                category=category,
                title="Streak at risk",
                message="You logged yesterday but not today. A quick rating takes under a minute.",
                suggested_actions=["Open Log / Update Today — rating + Save is enough."],
                priority=15,
            )
        )

    recent = _ratings_for_category(entries, category, last_7)
    prior = _ratings_for_category(entries, category, prior_7)
    if len(recent) >= 3 and len(prior) >= 3:
        recent_avg = sum(recent) / len(recent)
        prior_avg = sum(prior) / len(prior)
        if recent_avg <= prior_avg - 1.0:
            insights.append(
                Insight(
                    severity="action",
                    category=category,
                    title="Declining trend",
                    message=f"Average rating dropped from {prior_avg:.1f} to {recent_avg:.1f} over the last two weeks.",
                    suggested_actions=get_actions(category, "declining"),
                    priority=12,
                )
            )
        elif recent_avg >= prior_avg + 1.0:
            insights.append(
                Insight(
                    severity="positive",
                    category=category,
                    title="Improving trend",
                    message=f"Average rating rose from {prior_avg:.1f} to {recent_avg:.1f} — note what's working in your journal.",
                    suggested_actions=["Capture in notes what changed so you can repeat it."],
                    priority=80,
                )
            )

    if len(recent) >= 5:
        spread = max(recent) - min(recent)
        avg = sum(recent) / len(recent)
        if spread <= 1.5 and 4 <= avg <= 7:
            insights.append(
                Insight(
                    severity="watch",
                    category=category,
                    title="Plateau",
                    message=f"Ratings have been steady around {avg:.1f}/10 — progress may need a different lever.",
                    suggested_actions=get_actions(category, "plateau"),
                    priority=35,
                )
            )

    today_entry = entries.get(today_str, {}).get(category, {})
    if today_entry:
        try:
            today_rating = float(today_entry.get("rating", 10))
        except (TypeError, ValueError):
            today_rating = 10.0
        if today_rating <= 4:
            insights.append(
                Insight(
                    severity="action",
                    category=category,
                    title="Low day logged",
                    message=f"Today's rating is {today_rating:.0f}/10 — the app works best when you name what's hard.",
                    suggested_actions=get_actions(category, "low_rating"),
                    priority=8,
                )
            )

    rare_items = _rarely_checked_items(entries, category, cat_def, last_14)
    for item in rare_items[:2]:
        insights.append(
            Insight(
                severity="watch",
                category=category,
                title="Checklist gap",
                message=f"'{item}' hasn't been checked in 2 weeks — a maintenance item may need attention or editing.",
                suggested_actions=[
                    f"Either do '{item}' once this week or edit the checklist if it's no longer relevant.",
                ],
                priority=40,
            )
        )

    done, total = _checklist_completion_rate(entries, category, cat_def, last_7)
    if total >= 7 and done / total < 0.35:
        insights.append(
            Insight(
                severity="watch",
                category=category,
                title="Low checklist follow-through",
                message=f"Only {int((done / total) * 100)}% of checklist items completed this week.",
                suggested_actions=get_actions(category, "declining"),
                priority=30,
            )
        )

    return insights


def analyze_cross_category(
    entries: dict,
    categories: dict,
    today: date,
    sessions: list[dict] | None = None,
    program_state: dict | None = None,
) -> list[Insight]:
    insights: list[Insight] = []
    today_str = today.strftime("%Y-%m-%d")
    last_7 = _date_range(today, 7)

    logged_today_count = sum(1 for cat in categories if cat in entries.get(today_str, {}))
    if logged_today_count == 0 and entries:
        insights.append(
            Insight(
                severity="action",
                category=None,
                title="Nothing logged today",
                message="Pick one category and log rating + Save — 20 seconds protects your streak.",
                suggested_actions=[
                    "Start with Burnout Prevention, What You Have Eaten, or Body & Presence if energy is low.",
                ],
                priority=5,
            )
        )

    # Burnout cluster
    burnout = "Burnout Prevention & Energy Management"
    body = "Body & Presence"
    body_days = sum(1 for d in last_7 if body in entries.get(d, {})) if body in categories else 0
    body_ratings = _ratings_for_category(entries, body, last_7) if body in categories else []
    if burnout in categories and body in categories:
        energy_trend = _metric_trend(entries, body, "Energy level", last_7)
        stress_trend = _metric_trend(entries, burnout, "Stress level (lower = better)", last_7)
        morning_trend = _metric_trend(entries, burnout, "Morning energy", last_7)
        if energy_trend == "declining" or (
            stress_trend == "improving" and morning_trend == "declining"
        ):
            insights.append(
                Insight(
                    severity="action",
                    category=burnout,
                    title="Burnout warning",
                    message="Energy is down and/or stress is up across recent logs — protect recovery before pushing output.",
                    suggested_actions=get_actions(burnout, "declining")
                    + ["Consider lowering Creative/Mental Work expectations this week."],
                    priority=6,
                )
            )

    if sessions is not None:
        recent_fitness = [
            session
            for session in sessions
            if _parse_date(session.get("date", "")) and (today - _parse_date(session["date"])).days <= 14
        ]
        if body_days >= 3 and body_ratings and sum(body_ratings) / len(body_ratings) < 5 and not recent_fitness:
            insights.append(
                Insight(
                    severity="watch",
                    category=body,
                    title="Body struggling, no structured fitness",
                    message="Body & Presence ratings are low and no fitness sessions in 14 days.",
                    suggested_actions=[
                        "Log a minimal movement session in Fitness Hub or tick 'Completed movement/exercise'.",
                        "Check sleep hours — often the root cause.",
                    ],
                    priority=18,
                )
            )

    if program_state:
        for program_id, state in program_state.items():
            if not isinstance(state, dict):
                continue
            for key, item in state.items():
                if isinstance(item, dict) and item.get("ready_to_advance"):
                    insights.append(
                        Insight(
                            severity="positive",
                            category=body,
                            title="Fitness: ready to advance",
                            message=item.get("messages", ["Official progression standard met."])[0],
                            suggested_actions=["Open Fitness Hub to confirm advancement and log the next session."],
                            priority=25,
                        )
                    )
                if isinstance(item, dict) and item.get("trend") == "plateau":
                    insights.append(
                        Insight(
                            severity="watch",
                            category=body,
                            title="Fitness plateau",
                            message=f"{key}: stable at current step for multiple sessions — review form or recovery.",
                            suggested_actions=[
                                "Re-read official B/I/P standards for your current step.",
                                "Deload or repeat beginner standard before forcing progression.",
                            ],
                            priority=32,
                        )
                    )

    food = "What You Have Eaten"
    emotional = "Emotional Wellbeing"
    art = "Art You Have Consumed"
    content = "Content You Have Consumed"
    reading = "General Reading"
    creative = "Creative/Mental Work"
    money = "Money/Freedom"
    career = "Career & Vocation"
    learning = "Learning & Intellectual Growth"
    relationships = "Relationships & Social Connection"
    cultural = "Cultural Life & Heritage"
    home = "Home & Environment"
    community = "Community & Service"
    spiritual = "Spiritual Development"
    if food in categories and body in categories:
        food_days = sum(1 for d in last_7 if food in entries.get(d, {}))
        if body_days >= 3 and body_ratings and sum(body_ratings) / len(body_ratings) < 5.5 and food_days == 0:
            insights.append(
                Insight(
                    severity="watch",
                    category=food,
                    title="Body struggling — food not logged",
                    message="Body ratings are soft this week and eating hasn't been logged — fuel and recovery may be connected.",
                    suggested_actions=get_actions(food, "neglected")
                    + ["Note sleep and one meal that helped or hurt energy."],
                    priority=20,
                )
            )

    if emotional in categories and art in categories:
        mood_ratings = _ratings_for_category(entries, emotional, last_7)
        art_days = sum(1 for d in last_7 if art in entries.get(d, {}))
        if mood_ratings and sum(mood_ratings) / len(mood_ratings) < 5 and art_days == 0:
            insights.append(
                Insight(
                    severity="watch",
                    category=art,
                    title="Mood low — little art logged",
                    message="Emotional ratings are down and no art logged this week — input isn't a fix, but honest logging helps you see the gap.",
                    suggested_actions=get_actions(art, "neglected")
                    + get_actions(emotional, "low_rating")[:1],
                    priority=22,
                )
            )

    if content in categories:
        content_days = sum(1 for d in last_7 if content in entries.get(d, {}))
        attention = _metric_trend(entries, content, "Quality of attention", last_7)
        if content_days >= 4 and attention == "declining":
            insights.append(
                Insight(
                    severity="watch",
                    category=content,
                    title="Lots of content, slipping attention",
                    message="You're logging content often but attention quality is trending down — worth noting what format drags you.",
                    suggested_actions=get_actions(content, "declining"),
                    priority=24,
                )
            )

    if reading in categories and content in categories:
        reading_days = sum(1 for d in last_7 if reading in entries.get(d, {}))
        content_days = sum(1 for d in last_7 if content in entries.get(d, {}))
        if content_days >= 5 and reading_days == 0:
            insights.append(
                Insight(
                    severity="watch",
                    category=reading,
                    title="Feeds up, books quiet",
                    message="Short-form content is logged most days this week but no book reading — fine if intentional; worth noticing.",
                    suggested_actions=get_actions(reading, "declining"),
                    priority=26,
                )
            )

    if creative in categories and reading in categories:
        creative_ratings = _ratings_for_category(entries, creative, last_7)
        reading_days = sum(1 for d in last_7 if reading in entries.get(d, {}))
        if creative_ratings and sum(creative_ratings) / len(creative_ratings) < 5 and reading_days == 0:
            insights.append(
                Insight(
                    severity="watch",
                    category=reading,
                    title="Creative work low — no reading logged",
                    message="Output feels stuck and no long-form reading this week — input and craft often travel together.",
                    suggested_actions=get_actions(reading, "neglected")[:2],
                    priority=28,
                )
            )

    if money in categories and career in categories:
        money_trend = _metric_trend(entries, money, "Financial clarity rating", last_7)
        if money_trend == "declining":
            career_ratings = _ratings_for_category(entries, career, last_7)
            if career_ratings and sum(career_ratings) / len(career_ratings) < 5.5:
                insights.append(
                    Insight(
                        severity="watch",
                        category=money,
                        title="Money and work both under strain",
                        message="Financial clarity is trending down and career satisfaction is soft — often connected; log one small action in each.",
                        suggested_actions=get_actions(money, "declining")[:1]
                        + get_actions(career, "low_rating")[:1],
                        priority=19,
                    )
                )

    if emotional in categories and relationships in categories:
        mood_ratings = _ratings_for_category(entries, emotional, last_7)
        loneliness_trend = _metric_trend(entries, relationships, "Loneliness (lower = better)", last_7)
        if mood_ratings and sum(mood_ratings) / len(mood_ratings) < 5 and loneliness_trend == "improving":
            insights.append(
                Insight(
                    severity="watch",
                    category=relationships,
                    title="Mood down — loneliness creeping up",
                    message="Emotional ratings are low and loneliness metrics are trending worse — connection may need attention.",
                    suggested_actions=get_actions(relationships, "neglected")
                    + get_actions(emotional, "low_rating")[:1],
                    priority=21,
                )
            )

    if cultural in categories and art in categories:
        cultural_days = sum(1 for d in last_7 if cultural in entries.get(d, {}))
        art_days = sum(1 for d in last_7 if art in entries.get(d, {}))
        if art_days >= 4 and cultural_days == 0:
            insights.append(
                Insight(
                    severity="info",
                    category=cultural,
                    title="Consuming culture, not practicing it",
                    message="Art is logged often but active cultural life isn't — passive intake vs language, tradition, or heritage.",
                    suggested_actions=get_actions(cultural, "neglected")[:2],
                    priority=30,
                )
            )

    if home in categories and burnout in categories:
        stress_trend = _metric_trend(entries, burnout, "Stress level (lower = better)", last_7)
        home_ratings = _ratings_for_category(entries, home, last_7)
        if stress_trend == "improving" and home_ratings and sum(home_ratings) / len(home_ratings) < 5:
            insights.append(
                Insight(
                    severity="watch",
                    category=home,
                    title="Stress up — environment suffering",
                    message="Burnout stress is rising and home/environment ratings are low — clutter and recovery often travel together.",
                    suggested_actions=get_actions(home, "declining")[:2]
                    + get_actions(burnout, "declining")[:1],
                    priority=23,
                )
            )

    if learning in categories and creative in categories:
        learning_days = sum(1 for d in last_7 if learning in entries.get(d, {}))
        creative_ratings = _ratings_for_category(entries, creative, last_7)
        if creative_ratings and sum(creative_ratings) / len(creative_ratings) < 5.5 and learning_days == 0:
            insights.append(
                Insight(
                    severity="watch",
                    category=learning,
                    title="Output stuck — little learning logged",
                    message="Creative work is soft and no deliberate learning this week — skills and input feed output.",
                    suggested_actions=get_actions(learning, "neglected")[:2],
                    priority=27,
                )
            )

    if spiritual in categories and community in categories:
        spiritual_days = sum(1 for d in last_7 if spiritual in entries.get(d, {}))
        community_days = sum(1 for d in last_7 if community in entries.get(d, {}))
        if spiritual_days >= 3 and community_days == 0:
            insights.append(
                Insight(
                    severity="info",
                    category=community,
                    title="Inner practice strong — outer service quiet",
                    message="Spiritual practice is consistent but service/community isn't logged — balance inner and outer if that matters to you.",
                    suggested_actions=get_actions(community, "neglected")[:2],
                    priority=31,
                )
            )

    return insights


def analyze_all(
    entries: dict,
    categories: dict,
    *,
    today: date | None = None,
    sessions: list[dict] | None = None,
    program_state: dict | None = None,
) -> list[Insight]:
    today = today or date.today()
    insights: list[Insight] = []
    for cat_name, cat_def in categories.items():
        insights.extend(analyze_category(cat_name, cat_def, entries, today))
    insights.extend(
        analyze_cross_category(entries, categories, today, sessions=sessions, program_state=program_state)
    )
    insights.sort(key=lambda item: item.sort_key())
    return insights


def top_insights(insights: list[Insight], limit: int = 5) -> list[Insight]:
    prioritized = [item for item in insights if item.severity in ("action", "watch")]
    if len(prioritized) < limit:
        prioritized.extend(item for item in insights if item.severity == "positive")
    return prioritized[:limit]


def category_insight(insights: list[Insight], category: str) -> Insight | None:
    for item in insights:
        if item.category == category and item.severity in ("action", "watch"):
            return item
    return None


def format_insight_line(insight: Insight) -> str:
    prefix = {"action": "!", "watch": "~", "positive": "+", "info": "·"}.get(insight.severity, "·")
    return f"{prefix} {insight.title}: {insight.message}"


def format_guidance_report(insights: list[Insight]) -> str:
    if not insights:
        return "Log a few days across categories — guidance improves as patterns emerge.\n"

    lines = ["GUIDANCE & MAINTENANCE\n", "=" * 50 + "\n"]
    current_severity: str | None = None
    for insight in insights:
        if insight.severity != current_severity:
            current_severity = insight.severity
            label = {
                "action": "NEEDS ATTENTION",
                "watch": "WATCH",
                "positive": "WINS & MOMENTUM",
                "info": "INFO",
            }.get(current_severity, current_severity.upper())
            lines.append(f"\n{label}\n" + "-" * 30 + "\n")

        cat = f"[{insight.category}] " if insight.category else ""
        lines.append(f"{cat}{insight.title}\n")
        lines.append(f"  {insight.message}\n")
        if insight.suggested_actions:
            lines.append("  Try:\n")
            for action in insight.suggested_actions:
                lines.append(f"    • {action}\n")
        lines.append("\n")
    return "".join(lines)
