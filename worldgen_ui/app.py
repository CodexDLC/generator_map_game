#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk

# --- ИЗМЕНЕНИЕ: Импортируем ScatterTab ---
from worldgen_ui.tabs import GenerateTab, ExtractTab, ScatterTab

def main():
    root = tk.Tk()
    root.title("WorldGen")
    root.geometry("820x560")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)

    nb.add(GenerateTab(nb), text="1. Generate")
    nb.add(ExtractTab(nb), text="2. World Detailer")
    # --- ИЗМЕНЕНИЕ: Добавляем новую вкладку ---
    nb.add(ScatterTab(nb), text="3. Scatter Objects")

    root.mainloop()

if __name__ == "__main__":
    main()