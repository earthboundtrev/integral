import sqlite3


class ProgressionCycleError(ValueError):
    """Raised when a prerequisite edge would create a cycle."""


def would_create_cycle(
    conn: sqlite3.Connection,
    from_exercise_id: str,
    to_exercise_id: str,
) -> bool:
    if from_exercise_id == to_exercise_id:
        return True

    # A new from -> to edge creates a cycle if `to` already reaches `from`.
    stack = [to_exercise_id]
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current == from_exercise_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        rows = conn.execute(
            """
            SELECT to_exercise_id
            FROM progression_edges
            WHERE from_exercise_id = ? AND edge_type = 'prerequisite'
            """,
            (current,),
        ).fetchall()
        stack.extend(row["to_exercise_id"] for row in rows)
    return False
