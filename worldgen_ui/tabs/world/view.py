
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

from .controller import WorldController
from .state import WorldState


PALETTE = {
    "ground": "#7a9e7a",
    "obstacle": "#444444",
    "water": "#3573b8",
    "void": "#000000",
}

ID2KIND = {0: "ground", 1: "obstacle", 2: "water"}

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
        self.btn_w = ttk.Button(nav, text="← W", command=lambda: self._on_nav(-1, 0))
        self.btn_n = ttk.Button(nav, text="↑ N", command=lambda: self._on_nav(0, -1))
        self.btn_s = ttk.Button(nav, text="↓ S", command=lambda: self._on_nav(0, 1))
        self.btn_e = ttk.Button(nav, text="E →", command=lambda: self._on_nav(1, 0))
        self.btn_w.pack(side="left")
        self.btn_n.pack(side="left", padx=4)
        self.btn_s.pack(side="left", padx=4)
        self.btn_e.pack(side="left")

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

    def _on_nav(self, dx: int, dz: int):
        # жёсткая проверка шва
        if not self.ctrl.can_move(dx, dz):
            self.status.set("Нет порта в эту сторону — переход запрещён.")
            return
        self.ctrl.move(dx, dz)
        self._redraw()

    def _update_nav_buttons(self, _ports_unused):
        # Решаем, можно ли шагнуть логически, а не по порту
        def en(btn, ok): btn.config(state=("normal" if ok else "disabled"))

        en(self.btn_n, self.ctrl.can_move(0, -1))
        en(self.btn_e, self.ctrl.can_move(1, 0))
        en(self.btn_s, self.ctrl.can_move(0, 1))
        en(self.btn_w, self.ctrl.can_move(-1, 0))

    def _grid_from_kind_payload(self, payload, size):
        """
        Нормализует layers.kind:
          - если RLE dict -> декодируем в grid и считаем, что значения = id (0/1/2)
          - если 2D list  -> берём как есть (значения могут быть строками или id)
          - иначе          -> пустая сетка
        Возвращает (grid, val_to_kind_fn)
        """
        if isinstance(payload, dict) and payload.get("encoding") == "rle_rows_v1":
            rows = payload.get("rows", [])
            grid = self._decode_rle_rows(rows)

            def val_to_kind(v):  # RLE обычно отдаём id
                try:
                    return ID2KIND.get(int(v), "ground")
                except Exception:
                    return "ground"

            return grid, val_to_kind

        if isinstance(payload, list):
            grid = payload

            def val_to_kind(v):
                if isinstance(v, str):
                    return v
                try:
                    return ID2KIND.get(int(v), "ground")
                except Exception:
                    return "ground"

            return grid, val_to_kind

        # fallback
        grid = [[0] * size for _ in range(size)]

        def val_to_kind(_v):
            return "ground"

        return grid, val_to_kind

    def _decode_rle_rows(self, rows):
        grid = []
        for r in rows:
            line = []
            for val, run in r:
                line.extend([val] * int(run))
            grid.append(line)
        return grid

    def _extract_grid_and_size(self, data):
        """
        Возвращает (grid, size), где grid — 2D список значений (строки или id).
        Понимает три формата:
          - data["layers"]["kind"] как RLE dict {"encoding":"rle_rows_v1","rows":[...]}
          - data["layers"]["kind"] как 2D list
          - data["chunks"][0] как RLE (при загрузке с диска)
        """
        # 1) layers.kind
        layers = data.get("layers", {})
        if "kind" in layers:
            payload = layers["kind"]
            if isinstance(payload, dict) and payload.get("encoding") == "rle_rows_v1":
                grid = self._decode_rle_rows(payload.get("rows", []))
                size = len(grid) if grid else data.get("size", 64)
                return grid, size
            if isinstance(payload, list):
                grid = payload
                size = len(grid) if grid else data.get("size", 64)
                return grid, size

        # 2) chunks[0] (как в сохранённом chunk.rle.json)
        chunks = data.get("chunks", [])
        if chunks:
            ch = chunks[0]
            grid = self._decode_rle_rows(ch.get("rows", []))
            size = ch.get("h", len(grid) if grid else data.get("size", 64))
            return grid, size

        # 3) пусто — вернём чистую сетку
        size = data.get("size", 64)
        return [[0] * size for _ in range(size)], size


    def _redraw(self):
        data = self.ctrl.load_center()

        grid, size = self._extract_grid_and_size(data)

        self.canvas.delete("all")
        w = self.canvas.winfo_width() or 512
        h = self.canvas.winfo_height() or 512
        cell = max(1, min(w, h) // max(1, size))
        offx = (w - size * cell) // 2
        offy = (h - size * cell) // 2

        for z in range(size):
            row = grid[z] if z < len(grid) else []
            for x in range(size):
                v = row[x] if x < len(row) else 0
                # нормализуем к имени тайла
                if isinstance(v, str):
                    kind_name = v
                else:
                    try:
                        kind_name = ID2KIND.get(int(v), "ground")
                    except Exception:
                        kind_name = "ground"
                color = PALETTE.get(kind_name, "#000000")
                x0 = offx + x * cell
                y0 = offy + z * cell
                x1 = x0 + cell
                y1 = y0 + cell
                self.canvas.create_rectangle(x0, y0, x1, y1, outline=color, fill=color)

        # порты (берём из top-level или из _meta, что найдём)
        ports = data.get("ports") or (data.get("_meta", {}) or {}).get("ports") or {"N": [], "E": [], "S": [], "W": []}

        # N
        for x in ports.get("N", []):
            x0 = offx + x * cell
            y0 = offy
            self.canvas.create_rectangle(x0, y0, x0 + cell, y0 + cell, outline="#ff0000", width=2)
        # S
        for x in ports.get("S", []):
            x0 = offx + x * cell
            y0 = offy + (size - 1) * cell
            self.canvas.create_rectangle(x0, y0, x0 + cell, y0 + cell, outline="#ff0000", width=2)
        # W
        for z in ports.get("W", []):
            x0 = offx
            y0 = offy + z * cell
            self.canvas.create_rectangle(x0, y0, x0 + cell, y0 + cell, outline="#ff0000", width=2)
        # E
        for z in ports.get("E", []):
            x0 = offx + (size - 1) * cell
            y0 = offy + z * cell
            self.canvas.create_rectangle(x0, y0, x0 + cell, y0 + cell, outline="#ff0000", width=2)

        if self.state.world_id == "city" and self.state.cx == 0 and self.state.cz == 0:
            gates = self.ctrl._city_gateway_sides()
            size = len(grid)
            cell = max(1, min(self.canvas.winfo_width() or 512, self.canvas.winfo_height() or 512) // max(1, size))
            offx = (self.canvas.winfo_width() or 512 - size * cell) // 2
            offy = (self.canvas.winfo_height() or 512 - size * cell) // 2
            # рисуем маленькие оранжевые квадраты на соответствующих сторонах
            mark = "#ffa600"
            if "N" in gates:
                x0 = offx + (size // 2) * cell
                y0 = offy
                self.canvas.create_rectangle(x0, y0, x0 + cell, y0 + cell, outline=mark, width=2)
            if "S" in gates:
                x0 = offx + (size // 2) * cell
                y0 = offy + (size - 1) * cell
                self.canvas.create_rectangle(x0, y0, x0 + cell, y0 + cell, outline=mark, width=2)
            if "W" in gates:
                x0 = offx
                y0 = offy + (size // 2) * cell
                self.canvas.create_rectangle(x0, y0, x0 + cell, y0 + cell, outline=mark, width=2)
            if "E" in gates:
                x0 = offx + (size - 1) * cell
                y0 = offy + (size // 2) * cell
                self.canvas.create_rectangle(x0, y0, x0 + cell, y0 + cell, outline=mark, width=2)