import tkinter as tk
from tkinter import ttk
from ..tabs import TABS

def main():
    root = tk.Tk()
    root.title("WorldGen")
    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)

    services = {}  # заполним позже

    for make_tab in TABS:
        tab = make_tab(nb, services)
        nb.add(tab.frame, text=tab.name)

    root.mainloop()
