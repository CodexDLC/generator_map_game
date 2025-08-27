import tkinter as tk
from tkinter import ttk
from ..tabs import TABS

def main():
    root = tk.Tk()
    root.title("WorldGen")
    root.geometry("900x560")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)

    services = {}  # общий контейнер сервисов, если потребуется

    for make_tab in TABS:
        tab = make_tab(nb, services)
        nb.add(tab.frame, text=tab.name)

    root.mainloop()
