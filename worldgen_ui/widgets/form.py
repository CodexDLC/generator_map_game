import tkinter as tk
from tkinter import ttk, filedialog
from .tooltip import attach as attach_tooltip

class GroupBox(ttk.LabelFrame):
    def __init__(self, parent, text="", **kw):
        super().__init__(parent, text=text, padding=(8,8,8,8), **kw)
        self.columnconfigure(1, weight=1)

def row(parent, r, label, var, width=12, unit=None, tooltip: str | None = None):
    ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", padx=(0,6), pady=2)
    e = ttk.Entry(parent, textvariable=var, width=width)
    e.grid(row=r, column=1, sticky="ew", pady=2)
    if unit:
        ttk.Label(parent, text=unit).grid(row=r, column=2, sticky="w", padx=(6,0))
    if tooltip:
        attach_tooltip(e, tooltip)
    return e

def check(parent, r, label, var, tooltip: str | None = None):
    c = ttk.Checkbutton(parent, text=label, variable=var)
    c.grid(row=r, column=0, columnspan=3, sticky="w", pady=2)
    if tooltip:
        attach_tooltip(c, tooltip)
    return c

def row_path(parent, r, label, var, must_exist=True, is_dir=True, tooltip: str | None = None):
    ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", padx=(0,6), pady=2)
    e = ttk.Entry(parent, textvariable=var)
    e.grid(row=r, column=1, sticky="ew", pady=2)
    def browse():
        if is_dir:
            p = filedialog.askdirectory()
        else:
            p = filedialog.askopenfilename()
        if p:
            var.set(p)
    btn = ttk.Button(parent, text="…", width=3, command=browse)
    btn.grid(row=r, column=2, sticky="w", padx=(6,0))
    if tooltip:
        attach_tooltip(e, tooltip)
        attach_tooltip(btn, tooltip)
    return e
