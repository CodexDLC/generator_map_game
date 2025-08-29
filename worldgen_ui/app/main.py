
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from ..tabs.world.state import WorldState
from ..tabs.world.view import WorldView

def main():
    root = tk.Tk()
    root.title("WorldGen — Stage C (base preview)")
    root.geometry("720x800")

    state = WorldState()
    view = WorldView(root, state)
    view.pack(fill="both", expand=True)

    root.mainloop()
