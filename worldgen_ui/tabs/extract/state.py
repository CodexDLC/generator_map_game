import tkinter as tk
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ExtractState:
    src: tk.StringVar
    dst: tk.StringVar
    origin_x: tk.StringVar
    origin_y: tk.StringVar
    width: tk.StringVar
    height: tk.StringVar
    chunk: tk.StringVar
    copy_biomes: tk.BooleanVar

    @staticmethod
    def create_defaults():
        return ExtractState(
            src=tk.StringVar(value=str(Path("out/demo/v1"))),
            dst=tk.StringVar(value=str(Path("out/window_demo/v1"))),
            origin_x=tk.StringVar(value="0"),
            origin_y=tk.StringVar(value="0"),
            width=tk.StringVar(value="1024"),
            height=tk.StringVar(value="1024"),
            chunk=tk.StringVar(value="512"),
            copy_biomes=tk.BooleanVar(value=True),
        )

    def to_args(self):
        return (
            self.src.get(),
            self.dst.get(),
            int(self.origin_x.get()),
            int(self.origin_y.get()),
            int(self.width.get()),
            int(self.height.get()),
            int(self.chunk.get()),
            bool(self.copy_biomes.get()),
        )
