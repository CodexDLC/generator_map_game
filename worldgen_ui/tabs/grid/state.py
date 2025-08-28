import tkinter as tk
from dataclasses import dataclass



@dataclass
class GridState:
    seed: tk.StringVar
    width: tk.StringVar
    height: tk.StringVar
    out_dir: tk.StringVar
    wall_chance: tk.StringVar
    # NEW:
    mode: tk.StringVar
    open_min: tk.StringVar
    border_mode: tk.StringVar
    border_outer_cells: tk.StringVar
    deep_enabled: tk.BooleanVar
    deep_density: tk.StringVar
    deep_scale: tk.StringVar
    deep_threshold: tk.StringVar
    puddles_enabled: tk.BooleanVar
    puddles_density: tk.StringVar
    puddles_scale: tk.StringVar
    puddles_threshold: tk.StringVar

    @staticmethod
    def create_defaults():
        return GridState(
            seed=tk.StringVar(value="auto"),
            width=tk.StringVar(value="64"),
            height=tk.StringVar(value="64"),
            out_dir=tk.StringVar(value="out/grid_maps"),
            wall_chance=tk.StringVar(value="48"),
            # NEW defaults
            mode=tk.StringVar(value="cave"),
            open_min=tk.StringVar(value="55"),
            border_mode=tk.StringVar(value="cliff"),
            border_outer_cells=tk.StringVar(value="1"),
            deep_enabled=tk.BooleanVar(value=True),
            deep_density=tk.StringVar(value="6"),
            deep_scale=tk.StringVar(value="15.0"),
            deep_threshold=tk.StringVar(value="62"),
            puddles_enabled=tk.BooleanVar(value=True),
            puddles_density=tk.StringVar(value="3"),
            puddles_scale=tk.StringVar(value="8.0"),
            puddles_threshold=tk.StringVar(value="65"),
        )

    def to_args(self) -> dict:
        return {
            "seed": self.seed.get(),
            "width": int(self.width.get()),
            "height": int(self.height.get()),
            "out_dir": self.out_dir.get(),
            "wall_chance": float(self.wall_chance.get()) / 100.0,

            "mode": self.mode.get(),  # cave|rooms|hybrid|open
            "open_min": float(self.open_min.get()) / 100.0,
            "border_mode": self.border_mode.get(),  # cliff|wall|void
            "border_outer_cells": int(self.border_outer_cells.get()),

            "water": {
                "deep": {
                    "enabled": bool(self.deep_enabled.get()),
                    "density": float(self.deep_density.get()) / 100.0,
                    "scale": float(self.deep_scale.get()),
                    "threshold": float(self.deep_threshold.get()) / 100.0,
                },
                "puddles": {
                    "enabled": bool(self.puddles_enabled.get()),
                    "density": float(self.puddles_density.get()) / 100.0,
                    "scale": float(self.puddles_scale.get()),
                    "threshold": float(self.puddles_threshold.get()) / 100.0,
                },
            },

            # НОВОЕ: биомы (дорога по пути + раскраска floor по весам)
            "biomes": {
                "road_width": 3,
                "safe_radius_gate": 3,
                "no_mountain_in_necks": True,
                "weights": {
                    "grass": 0.45,
                    "forest": 0.30,
                    "mountain": 0.15,
                },
            },
        }