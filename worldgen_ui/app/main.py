from __future__ import annotations
import pathlib, tkinter as tk
from tkinter import ttk
from ..tabs.world.state import WorldState
from ..tabs.world.view import WorldView
from ..tabs.gallery.view import GalleryView

def main():
    root = tk.Tk()
    root.title("WorldGen — worlds & branches")
    root.geometry("1000x820")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)

    # Мир (город/ветви)
    state = WorldState()
    world_tab = WorldView(nb, state)
    nb.add(world_tab, text="Мир")

    # Галерея по мирам
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    gal_root = ROOT / "artifacts" / "world"
    gallery_tab = GalleryView(nb, default_root=str(gal_root))
    nb.add(gallery_tab, text="Галерея")

    root.mainloop()
