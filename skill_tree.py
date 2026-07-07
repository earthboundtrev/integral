"""Lightweight Tkinter skill tree visualization for the fitness DAG."""

from fitness_ui import ensure_fitness_seeded, list_exercise_rows, open_log_dialog_for_exercise
from progression.db import FitnessRepository

STATUS_COLORS = {
    "locked": "#BDC3C7",
    "available": "#3498DB",
    "in_progress": "#F39C12",
    "mastered": "#27AE60",
}
NODE_WIDTH = 200
NODE_HEIGHT = 40
X_GAP = 260
Y_START = 50
Y_GAP = 58


def get_profile_repo() -> FitnessRepository:
    return FitnessRepository()


def build_skill_tree_model(
    repo: FitnessRepository,
    source_book: str | None = None,
    family: str | None = None,
) -> dict:
    ensure_fitness_seeded(repo)
    rows = list_exercise_rows(repo, source_book=source_book, family=family)

    families: dict[str, list[dict]] = {}
    for row in rows:
        key = f"{row['source_book']}:{row['family']}"
        families.setdefault(key, []).append(row)

    nodes = []
    max_y = Y_START
    for col_index, (_key, group_rows) in enumerate(sorted(families.items())):
        x = 60 + col_index * X_GAP
        for row_index, row in enumerate(group_rows):
            y = Y_START + row_index * Y_GAP
            max_y = max(max_y, y)
            label = f"{row['step']}. {row['name']}" if row["step"] != "" else row["name"]
            if len(label) > 28:
                label = label[:25] + "..."
            nodes.append(
                {
                    "id": row["id"],
                    "label": label,
                    "status": row["status"],
                    "source_book": row["source_book"],
                    "family": row["family"],
                    "x": x,
                    "y": y,
                    "width": NODE_WIDTH,
                    "height": NODE_HEIGHT,
                    "color": STATUS_COLORS.get(row["status"], STATUS_COLORS["locked"]),
                }
            )

    node_ids = {node["id"] for node in nodes}
    edges = []
    for edge in repo.list_edges():
        if edge.from_exercise_id not in node_ids or edge.to_exercise_id not in node_ids:
            continue
        edges.append(
            {
                "from": edge.from_exercise_id,
                "to": edge.to_exercise_id,
                "type": edge.edge_type,
            }
        )

    width = max(60 + len(families) * X_GAP + NODE_WIDTH, 480)
    height = max(max_y + 100, 400)
    return {"nodes": nodes, "edges": edges, "width": width, "height": height}


def draw_skill_tree(canvas, model: dict) -> None:
    canvas.delete("all")
    nodes_by_id = {node["id"]: node for node in model["nodes"]}

    for edge in model["edges"]:
        source = nodes_by_id[edge["from"]]
        target = nodes_by_id[edge["to"]]
        x1 = source["x"] + source["width"]
        y1 = source["y"] + source["height"] / 2
        x2 = target["x"]
        y2 = target["y"] + target["height"] / 2
        color = "#9B59B6" if edge["type"] == "recommended" else "#7F8C8D"
        style = () if edge["type"] == "prerequisite" else (4, 2)
        canvas.create_line(x1, y1, x2, y2, arrow="last", fill=color, width=2, dash=style)

    for node in model["nodes"]:
        x1 = node["x"]
        y1 = node["y"]
        x2 = x1 + node["width"]
        y2 = y1 + node["height"]
        tag = f"node:{node['id']}"
        canvas.create_rectangle(
            x1, y1, x2, y2, fill=node["color"], outline="#2C3E50", width=2, tags=(tag, "node")
        )
        canvas.create_text(
            x1 + 8,
            y1 + node["height"] / 2,
            text=node["label"],
            anchor="w",
            fill="white" if node["status"] in {"available", "in_progress", "mastered"} else "#2C3E50",
            font=("Helvetica", 9, "bold"),
            tags=(tag, "node"),
        )

    canvas.configure(scrollregion=(0, 0, model["width"], model["height"]))


def show_skill_tree_window(
    root,
    repo: FitnessRepository | None = None,
    *,
    on_session_saved=None,
    fitness_settings: dict | None = None,
):
    import tkinter as tk
    from tkinter import ttk

    repo = repo or get_profile_repo()
    ensure_fitness_seeded(repo)

    filter_state = {"source_book": None, "family": None}

    win = tk.Toplevel(root)
    win.title("Fitness Skill Tree")
    win.geometry("900x720")
    win.transient(root)

    header = ttk.Frame(win, padding=10)
    header.pack(fill=tk.X)
    ttk.Label(header, text="Fitness Skill Tree", font=("Helvetica", 14, "bold")).pack(anchor="w")
    ttk.Label(
        header,
        text="Green = mastered, blue = available, orange = in progress, gray = locked. Click a node to log.",
    ).pack(anchor="w")

    filter_frame = ttk.Frame(header)
    filter_frame.pack(fill=tk.X, pady=6)
    books = sorted({row["source_book"] for row in list_exercise_rows(repo)})
    families = sorted({row["family"] for row in list_exercise_rows(repo)})
    book_var = tk.StringVar(value="All")
    family_var = tk.StringVar(value="All")

    ttk.Label(filter_frame, text="Book:").pack(side=tk.LEFT)
    book_combo = ttk.Combobox(
        filter_frame,
        textvariable=book_var,
        values=["All"] + books,
        state="readonly",
        width=12,
    )
    book_combo.pack(side=tk.LEFT, padx=6)
    ttk.Label(filter_frame, text="Family:").pack(side=tk.LEFT)
    family_combo = ttk.Combobox(
        filter_frame,
        textvariable=family_var,
        values=["All"] + families,
        state="readonly",
        width=14,
    )
    family_combo.pack(side=tk.LEFT, padx=6)

    body = ttk.Frame(win)
    body.pack(fill=tk.BOTH, expand=True)
    canvas = tk.Canvas(body, background="white", highlightthickness=0)
    scrollbar_y = ttk.Scrollbar(body, orient=tk.VERTICAL, command=canvas.yview)
    scrollbar_x = ttk.Scrollbar(body, orient=tk.HORIZONTAL, command=canvas.xview)
    canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
    scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

    import ui_scroll

    ui_scroll.activate_dialog_scrolling(win, canvas)
    ui_scroll.bind_mousewheel(canvas, canvas.yview)
    ui_scroll.bind_mousewheel(canvas, canvas.xview, horizontal=True)

    def current_filters():
        book = None if book_var.get() == "All" else book_var.get()
        family = None if family_var.get() == "All" else family_var.get()
        return book, family

    def refresh():
        book, family = current_filters()
        model = build_skill_tree_model(repo, source_book=book, family=family)
        draw_skill_tree(canvas, model)

    def on_node_click(event):
        item = canvas.find_closest(event.x, event.y)
        if not item:
            return
        tags = canvas.gettags(item[0])
        for tag in tags:
            if tag.startswith("node:"):
                exercise_id = tag.split(":", 1)[1]
                open_log_dialog_for_exercise(
                    win,
                    repo,
                    exercise_id,
                    on_saved=refresh,
                    on_session_saved=on_session_saved,
                    fitness_settings=fitness_settings,
                )
                return

    canvas.bind("<Button-1>", on_node_click)
    book_combo.bind("<<ComboboxSelected>>", lambda _e: refresh())
    family_combo.bind("<<ComboboxSelected>>", lambda _e: refresh())
    refresh()
    return win
