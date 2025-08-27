import tkinter as tk
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ScatterState:
    world_dir: tk.StringVar
    out_dir: tk.StringVar
    seed: tk.StringVar
    density_km2: tk.StringVar

    min_slope_deg: tk.StringVar
    max_slope_deg: tk.StringVar
    min_height_m: tk.StringVar
    max_height_m: tk.StringVar

    biome_filter: tk.StringVar
    instance_scene: tk.StringVar

    scale_min: tk.StringVar
    scale_max: tk.StringVar
    align_to_normal: tk.BooleanVar
    clear_existing: tk.BooleanVar

    @staticmethod
    def create_defaults():
        return ScatterState(
            world_dir=tk.StringVar(value=str(Path("out/demo/v1"))),
            out_dir=tk.StringVar(value=str(Path("out/demo_scatter/v1"))),
            seed=tk.StringVar(value="12345"),
            density_km2=tk.StringVar(value="200"),

            min_slope_deg=tk.StringVar(value="0"),
            max_slope_deg=tk.StringVar(value="35"),
            min_height_m=tk.StringVar(value="-1000"),
            max_height_m=tk.StringVar(value="10000"),

            biome_filter=tk.StringVar(value=""),   # пусто = любые биомы
            instance_scene=tk.StringVar(value="res://path/to/Tree.tscn"),

            scale_min=tk.StringVar(value="0.8"),
            scale_max=tk.StringVar(value="1.2"),
            align_to_normal=tk.BooleanVar(value=True),
            clear_existing=tk.BooleanVar(value=False),
        )

    def to_args(self):
        """Подготовка аргументов для services.worldgen.scatter(...).
        Сигнатуру ядра можно будет подогнать позже — тут возвращаем плоский словарь."""
        return dict(
            world_dir=self.world_dir.get(),
            out_dir=self.out_dir.get(),
            seed=int(self.seed.get()),
            density_km2=float(self.density_km2.get()),

            min_slope_deg=float(self.min_slope_deg.get()),
            max_slope_deg=float(self.max_slope_deg.get()),
            min_height_m=float(self.min_height_m.get()),
            max_height_m=float(self.max_height_m.get()),

            biome_filter=self.biome_filter.get().strip(),
            instance_scene=self.instance_scene.get(),

            scale_min=float(self.scale_min.get()),
            scale_max=float(self.scale_max.get()),
            align_to_normal=bool(self.align_to_normal.get()),
            clear_existing=bool(self.clear_existing.get()),
        )
