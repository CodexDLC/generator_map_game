import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
from ...widgets import GroupBox, row
from .state import GridState


class GridView:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self.state = GridState.create_defaults()
        self._preview_img_ref = None  # Для хранения ссылки на изображение

        # --- Основной контейнер с двумя панелями ---
        pw = ttk.Panedwindow(self.frame, orient="horizontal")
        pw.pack(fill="both", expand=True)

        # === ЛЕВАЯ ПАНЕЛЬ: Настройки ===
        left_panel = ttk.Frame(pw, padding=8)
        pw.add(left_panel, weight=0)

        gb_params = GroupBox(left_panel, text="Параметры локации")
        gb_params.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        row(gb_params, 0, "Seed", self.state.seed)
        row(gb_params, 1, "Width", self.state.width)
        row(gb_params, 2, "Height", self.state.height)

        row(gb_params, 3, "Output dir", self.state.out_dir)
        ttk.Button(gb_params, text="...", width=3,
                   command=lambda: self._browse_out_dir()).grid(row=3, column=2, padx=4)

        # Walls % (рядок 4)
        ttk.Label(gb_params, text="Walls %").grid(row=4, column=0, sticky="w")
        self.scale_walls = ttk.Scale(
            gb_params, from_=0, to=100, orient="horizontal",
            command=lambda v: self.state.wall_chance.set(str(int(float(v))))
        )
        self.scale_walls.set(float(self.state.wall_chance.get()))
        self.scale_walls.grid(row=4, column=1, sticky="ew")
        ttk.Entry(gb_params, width=4, textvariable=self.state.wall_chance).grid(row=4, column=2, sticky="w")

        gb_params.columnconfigure(1, weight=1)


        self.btn_generate = ttk.Button(left_panel, text="Сгенерировать")
        self.btn_generate.grid(row=1, column=0, sticky="ew", padx=5, pady=10)

        self.lbl_status = ttk.Label(left_panel, text="Готово")
        self.lbl_status.grid(row=2, column=0, sticky="w", padx=5, pady=5)

        self.json_label = tk.Label(gb_params, text="", anchor="w", justify="left", wraplength=260)
        self.json_label.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        gb_params.columnconfigure(1, weight=1)  # чтобы тянулся центр. столбец

        # === ПРАВАЯ ПАНЕЛЬ: Превью ===
        right_panel = ttk.Frame(pw, padding=8)
        right_panel.rowconfigure(0, weight=1)
        right_panel.columnconfigure(0, weight=1)
        pw.add(right_panel, weight=1)

        self.preview_label = ttk.Label(right_panel, anchor="center", background="gray20")
        self.preview_label.grid(row=0, column=0, sticky="nsew")

    def set_preview_image(self, image_path: str):
        """Загружает и отображает изображение в области превью."""
        try:
            # Открываем изображение и масштабируем его под размер окна
            img = Image.open(image_path)

            # Получаем размер области для превью
            w, h = self.preview_label.winfo_width(), self.preview_label.winfo_height()
            if w <= 1 or h <= 1:  # Если окно еще не отрисовано, берем дефолтный размер
                w, h = 400, 400

            img.thumbnail((w, h), Image.Resampling.LANCZOS)

            tk_img = ImageTk.PhotoImage(img)

            # Важно: сохраняем ссылку на объект, иначе он будет удален сборщиком мусора
            self._preview_img_ref = tk_img
            self.preview_label.config(image=tk_img)
        except Exception as e:
            self.lbl_status.config(text=f"Ошибка загрузки превью: {e}")
            self._preview_img_ref = None
            self.preview_label.config(image=None)

    def _browse_out_dir(self):
        d = filedialog.askdirectory(initialdir=self.state.out_dir.get() or ".")
        if d:
            self.state.out_dir.set(d)

    def show_json_path(self, path: str):
        self.json_label.config(text=f"JSON: {path}")