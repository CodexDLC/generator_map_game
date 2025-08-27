import tkinter as tk
from tkinter import ttk
from ...widgets import GroupBox, row, check
from .state import ExtractState
from ...widgets.form import row_path


class ExtractView:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=8)
        self.state = ExtractState.create_defaults()

        g1 = GroupBox(self.frame, text="Пути")
        g1.grid(row=0, column=0, sticky="nsew")
        row(g1, 0, "Источник (мир)", self.state.src)
        row(g1, 1, "Назначение (окно)", self.state.dst)

        g2 = GroupBox(self.frame, text="Окно")
        g2.grid(row=1, column=0, sticky="nsew", pady=(8,0))
        row(g2, 0, "Origin X", self.state.origin_x, unit="px")
        row(g2, 1, "Origin Y", self.state.origin_y, unit="px")
        row(g2, 2, "Width", self.state.width, unit="px")
        row(g2, 3, "Height", self.state.height, unit="px")
        row(g2, 4, "Chunk size", self.state.chunk, unit="px")
        check(g2, 5, "Копировать биомы", self.state.copy_biomes)

        self.btn_run = ttk.Button(self.frame, text="Extract")
        self.btn_run.grid(row=2, column=0, sticky="ew", pady=(10,0))

        g1 = GroupBox(self.frame, text="Пути")
        g1.grid(row=0, column=0, sticky="nsew")
        row_path(g1, 0, "Источник (мир)", self.state.src,  is_dir=True)
        row_path(g1, 1, "Назначение (окно)", self.state.dst, is_dir=True)