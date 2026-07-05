"""Category-specific coaching playbooks for maintenance and progression."""

from __future__ import annotations

PLAYBOOKS: dict[str, dict[str, list[str]]] = {
    "Money/Freedom": {
        "neglected": [
            "Log one concrete money action today — even 5 minutes reviewing accounts counts.",
            "Pick one freedom goal and write the next smallest step in notes.",
        ],
        "declining": [
            "Identify one expense or income leak you can address this week.",
            "Re-read long-term money goals; note what felt harder this week.",
        ],
        "plateau": [
            "Plateaus often mean maintenance mode — schedule a 15-minute finance review.",
            "Try a new metric: track one action toward freedom, not just mood.",
        ],
        "low_rating": [
            "When money feels stuck, shrink the task: one receipt, one transfer, one decision.",
            "Journal what 'freedom' would feel like tomorrow — not in 5 years.",
        ],
    },
    "Body & Presence": {
        "neglected": [
            "A 10-minute walk or mobility round counts — log it and rate honestly.",
            "Check sleep hours in metrics; low sleep often drives skipped movement.",
        ],
        "declining": [
            "Reduce scope: one movement, one mindful meal, one presence check-in.",
            "Open Fitness Hub if you use structured programs — log even a partial session.",
        ],
        "plateau": [
            "Swap one checklist item (mindfulness vs movement) to break routine fatigue.",
            "Note energy level separately from overall rating to spot patterns.",
        ],
        "low_rating": [
            "Hypersomnia days: log presence without demanding exercise.",
            "Hydration + 5 minutes outside can shift energy before a full workout.",
        ],
    },
    "Burnout Prevention & Energy Management": {
        "neglected": [
            "This area protects everything else — log even a 1/10 rating today.",
            "Name one boundary you kept or need to set; put it in notes.",
        ],
        "declining": [
            "Stress up + energy down is a warning — plan one intentional break today.",
            "Audit: what drained you most this week? Write it in notes.",
        ],
        "plateau": [
            "Burnout prevention is maintenance — schedule non-negotiable rest blocks.",
            "Track morning energy for 7 days before changing your whole routine.",
        ],
        "low_rating": [
            "Lower the bar: one self-care act, one boundary, then save.",
            "If stress is high, skip deep work — protect recovery first.",
        ],
    },
    "Creative/Mental Work": {
        "neglected": [
            "Capture one idea in notes — deep work can wait until energy returns.",
            "Log 25 minutes of focused work if a full session feels impossible.",
        ],
        "declining": [
            "Split creative vs admin — log which type dropped off.",
            "Reduce friction: same time, same place, smallest possible task.",
        ],
        "plateau": [
            "Plateau may mean output is steady — try a new capture method in notes.",
            "Review insights metric: are you collecting but not acting?",
        ],
        "low_rating": [
            "On low-energy days, 'capture ideas' beats 'finish project'.",
            "Note the obstacle in one sentence — that's progress data.",
        ],
    },
    "Family/Logistics": {
        "neglected": [
            "Send one meaningful message or handle one logistics task — then log.",
            "Family time can be quality over quantity; note what happened.",
        ],
        "declining": [
            "Name one conversation avoided — logging it is the first repair step.",
            "Split logistics vs connection in notes to see which slipped.",
        ],
        "plateau": [
            "Stable family ratings may hide uneven time — track hours honestly.",
            "Pick one recurring logistics task to systematize this week.",
        ],
        "low_rating": [
            "Logistics overwhelm is valid — tackle one task, not the whole list.",
            "Note one moment of connection, however small.",
        ],
    },
    "Search Practice": {
        "neglected": [
            "Search practice can be 5 minutes of honest inquiry — log it.",
            "Write one question you're sitting with; that counts as practice.",
        ],
        "declining": [
            "Return to journaling: what are you actually searching for right now?",
            "One concrete search-related action beats passive rumination.",
        ],
        "plateau": [
            "Plateau in search often means integration — review past notes for themes.",
            "Try changing the practice form (walk, read, dialogue) and log it.",
        ],
        "low_rating": [
            "Low ratings here are data, not failure — note what feels blocked.",
            "Shrink practice to one reflection sentence in notes.",
        ],
    },
    "Spiritual Development": {
        "neglected": [
            "One minute of stillness or gratitude counts — log and move on.",
            "Re-read a single teaching or prayer; note one line that lands.",
        ],
        "declining": [
            "Spiritual dips often track stress — check Burnout and Emotional categories.",
            "Practice connection without performance: presence over duration.",
        ],
        "plateau": [
            "Maintenance is valid — note what practice still feeds you vs what feels rote.",
            "Try community or nature if solo practice has flattened.",
        ],
        "low_rating": [
            "Honest low ratings are part of the path — write without fixing.",
            "Gratitude or surrender practice can be smaller than meditation.",
        ],
    },
    "Emotional Wellbeing": {
        "neglected": [
            "Name one emotion in notes — that's a check-in worth logging.",
            "Self-compassion counts: log even when mood is flat.",
        ],
        "declining": [
            "Declining mood + skipped emotional check-ins is a loop — log first, act second.",
            "Note triggers in free-form notes; patterns emerge over weeks.",
        ],
        "plateau": [
            "Stable mood can still need processing — journal one feeling in depth.",
            "Track check-in count metric to separate awareness from intensity.",
        ],
        "low_rating": [
            "Low days: log rating + one sentence; skip checklist if needed.",
            "Regulation tools (walk, breath, talk) — note which you tried.",
        ],
    },
}


def get_actions(category: str, issue_type: str) -> list[str]:
    book = PLAYBOOKS.get(category, {})
    return book.get(issue_type, book.get("declining", ["Log today with an honest rating and one note about the obstacle."]))
