import tkinter as tk
from tkinter import ttk

import ui_theme


def test_apply_theme_configures_styles():
    root = tk.Tk()
    root.withdraw()
    style = ui_theme.apply_theme(root)
    assert style.lookup("Accent.TButton", "background") == ui_theme.color("accent")
    assert style.lookup("TFrame", "background") == ui_theme.color("bg")
    root.destroy()


def test_make_card_has_surface_background():
    root = tk.Tk()
    root.withdraw()
    outer, inner = ui_theme.make_card(root, accent="#FF0000")
    assert inner.cget("bg") == ui_theme.color("surface")
    root.destroy()


def test_configure_fitness_tree_tags():
    root = tk.Tk()
    root.withdraw()
    tree = ttk.Treeview(root)
    ui_theme.configure_fitness_tree_tags(tree)
    tree.insert("", "end", iid="x", text="Test", tags=("mastered",))
    root.destroy()
