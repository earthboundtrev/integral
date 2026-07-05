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
            "Try tracking money actions separately from mood ratings.",
        ],
        "low_rating": [
            "When money feels stuck, shrink the task: one receipt, one transfer, one decision.",
            "Journal what 'freedom' would feel like tomorrow — not in 5 years.",
        ],
    },
    "Career & Vocation": {
        "neglected": [
            "Log one professional action — email sent, skill practiced, boundary held.",
            "Note whether work today aligned with calling or only paid bills.",
        ],
        "declining": [
            "Declining satisfaction often tracks burnout — check energy before pushing harder.",
            "Name one skill or relationship that would move career forward this month.",
        ],
        "plateau": [
            "Stable but flat? Log whether you need growth, rest, or a pivot.",
            "Separate hours worked from satisfaction in metrics to see the gap.",
        ],
        "low_rating": [
            "Bad work weeks are data — note what drained you without fixing everything.",
            "One boundary or one small win counts; log it and step away.",
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
            "Plateau may mean output is steady — try shipping something tiny.",
            "Review whether learning input (reading, courses) has stalled too.",
        ],
        "low_rating": [
            "On low-energy days, 'capture ideas' beats 'finish project'.",
            "Note the obstacle in one sentence — that's progress data.",
        ],
    },
    "Learning & Intellectual Growth": {
        "neglected": [
            "15 minutes of deliberate practice counts — log the skill and duration.",
            "Follow one curiosity thread and note where it led.",
        ],
        "declining": [
            "If learning dropped, check whether content feeds replaced depth.",
            "Pick one skill to focus on for two weeks; log daily touchpoints.",
        ],
        "plateau": [
            "Plateau can mean consolidation — note what you're integrating vs collecting.",
            "Try teaching or explaining what you learned — log that as practice.",
        ],
        "low_rating": [
            "Brain fog days: log mental clarity low and rest without guilt.",
            "Shrink to one page, one lesson, or one vocabulary word.",
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
    "Relationships & Social Connection": {
        "neglected": [
            "One text, call, or coffee invitation counts — log it.",
            "Loneliness without logging becomes invisible; rate honestly.",
        ],
        "declining": [
            "If connection dropped, note whether isolation was chosen or default.",
            "Reach out to one person you miss — log before or after, not instead.",
        ],
        "plateau": [
            "Lots of shallow contact? Note one conversation that had depth.",
            "Track loneliness metric separately from belonging.",
        ],
        "low_rating": [
            "Social exhaustion is real — log boundary kept, not only outings.",
            "One authentic exchange beats five performative ones.",
        ],
    },
    "Home & Environment": {
        "neglected": [
            "Five minutes tidying one surface counts — log space satisfaction.",
            "Step outside or open a window; note nature time even if brief.",
        ],
        "declining": [
            "Clutter often tracks stress — check Burnout before blaming yourself.",
            "One environmental fix: light, air, one cleared zone.",
        ],
        "plateau": [
            "Home stable but stale? Note one small upgrade that would help mood.",
            "Track nature time separately from indoor tidying.",
        ],
        "low_rating": [
            "When space drags you down, log honestly — outsourcing or help counts.",
            "Bad environment days: note what would help most in one sentence.",
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
            "Regulation tools (walk, breath, talk) — note which you tried.",
            "Low days: log rating + one sentence; skip checklist if needed.",
        ],
    },
    "Community & Service": {
        "neglected": [
            "Small kindness counts — log one act of service or help given.",
            "Contribution doesn't require a nonprofit; note informal giving too.",
        ],
        "declining": [
            "If service dropped during burnout, that's information — protect rest first.",
            "One hour volunteered or one neighbor helped — log and rate.",
        ],
        "plateau": [
            "Routine volunteering can flatten — note what still feels alive.",
            "Balance giving with receiving; check Emotional and Burnout areas.",
        ],
        "low_rating": [
            "Compassion fatigue is real — log boundary, not only output.",
            "Low contribution days: note what you needed for yourself.",
        ],
    },
    "Cultural Life & Heritage": {
        "neglected": [
            "Culture can be one song in your heritage, one recipe, one phrase in a language.",
            "Log a museum visit, festival, or intentional cultural meal.",
        ],
        "declining": [
            "Passive art consumption without active culture? Compare Art vs this category.",
            "Reconnect with one tradition or curiosity about roots.",
        ],
        "plateau": [
            "Tourism vs depth — note whether engagement felt alive or touristic.",
            "Language practice 10 minutes counts toward cultural aliveness.",
        ],
        "low_rating": [
            "Disconnection from culture can track displacement or grief — log gently.",
            "One small ritual or food memory can reopen the channel.",
        ],
    },
    "What You Have Eaten": {
        "neglected": [
            "You don't need a perfect food diary — log one meal or snack and how it felt.",
            "Note what you ate in free-form notes; rating alone still counts.",
        ],
        "declining": [
            "Declining nourishment ratings often track stress or rushed days — check Burnout.",
            "Name one meal that felt good this week; repeat what worked.",
        ],
        "plateau": [
            "Stable ratings may hide autopilot eating — note one mindful meal.",
            "Track 'energy after eating' separately from overall nourishment.",
        ],
        "low_rating": [
            "Low days: log honestly without judgment — patterns matter more than one score.",
            "Shrink to one sentence: what did you eat and how did your body feel?",
        ],
    },
    "Art You Have Consumed": {
        "neglected": [
            "Log one piece of art — a song, scene, novel chapter, comic, or game moment counts.",
            "Tick the medium you engaged with; add title and one line in notes.",
        ],
        "declining": [
            "If art intake dropped, note whether you want more input or more space.",
            "Try one shorter format (song, short film, comic chapter) and log it.",
        ],
        "plateau": [
            "Plateau can mean comfort viewing — note what still moves you vs what is filler.",
            "Use 'would recommend' metric to separate memorable from passive consumption.",
        ],
        "low_rating": [
            "Low ratings are valid — note what felt empty or overstimulating.",
            "Art that drained you is still worth logging; it teaches your taste.",
        ],
    },
    "Content You Have Consumed": {
        "neglected": [
            "Log content honestly — including scroll time if that was most of the day.",
            "One podcast chapter or article + one takeaway is enough.",
        ],
        "declining": [
            "Declining 'quality of attention' often means more passive intake — note the shift.",
            "Separate learning content from news/social in notes to see the mix.",
        ],
        "plateau": [
            "Lots of content with flat value? Try one deep dive instead of many tabs.",
            "Check if you applied anything from last week's consumption.",
        ],
        "low_rating": [
            "Doomscrolling counts — log it, then decide if tomorrow needs a boundary.",
            "Low value days: note one piece worth keeping and skip the rest mentally.",
        ],
    },
    "General Reading": {
        "neglected": [
            "One chapter or 15 minutes counts — log title and format in notes.",
            "Audiobook during a commute still counts; tick audiobook and note the book.",
        ],
        "declining": [
            "If reading dropped while content time rose, note the swap — feeds vs books.",
            "Pick one short book or essay collection to restart momentum.",
        ],
        "plateau": [
            "Many books started, few finished? Log progress % instead of only time.",
            "Use 'what I retained' to separate reading that stuck from skimming.",
        ],
        "low_rating": [
            "Low retention days happen — note whether the book, your energy, or context was off.",
            "DNF is valid; log why you stopped so your future self learns.",
        ],
    },
}


def get_actions(category: str, issue_type: str) -> list[str]:
    book = PLAYBOOKS.get(category, {})
    return book.get(issue_type, book.get("declining", ["Log today with an honest rating and one note about the obstacle."]))
