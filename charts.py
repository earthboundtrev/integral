def build_daily_avg_figure(entries):
    from matplotlib.figure import Figure

    fig = Figure(figsize=(10, 5))
    ax = fig.add_subplot(111)
    dates = sorted(entries.keys())[-30:]
    if dates:
        daily_avg = []
        for date_str in dates:
            ratings = [e.get("rating", 0) for e in entries[date_str].values()]
            daily_avg.append(sum(ratings) / len(ratings) if ratings else 0)
        ax.plot(dates, daily_avg, marker="o", linewidth=2)
        ax.set_title("Daily Average Rating (Last 30 Days)")
        ax.set_xlabel("Date")
        ax.set_ylabel("Average Rating (1-10)")
        ax.tick_params(axis="x", rotation=45)
    else:
        ax.text(0.5, 0.5, "No data yet", ha="center", va="center")
    fig.tight_layout()
    return fig


def build_category_avg_figure(entries, categories):
    from matplotlib.figure import Figure

    fig = Figure(figsize=(10, 5))
    ax = fig.add_subplot(111)
    cat_names = list(categories.keys())
    avgs = []
    for cat in cat_names:
        ratings = []
        for day in entries.values():
            if cat in day:
                ratings.append(day[cat].get("rating", 0))
        avgs.append(sum(ratings) / len(ratings) if ratings else 0)
    ax.bar(cat_names, avgs)
    ax.set_title("Average Rating per Category (All Time)")
    ax.set_ylabel("Average Rating")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig


def build_life_balance_figure(entries, categories):
    from matplotlib.figure import Figure
    import numpy as np

    cat_names = list(categories.keys())
    values = []
    for cat in cat_names:
        ratings = [
            day[cat].get("rating", 0)
            for day in entries.values()
            if cat in day and isinstance(day[cat].get("rating"), int | float)
        ]
        values.append(sum(ratings) / len(ratings) if ratings else 0)

    if not any(values):
        fig = Figure(figsize=(8, 6))
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "No data yet", ha="center", va="center")
        fig.tight_layout()
        return fig

    angles = np.linspace(0, 2 * np.pi, len(cat_names), endpoint=False).tolist()
    values_plot = values + [values[0]]
    angles_plot = angles + [angles[0]]
    short_labels = [name.split("&")[0].strip()[:14] for name in cat_names]

    fig = Figure(figsize=(8, 6))
    ax = fig.add_subplot(111, polar=True)
    ax.plot(angles_plot, values_plot, "o-", linewidth=2, color="#3498DB")
    ax.fill(angles_plot, values_plot, alpha=0.25, color="#3498DB")
    ax.set_xticks(angles)
    ax.set_xticklabels(short_labels, fontsize=9)
    ax.set_ylim(0, 10)
    ax.set_title("Life Balance Radar (8 Categories)", pad=20)
    fig.tight_layout()
    return fig


def embed_figure(parent, fig):
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

    canvas = FigureCanvasTkAgg(fig, parent)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
    return canvas
