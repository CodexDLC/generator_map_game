
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from .state import WorldState
from .controller import WorldController

PALETTE = {
    "ground": "#7a9e7a",
    "obstacle": "#444444",
    "water": "#3573b8",
    "void": "#000000",
}

class WorldView(ttk.Frame):
    def __init__(self, master, state: WorldState):
        super().__init__(master)
        self.state = state
        self.ctrl = WorldController(state)

        # UI
        top = ttk.Frame(self)
        top.pack(fill="x", padx=6, pady=6)
        ttk.Label(top, text="Seed:").pack(side="left")
        self.seed_var = tk.IntVar(value=self.state.seed)
        ttk.Entry(top, textvariable=self.seed_var, width=10).pack(side="left", padx=4)
        ttk.Button(top, text="Set", command=self._apply_seed).pack(side="left", padx=4)

        nav = ttk.Frame(self)
        nav.pack(fill="x", padx=6, pady=6)
        ttk.Button(nav, text="← W", command=lambda: self._move(-1,0)).pack(side="left")
        ttk.Button(nav, text="↑ N", command=lambda: self._move(0,-1)).pack(side="left", padx=4)
        ttk.Button(nav, text="↓ S", command=lambda: self._move(0,1)).pack(side="left", padx=4)
        ttk.Button(nav, text="E →", command=lambda: self._move(1,0)).pack(side="left")

        self.canvas = tk.Canvas(self, width=512, height=512, bg="#222")
        self.canvas.pack(fill="both", expand=True, padx=6, pady=6)

        self.status = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status).pack(fill="x", padx=6, pady=(0,6))

        self._redraw()

    def _apply_seed(self):
        self.state.seed = int(self.seed_var.get())
        self.state.cache.clear()
        self._redraw()

    def _move(self, dx: int, dz: int):
        self.ctrl.move(dx, dz)
        self._redraw()

    def _redraw(self):
        data = self.ctrl.load_center()
        layers = data.get("layers", {})
        kind_rle = layers.get("kind", {})
        rows = kind_rle.get("rows", [])
        size = data.get("size", 64)
        # раскодируем RLE в грид для отрисовки
        grid = []
        for row in rows:
            line = []
            for val, run in row:
                line.extend([val]*run)
            grid.append(line)

        self.canvas.delete("all")
        w = self.canvas.winfo_width() or 512
        h = self.canvas.winfo_height() or 512
        cell = max(1, min(w, h) // max(1, size))
        offx = (w - size*cell)//2
        offy = (h - size*cell)//2

        for z in range(size):
            row = grid[z]
            for x in range(size):
                v = row[x] if x < len(row) else "void"
                color = PALETTE.get(v, "#000000")
                x0 = offx + x*cell; y0 = offy + z*cell
                x1 = x0 + cell; y1 = y0 + cell
                self.canvas.create_rectangle(x0,y0,x1,y1, outline=color, fill=color)

        # порты подсветим красным
        ports = data.get("ports", {"N":[],"E":[],"S":[],"W":[]})
        # N
        for x in ports.get("N", []):
            x0 = offx + x*cell; y0 = offy + 0*cell
            self.canvas.create_rectangle(x0, y0, x0+cell, y0+cell, outline="#ff0000", width=2)
        # S
        for x in ports.get("S", []):
            x0 = offx + x*cell; y0 = offy + (size-1)*cell
            self.canvas.create_rectangle(x0, y0, x0+cell, y0+cell, outline="#ff0000", width=2)
        # W
        for z in ports.get("W", []):
            x0 = offx + 0*cell; y0 = offy + z*cell
            self.canvas.create_rectangle(x0, y0, x0+cell, y0+cell, outline="#ff0000", width=2)
        # E
        for z in ports.get("E", []):
            x0 = offx + (size-1)*cell; y0 = offy + z*cell
            self.canvas.create_rectangle(x0, y0, x0+cell, y0+cell, outline="#ff0000", width=2)

        self.status.set(f"seed={self.state.seed}  cx={self.state.cx} cz={self.state.cz}")
