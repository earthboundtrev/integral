from datetime import datetime, timedelta

from ai_insights import (
    DEFAULT_MODEL,
    build_chat_messages,
    collect_recent_context,
    ollama_installed,
)


def test_collect_recent_context_compact():
    today = datetime.now().date()
    date_str = today.strftime("%Y-%m-%d")
    entries = {
        date_str: {
            "Body & Presence": {
                "rating": 8,
                "notes": "Morning walk felt good.",
                "checklist": {},
                "metrics": {},
            },
            "Emotional Wellbeing": {
                "rating": 6,
                "notes": "A bit drained after meetings.",
                "checklist": {},
                "metrics": {},
            },
        }
    }
    categories = {
        "Body & Presence": {"checklist": [], "metrics": []},
        "Emotional Wellbeing": {"checklist": [], "metrics": []},
    }
    journal_data = {
        "entries": [
            {
                "id": "j1",
                "entry_date": date_str,
                "title": "Evening reflection",
                "body": "Grateful for small wins today.",
                "written_at": f"{date_str}T20:00:00",
            }
        ]
    }

    context = collect_recent_context(
        entries,
        categories,
        journal_data=journal_data,
        fitness_settings=None,
        days=7,
    )

    assert "Body & Presence" in context
    assert "avg rating 8.0/10" in context
    assert "Emotional Wellbeing" in context
    assert "Evening reflection" in context
    assert "JOURNAL" in context
    assert len(context) < 4000


def test_build_chat_messages_weekly_review():
    messages = build_chat_messages("sample context", kind="weekly_review", days=7)
    assert messages[0]["role"] == "system"
    assert "life coach" in messages[0]["content"]
    assert "sample context" in messages[1]["content"]
    assert "Next steps" in messages[1]["content"]


def test_ollama_optional():
    # App must import without ollama installed in CI
    assert isinstance(ollama_installed(), bool)
    assert DEFAULT_MODEL == "llama3.2:3b"
