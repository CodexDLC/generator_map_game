import tkinter as tk
from dataclasses import dataclass

@dataclass
class GridState:
    """Состояние для вкладки генерации сетки."""
    seed: tk.StringVar
    width: tk.StringVar
    height: tk.StringVar
    out_dir: tk.StringVar
    wall_chance: tk.StringVar

    @staticmethod
    def create_defaults():
        return GridState(
            seed=tk.StringVar(value="auto"),
            width=tk.StringVar(value="64"),
            height=tk.StringVar(value="64"),
            out_dir=tk.StringVar(value="out/grid_maps"),
            wall_chance=tk.StringVar(value="48")
        )

    def to_args(self) -> dict:
        """Преобразует состояние в словарь аргументов для генератора."""
        return {
            "seed": self.seed.get(),
            "width": int(self.width.get()),
            "height": int(self.height.get()),
            "out_dir": self.out_dir.get(),
            # Конвертируем процент в число от 0 до 1
            "wall_chance": float(self.wall_chance.get()) / 100.0
        }