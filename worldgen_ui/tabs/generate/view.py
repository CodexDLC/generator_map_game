import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

from ...widgets import GroupBox, row, check
from ...descriptions import HELP, TOOLTIP
from .state import GenerateState


class GenerateView:
    """
    Слева — вертикальная панель настроек.
    Справа — сетка миниатюр чанков + прогресс/статус.
    """
    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self.state = GenerateState.create_defaults()

        # --- help window singleton ---
        self._help_win: tk.Toplevel | None = None

        pw = ttk.Panedwindow(self.frame, orient="horizontal")
        pw.pack(fill="both", expand=True)

        # === ЛЕВЫЙ САЙДБАР ===
        left = ttk.Frame(pw, padding=8)
        left.columnconfigure(0, weight=1)
        pw.add(left, weight=0)

        gb_grid = GroupBox(left, text="Сетка и мир")
        gb_grid.grid(sticky="ew", pady=(0, 8))
        row(gb_grid, 0, "World ID", self.state.world_id)
        row(gb_grid, 1, "Seed", self.state.seed)
        row(gb_grid, 2, "Width (chunks)", self.state.chunks_w)
        row(gb_grid, 3, "Height (chunks)", self.state.chunks_h)
        row(gb_grid, 4, "Chunk Size", self.state.chunk_size, unit="px")

        gb_noise = GroupBox(left, text="Шум")
        gb_noise.grid(sticky="ew", pady=(0, 8))
        row(gb_noise, 0, "Plains Scale", self.state.plains_scale, unit="м")
        row(gb_noise, 1, "Plains Octaves", self.state.plains_oct)
        row(gb_noise, 2, "Mountains Scale", self.state.mount_scale, unit="м")
        row(gb_noise, 3, "Mountains Octaves", self.state.mount_oct)
        row(gb_noise, 4, "Mask Scale", self.state.mask_scale, unit="м")
        row(gb_noise, 5, "Mount Strength", self.state.mount_strength)
        row(gb_noise, 6, "Height Distrib Power", self.state.dist_power)
        row(gb_noise, 7, "Lacunarity", self.state.lacunarity)
        row(gb_noise, 8, "Gain", self.state.gain)

        gb_biome = GroupBox(left, text="Биомы")
        gb_biome.grid(sticky="ew", pady=(0, 8))
        row(gb_biome, 0, "Уровень океана", self.state.ocean_m, unit="м")
        row(gb_biome, 1, "Высота суши", self.state.land_m, unit="м")
        row(gb_biome, 2, "Высота пляжа", self.state.beach_m, unit="м")
        row(gb_biome, 3, "Высота скал", self.state.rock_m, unit="м")
        row(gb_biome, 4, "Высота снега", self.state.snow_m, unit="м")
        row(gb_biome, 5, "Угол склона", self.state.slope_deg, unit="°")
        volcano_box = self.add_volcano_controls(left, self.state)
        volcano_box.grid(sticky="ew", pady=(0, 8))

        gb_exp = GroupBox(left, text="Экспорт")
        gb_exp.grid(sticky="ew")
        check(gb_exp, 0, "Экспорт для Godot Terrain3D", self.state.export_godot)
        row(gb_exp, 1, "Version", self.state.version)

        # Кнопки
        btns = ttk.Frame(left)
        btns.grid(sticky="ew", pady=(10, 0))
        btns.columnconfigure(0, weight=1)
        self.btn_gen = ttk.Button(btns, text="Generate")
        self.btn_gen.grid(row=0, column=0, sticky="ew")
        self.btn_help = ttk.Button(btns, text="?", width=3, command=self.show_help)
        self.btn_help.grid(row=0, column=1, padx=(6, 0))

        # === ПРАВАЯ ПАНЕЛЬ (превью сеткой) ===
        right = ttk.Frame(pw, padding=8)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        pw.add(right, weight=1)

        self.grid_frame = ttk.Frame(right)  # превью чанков
        self.grid_frame.grid(row=0, column=0, sticky="nsew")

        self.prog = ttk.Progressbar(right, mode="determinate")
        self.prog.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.prog.grid_remove()  # скрыт, пока нет генерации

        self.lbl_status = ttk.Label(right, text="Готово.")
        self.lbl_status.grid(row=2, column=0, sticky="w", pady=(4, 0))

        # внутренние структуры для превью
        self._tiles: list[list[ttk.Label]] = []
        self._imgrefs: list[list[ImageTk.PhotoImage | None]] = []
        self._tile_px = 96

    # --- API для контроллера ---

    def init_grid(self, cols: int, rows: int, tile_px: int = 96) -> None:
        for row_lbls in self._tiles:
            for lbl in row_lbls:
                lbl.destroy()
        self._tiles.clear()
        self._imgrefs.clear()

        self._tile_px = tile_px
        for r in range(rows):
            row_lbls = []
            row_refs = []
            for c in range(cols):
                lbl = ttk.Label(self.grid_frame, text="", anchor="center")
                lbl.grid(row=r, column=c, padx=2, pady=2)
                row_lbls.append(lbl)
                row_refs.append(None)
            self._tiles.append(row_lbls)
            self._imgrefs.append(row_refs)

    def set_tile_image(self, cx: int, cy: int, img_path: str) -> None:
        try:
            img = Image.open(img_path)
            img.thumbnail((self._tile_px, self._tile_px))
            tkimg = ImageTk.PhotoImage(img)
            self._imgrefs[cy][cx] = tkimg
            self._tiles[cy][cx].configure(image=tkimg, text="")
        except Exception:
            self._tiles[cy][cx].configure(text="×")

    # --- Справка: один экземпляр ---
    def show_help(self):
        # если уже открыта — просто активируем
        if self._help_win and tk.Toplevel.winfo_exists(self._help_win):
            self._help_win.deiconify()
            self._help_win.lift()
            self._help_win.focus_force()
            return

        win = tk.Toplevel(self.frame)
        win.title("Подсказки по генератору")
        win.geometry("560x640")
        self._help_win = win

        txt = tk.Text(win, wrap="word")
        scr = ttk.Scrollbar(win, command=txt.yview)
        txt.configure(yscrollcommand=scr.set)
        txt.pack(side="left", fill="both", expand=True)
        scr.pack(side="right", fill="y")

        txt.insert("end", HELP.get("generate", ""))
        txt.configure(state="disabled")

        def _on_close():
            # помечаем, что окна больше нет
            self._help_win = None
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)

    @staticmethod
    def _bind_enable(var: tk.BooleanVar, controlled: list[tk.Widget]) -> None:
        def _update(*_):
            state = "normal" if var.get() else "disabled"
            for w in controlled:
                try:
                    w.configure(state=state)
                except tk.TclError:
                    pass

        var.trace_add("write", _update)
        _update()

    @staticmethod
    def add_volcano_controls(parent: ttk.Frame, state) -> ttk.LabelFrame:
        lf = ttk.LabelFrame(parent, text="Вулкан / Остров")
        lf.grid_columnconfigure(1, weight=1)
        row = 0
        chk = ttk.Checkbutton(lf, text="Включить вулкан", variable=state.volcano_enable)
        chk.grid(row=row, column=0, columnspan=2, sticky="w", padx=6, pady=(6, 2));
        row += 1
        ttk.Label(lf, text="Центр X (px):").grid(row=row, column=0, sticky="e", padx=6, pady=2)
        ent_cx = ttk.Entry(lf, textvariable=state.volcano_center_x, width=10)
        ent_cx.grid(row=row, column=1, sticky="w", padx=6, pady=2);
        row += 1
        ttk.Label(lf, text="Центр Y (px):").grid(row=row, column=0, sticky="e", padx=6, pady=2)
        ent_cy = ttk.Entry(lf, textvariable=state.volcano_center_y, width=10)
        ent_cy.grid(row=row, column=1, sticky="w", padx=6, pady=2);
        row += 1
        ttk.Label(lf, text="Пик (м):").grid(row=row, column=0, sticky="e", padx=6, pady=2)
        ent_peak = ttk.Entry(lf, textvariable=state.volcano_peak_m, width=10)
        ent_peak.grid(row=row, column=1, sticky="w", padx=6, pady=2);
        row += 1
        ttk.Label(lf, text="Радиус вулкана (м):").grid(row=row, column=0, sticky="e", padx=6, pady=2)
        ent_rv = ttk.Entry(lf, textvariable=state.volcano_radius_m, width=10)
        ent_rv.grid(row=row, column=1, sticky="w", padx=6, pady=2);
        row += 1
        ttk.Label(lf, text="Радиус кратера (м):").grid(row=row, column=0, sticky="e", padx=6, pady=2)
        ent_rc = ttk.Entry(lf, textvariable=state.crater_radius_m, width=10)
        ent_rc.grid(row=row, column=1, sticky="w", padx=6, pady=2);
        row += 1
        ttk.Label(lf, text="Радиус острова (м):").grid(row=row, column=0, sticky="e", padx=6, pady=2)
        ent_ri = ttk.Entry(lf, textvariable=state.island_radius_m, width=10)
        ent_ri.grid(row=row, column=1, sticky="w", padx=6, pady=2);
        row += 1
        ttk.Label(lf, text="Пояс спада (м):").grid(row=row, column=0, sticky="e", padx=6, pady=2)
        ent_ib = ttk.Entry(lf, textvariable=state.island_band_m, width=10)
        ent_ib.grid(row=row, column=1, sticky="w", padx=6, pady=2);
        row += 1
        ttk.Label(lf, text="Рябь гребней (0..1):").grid(row=row, column=0, sticky="e", padx=6, pady=2)
        ent_ridge = ttk.Entry(lf, textvariable=state.ridge_noise_amp, width=10)
        ent_ridge.grid(row=row, column=1, sticky="w", padx=6, pady=2);
        row += 1

        GenerateView._bind_enable(state.volcano_enable,
                                  [ent_cx, ent_cy, ent_peak, ent_rv, ent_rc, ent_ri, ent_ib, ent_ridge])
        return lf