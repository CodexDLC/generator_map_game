# worldgen_ui/tabs/gallery/view.py

from __future__ import annotations
import re, pathlib
import tkinter as tk
from tkinter import ttk, filedialog
from typing import Dict, Tuple, Optional, List

# PIL для нормального ресайза (опционально, но рекомендуется)
try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

# --- НОВЫЕ ПАРАМЕТРЫ СЕТКИ ---
CELL_SIZE = 128 # Фиксированный размер ячейки в пикселях
PADDING = 5  # Отступ внутри ячейки, чтобы картинка не прилипала к краям
MARGIN = 5  # Отступ для всей сетки от краев окна
NAME_RE = re.compile(r"^(?P<cx>-?\d+)_(?P<cz>-?\d+)$")


class GalleryView(ttk.Frame):
    """
    Галерея: artifacts/world/<world_id>/<seed>/<cx>_<cz>/
    Рисует плитки в фиксированной координатной сетке.
    """

    def __init__(self, master, default_root: Optional[str] = None):
        super().__init__(master)
        self.root_dir_var = tk.StringVar(value=default_root or "artifacts/world")
        self.world_var = tk.StringVar(value="")
        self.seed_var = tk.StringVar(value="")

        self.items: Dict[Tuple[int, int], pathlib.Path] = {}
        self.images: Dict[Tuple[int, int], ImageTk.PhotoImage | tk.PhotoImage] = {}

        # --- Панель управления ---
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=8)

        ttk.Label(bar, text="Корень:").pack(side="left")
        ttk.Entry(bar, textvariable=self.root_dir_var, width=40).pack(side="left", padx=4)
        ttk.Button(bar, text="Обзор…", command=self._pick_root).pack(side="left", padx=(0, 6))

        bar2 = ttk.Frame(self)
        bar2.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Label(bar2, text="Мир:").pack(side="left")
        self.world_cb = ttk.Combobox(bar2, textvariable=self.world_var, state="readonly", width=18)
        self.world_cb.pack(side="left", padx=4)
        self.world_cb.bind("<<ComboboxSelected>>", self._on_world_select)

        ttk.Label(bar2, text="Seed:").pack(side="left", padx=(12, 0))
        self.seed_cb = ttk.Combobox(bar2, textvariable=self.seed_var, state="readonly", width=18)
        self.seed_cb.pack(side="left", padx=4)
        self.seed_cb.bind("<<ComboboxSelected>>", self._on_seed_select)

        ttk.Button(bar2, text="Обновить", command=self._scan).pack(side="left", padx=4)

        # --- Канвас для отрисовки ---
        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(wrap, background="#f0f0f0")
        self.scroll_y = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.scroll_x = ttk.Scrollbar(wrap, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.scroll_y.set, xscrollcommand=self.scroll_x.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scroll_y.grid(row=0, column=1, sticky="ns")
        self.scroll_x.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        # Авто-инициализация при запуске
        self.after(100, self._refresh_worlds)

    def _on_world_select(self, *_):
        self._refresh_seeds()

    def _on_seed_select(self, *_):
        self._scan()

    def _pick_root(self):
        p = filedialog.askdirectory(title="Выберите папку artifacts/world")
        if p:
            self.root_dir_var.set(p)
            self._refresh_worlds()

    def _refresh_worlds(self):
        # ... (этот метод без изменений) ...
        root = pathlib.Path(self.root_dir_var.get())
        worlds: List[str] = []
        if root.exists():
            for p in sorted(root.iterdir()):
                if not p.is_dir():
                    continue
                if p.name == "branch":
                    for branch_p in sorted(p.iterdir()):
                        if branch_p.is_dir():
                            worlds.append(f"branch/{branch_p.name}")
                else:
                    worlds.append(p.name)
        self.world_cb["values"] = worlds
        if worlds:
            if not self.world_var.get() in worlds:
                self.world_var.set(worlds[0])
            self._refresh_seeds()
        else:
            self.world_var.set("")
            self.seed_cb["values"] = []
            self.seed_var.set("")
            self._clear_canvas()

    def _refresh_seeds(self):
        # ... (этот метод без изменений) ...
        root = pathlib.Path(self.root_dir_var.get())
        world = self.world_var.get()
        if not world: return
        world_path = root / world
        seeds: List[str] = []
        if world_path.exists():
            for p in sorted(world_path.iterdir()):
                if p.is_dir() and p.name.isdigit():
                    seeds.append(p.name)
        self.seed_cb["values"] = seeds
        if seeds:
            if not self.seed_var.get() in seeds:
                self.seed_var.set(seeds[0])
            self._scan()
        else:
            self.seed_var.set("")
            self._clear_canvas()

    def _scan(self, *_):
        root = pathlib.Path(self.root_dir_var.get())
        world = self.world_var.get()
        seed = self.seed_var.get()

        print("\n--- GALLERY: Starting scan...")  # ЛОГ
        print(f"--- GALLERY: Root='{root}', World='{world}', Seed='{seed}'")  # ЛОГ

        if not world or not seed:
            self._clear_canvas()
            print("--- GALLERY: Scan aborted (no world or seed).")  # ЛОГ
            return

        world_parts = world.split('/')
        base = root.joinpath(*world_parts) / seed
        print(f"--- GALLERY: Scanning base directory: {base}")  # ЛОГ

        if not base.exists():
            self._clear_canvas()
            print(f"!!! LOG: Base directory does not exist.")  # ЛОГ
            return

        items: Dict[Tuple[int, int], pathlib.Path] = {}
        print("--- GALLERY: Iterating directory contents...")  # ЛОГ
        found_items = False
        for p in base.iterdir():
            print(f"--- GALLERY: Found item: '{p.name}'")  # ЛОГ
            if p.is_dir():
                m = NAME_RE.match(p.name)
                if m:
                    found_items = True
                    cx = int(m.group("cx"))
                    cz = int(m.group("cz"))
                    items[(cx, cz)] = p
                    print(f"--- GALLERY: Matched as chunk, coords=({cx},{cz})")  # ЛОГ

        if not found_items:
            print("--- GALLERY: No chunk directories found matching the pattern.")  # ЛОГ

        self.items = items
        self._render()
        print("--- GALLERY: Scan and render finished.")  # ЛОГ

    def _clear_canvas(self):
        self.items = {}
        self.images.clear()
        self.canvas.delete("all")
        self.canvas.configure(scrollregion=(0, 0, 0, 0))

    def _render(self, *_):
        self.canvas.delete("all")
        if not self.items:
            self.canvas.configure(scrollregion=(0, 0, 0, 0))
            return

        xs = [cx for (cx, _) in self.items.keys()]
        zs = [cz for (_, cz) in self.items.keys()]
        min_cx, max_cx = min(xs), max(xs)
        min_cz, max_cz = min(zs), max(zs)

        cols = max_cx - min_cx + 1
        rows = max_cz - min_cz + 1
        content_w = MARGIN * 2 + cols * CELL_SIZE
        content_h = MARGIN * 2 + rows * CELL_SIZE

        img_size = CELL_SIZE - PADDING * 2

        for (cx, cz), folder in self.items.items():
            c = cx - min_cx
            r = cz - min_cz

            # Координаты ячейки
            x0 = MARGIN + c * CELL_SIZE
            y0 = MARGIN + r * CELL_SIZE

            # Координаты картинки внутри ячейки
            img_x = x0 + PADDING
            img_y = y0 + PADDING

            img_obj = self._load_preview(folder, img_size)
            if img_obj is not None:
                self.canvas.create_image(img_x, img_y, anchor="nw", image=img_obj)
                self.images[(cx, cz)] = img_obj
            else:
                self.canvas.create_rectangle(img_x, img_y, img_x + img_size, img_y + img_size,
                                             outline="#ccc", fill="#eee")
                self.canvas.create_text(img_x + img_size / 2, img_y + img_size / 2, text=f"{cx},{cz}",
                                        fill="#aaa", font=("TkDefaultFont", 10, "bold"))

            # Подпись под ячейкой
            self.canvas.create_text(x0 + CELL_SIZE / 2, y0 + CELL_SIZE - 4, text=f"{cx},{cz}",
                                    fill="#555", font=("TkDefaultFont", 8), anchor="s")

        self.canvas.configure(scrollregion=(0, 0, content_w, content_h))

    def _load_preview(self, folder: pathlib.Path, size: int) -> Optional[tk.PhotoImage | ImageTk.PhotoImage]:
        for name in ("preview.png", "preview.jpg", "preview.jpeg"):
            p = folder / name
            if p.exists():
                print(f"--- GALLERY: Loading preview image: {p}") # ЛОГ
                try:
                    # Основной, правильный способ с Pillow
                    if PIL_OK:
                        im = Image.open(str(p)).convert("RGBA")
                        # .thumbnail сохраняет пропорции, убедимся что она растянется до нужного размера
                        im.thumbnail((size, size), Image.Resampling.LANCZOS)
                        return ImageTk.PhotoImage(im)

                    # <<< УЛУЧШЕННЫЙ ЗАПАСНОЙ ВАРИАНТ >>>
                    else:
                        # Масштабирование без Pillow очень примитивное и НЕ УМЕЕТ УВЕЛИЧИВАТЬ
                        ph = tk.PhotoImage(file=str(p))

                        # Если просим размер больше, а Pillow нет - возвращаем как есть
                        if size > ph.width() or size > ph.height():
                            return ph

                            # Уменьшаем, если нужно (старая логика)
                        sx = max(1, ph.width() // size)
                        sy = max(1, ph.height() // size)
                        if sx > 1 or sy > 1:
                            ph = ph.subsample(sx, sy)
                        return ph

                except Exception:
                    # В случае ошибки при обработке файла, вернем None
                    return None
        return None