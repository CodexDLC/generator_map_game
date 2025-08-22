#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk

from worldgen_ui.tabs import GenerateTab, ExtractTab


def main():
    root = tk.Tk()
    root.title("WorldGen")
    root.geometry("820x560")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)

    nb.add(GenerateTab(nb), text="Generate")
    nb.add(ExtractTab(nb), text="Extract")

    root.mainloop()

if __name__ == "__main__":
    main()
