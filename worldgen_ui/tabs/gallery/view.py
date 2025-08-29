from __future__ import annotations
import os, re, pathlib
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, Tuple, Optional, List

# PIL для нормального ресайза (опционально)
try:
    from PIL import Image, ImageTk
    PIL_OK = True
except Exception:
    PIL_OK = False

THUMB   = 128
GAP     = 8
MARGIN  = 16
NAME_RE = re.compile(r"^(?P<cx>-?\d+)_(?P<cz>-?\d+)$")

class GalleryView(ttk.Frame):
    """
    Галерея: artifacts/world/<world_id>/<seed>/<cx>_<cz>/
    Позволяет выбрать world_id и seed, рисует плитки плотно, заглушки — тёмные с белой надписью 'cx,cz'.
    """
    def __init__(self, master, default_root: Optional[str] = None):
        super().__init__(master)
        self.root_dir_var = tk.StringVar(value=default_root or "artifacts/world")
        self.world_var = tk.StringVar(value="")
        self.seed_var  = tk.StringVar(value="")

        self.items: Dict[Tuple[int,int], pathlib.Path] = {}
        self.images: Dict[Tuple[int,int], tk.PhotoImage] = {}
        self.min_cx = self.min_cz = 0
        self.max_cx = self.max_cz = -1

        # --- Панель: выбор корня / мира / сида
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=8)

        ttk.Label(bar, text="Корень:").pack(side="left")
        ttk.Entry(bar, textvariable=self.root_dir_var, width=40).pack(side="left", padx=4)
        ttk.Button(bar, text="Обзор…", command=self._pick_root).pack(side="left", padx=(0,6))
        ttk.Button(bar, text="Обновить", command=self._refresh_worlds).pack(side="left")

        bar2 = ttk.Frame(self)
        bar2.pack(fill="x", padx=8, pady=(0,8))
        ttk.Label(bar2, text="Мир:").pack(side="left")
        self.world_cb = ttk.Combobox(bar2, textvariable=self.world_var, state="readonly", width=18)
        self.world_cb.pack(side="left", padx=4)
        self.world_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_seeds())

        ttk.Label(bar2, text="Seed:").pack(side="left", padx=(12,0))
        self.seed_cb = ttk.Combobox(bar2, textvariable=self.seed_var, state="readonly", width=18)
        self.seed_cb.pack(side="left", padx=4)
        self.seed_cb.bind("<<ComboboxSelected>>", lambda _e: self._scan())

        # --- Канвас
        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(wrap, background="#eee")
        self.scroll_y = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.scroll_x = ttk.Scrollbar(wrap, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.scroll_y.set, xscrollcommand=self.scroll_x.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scroll_y.grid(row=0, column=1, sticky="ns")
        self.scroll_x.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1); wrap.columnconfigure(0, weight=1)

        # автоинициализация
        self._refresh_worlds()

    # ---------- выборы ----------
    def _pick_root(self):
        p = filedialog.askdirectory(title="Выберите папку artifacts/world")
        if p:
            self.root_dir_var.set(p)
            self._refresh_worlds()

    def _refresh_worlds(self):
        root = pathlib.Path(self.root_dir_var.get())
        worlds: List[str] = []
        if root.exists():
            for p in sorted(root.iterdir()):
                if p.is_dir():
                    worlds.append(p.name)
        self.world_cb["values"] = worlds
        # авто-выбор
        if worlds:
            self.world_var.set(worlds[0])
            self._refresh_seeds()
        else:
            self.world_var.set("")
            self.seed_cb["values"] = []
            self.seed_var.set("")
            self._clear_canvas()

    def _refresh_seeds(self):
        root = pathlib.Path(self.root_dir_var.get())
        world = self.world_var.get()
        seeds: List[str] = []
        if world:
            wdir = root / world
            if wdir.exists():
                for p in sorted(wdir.iterdir()):
                    if p.is_dir():
                        seeds.append(p.name)
        self.seed_cb["values"] = seeds
        if seeds:
            self.seed_var.set(seeds[0])
            self._scan()
        else:
            self.seed_var.set("")
            self._clear_canvas()

    # ---------- скан и рендер ----------
    def _scan(self):
        root = pathlib.Path(self.root_dir_var.get())
        world = self.world_var.get()
        seed  = self.seed_var.get()
        if not world or not seed:
            self._clear_canvas()
            return
        base = root / world / seed
        if not base.exists():
            messagebox.showinfo("Галерея", f"Папка не найдена:\n{base}")
            self._clear_canvas()
            return

        items: Dict[Tuple[int,int], pathlib.Path] = {}
        for p in base.iterdir():
            if p.is_dir():
                m = NAME_RE.match(p.name)
                if m:
                    cx = int(m.group("cx")); cz = int(m.group("cz"))
                    items[(cx, cz)] = p
        if not items:
            self._clear_canvas()
            return

        self.items = items
        xs = [cx for (cx, _) in items.keys()]
        zs = [cz for (_, cz) in items.keys()]
        self.min_cx, self.max_cx = min(xs), max(xs)
        self.min_cz, self.max_cz = min(zs), max(zs)

        self._render()

    def _clear_canvas(self):
        self.items = {}
        self.images.clear()
        self.canvas.delete("all")
        self.canvas.configure(scrollregion=(0,0,0,0))

    def _render(self):
        self.canvas.delete("all")
        self.images.clear()

        cols = self.max_cx - self.min_cx + 1
        rows = self.max_cz - self.min_cz + 1
        content_w = MARGIN*2 + (cols-1)*(THUMB+GAP) + THUMB
        content_h = MARGIN*2 + (rows-1)*(THUMB+GAP) + THUMB

        for (cx, cz), folder in self.items.items():
            c = cx - self.min_cx
            r = cz - self.min_cz
            x = MARGIN + c*(THUMB+GAP)
            y = MARGIN + r*(THUMB+GAP)

            img = self._load_preview(folder)
            if img is not None:
                self.canvas.create_image(x, y, anchor="nw", image=img)
                self.images[(cx,cz)] = img
            else:
                self.canvas.create_rectangle(x, y, x+THUMB, y+THUMB, outline="#333", fill="#333")
                self.canvas.create_text(x+THUMB/2, y+THUMB/2, text=f"{cx},{cz}",
                                        fill="#fff", font=("TkDefaultFont", 12, "bold"))

            # подпись под тайлом
            self.canvas.create_text(x+THUMB/2, y+THUMB+10, text=f"{cx},{cz}",
                                    fill="#777", font=("TkDefaultFont", 9))

        self.canvas.configure(scrollregion=(0, 0, content_w, content_h))

    def _load_preview(self, folder: pathlib.Path) -> Optional[tk.PhotoImage]:
        for name in ("preview.png", "preview.jpg", "preview.jpeg"):
            p = folder / name
            if p.exists():
                try:
                    if PIL_OK:
                        im = Image.open(str(p)).convert("RGBA")
                        im.thumbnail((THUMB, THUMB), Image.LANCZOS)
                        return ImageTk.PhotoImage(im)
                    else:
                        ph = tk.PhotoImage(file=str(p))
                        # поджать кратно (на всякий случай)
                        sx = max(1, ph.width()  // THUMB)
                        sy = max(1, ph.height() // THUMB)
                        if sx > 1 or sy > 1:
                            ph = ph.subsample(max(1, sx), max(1, sy))
                        return ph
                except Exception:
                    return None
        return None
