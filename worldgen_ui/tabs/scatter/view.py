import tkinter as tk
from tkinter import ttk
from ...widgets import GroupBox, row, check
from .state import ScatterState
from ...widgets.form import row_path


class ScatterView:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=8)
        self.state = ScatterState.create_defaults()

        g_path = GroupBox(self.frame, text="Пути")
        g_path.grid(row=0, column=0, sticky="nsew")
        row_path(g_path, 0, "Мир (вход)", self.state.world_dir, is_dir=True)
        row_path(g_path, 1, "Выход (scatter)", self.state.out_dir, is_dir=True)

        g_obj = GroupBox(self.frame, text="Объект и случайность")
        g_obj.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        row_path(g_obj, 0, "Scene", self.state.instance_scene, is_dir=False)

        g_rules = GroupBox(self.frame, text="Правила размещения")
        g_rules.grid(row=0, column=1, sticky="nsew", padx=(8,0))
        row(g_rules, 0, "Seed", self.state.seed)
        row(g_rules, 1, "Плотность", self.state.density_km2, unit="шт/км²")
        row(g_rules, 2, "Мин. склон", self.state.min_slope_deg, unit="°")
        row(g_rules, 3, "Макс. склон", self.state.max_slope_deg, unit="°")
        row(g_rules, 4, "Мин. высота", self.state.min_height_m, unit="м")
        row(g_rules, 5, "Макс. высота", self.state.max_height_m, unit="м")
        row(g_rules, 6, "Фильтр биомов", self.state.biome_filter)  # напр. "plain,beach"

        g_obj = GroupBox(self.frame, text="Объект и случайность")
        g_obj.grid(row=1, column=0, sticky="nsew", pady=(8,0))
        row(g_obj, 0, "Scene", self.state.instance_scene)
        row(g_obj, 1, "Scale min", self.state.scale_min)
        row(g_obj, 2, "Scale max", self.state.scale_max)
        check(g_obj, 3, "Align to normal", self.state.align_to_normal)
        check(g_obj, 4, "Clear existing", self.state.clear_existing)

        self.btn_run = ttk.Button(self.frame, text="Scatter")
        self.btn_run.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10,0))

        self.lbl_status = ttk.Label(self.frame, text="Готово.")
        self.lbl_status.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6,0))
