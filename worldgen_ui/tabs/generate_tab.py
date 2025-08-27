import tkinter as tk
from tkinter import ttk, filedialog, messagebox, TclError
from datetime import datetime
from pathlib import Path
import queue
import math
from dataclasses import dataclass
import os

from PIL import Image, ImageTk

from setting.config import GenConfig, BiomeConfig
from worldgen_core.pipeline import generate_world
from .ui_utils import create_help_window
from ..utils.run_bg import run_bg
from ..widgets.tooltip import tip
from ..descriptions.tooltips import *
from ..descriptions.help_texts import HELP_TEXTS


def _ts_version() -> str:
    """Генерирует строку версии на основе текущей временной метки."""
    return "v" + datetime.now().strftime("%Y%m%d_%H%M%S")


@dataclass
class GenerateTabState:
    """Хранит все переменные tkinter для вкладки генерации."""
    out_dir: tk.StringVar
    world_id: tk.StringVar
    seed: tk.StringVar
    width_chunks: tk.StringVar
    height_chunks: tk.StringVar
    chunk_size: tk.StringVar
    chunk_info: tk.StringVar
    plains_scale: tk.StringVar
    plains_octaves: tk.StringVar
    mountains_scale: tk.StringVar
    mountains_octaves: tk.StringVar
    mask_scale: tk.StringVar
    mountain_strength: tk.StringVar
    height_distribution_power: tk.StringVar
    lacunarity: tk.StringVar
    gain: tk.StringVar
    ocean_level_m: tk.StringVar
    land_height_m: tk.StringVar
    beach_height_m: tk.StringVar
    rock_height_m: tk.StringVar
    snow_height_m: tk.StringVar
    max_grass_slope_deg: tk.StringVar
    auto_version: tk.IntVar
    version: tk.StringVar
    export_godot: tk.IntVar


class GenerateTab(ttk.Frame):
    def __init__(self, master):
        """
        Инициализирует вкладку 'Генерация'.

        Args:
            master: Родительский виджет.
        """
        super().__init__(master)
        self.pad = {"padx": 6, "pady": 4}

        self.state = self._create_initial_state()
        self.update_queue = queue.Queue()
        self.photos = []

        self._build_ui()
        self._update_chunk_info()

    def _create_initial_state(self) -> GenerateTabState:
        """
        Инициализирует и возвращает объект состояния с значениями по умолчанию.

        Returns:
            GenerateTabState: Объект состояния с начальными значениями.
        """
        cfg = GenConfig()

        state = GenerateTabState(
            out_dir=tk.StringVar(value=str(Path(cfg.out_dir).resolve())),
            world_id=tk.StringVar(value=cfg.world_id),
            seed=tk.StringVar(value=str(cfg.seed)),
            width_chunks=tk.StringVar(value=str(cfg.width // cfg.chunk)),
            height_chunks=tk.StringVar(value=str(cfg.height // cfg.chunk)),
            chunk_size=tk.StringVar(value=str(cfg.chunk)),
            chunk_info=tk.StringVar(value=""),
            plains_scale=tk.StringVar(value=str(cfg.plains_scale)),
            plains_octaves=tk.StringVar(value=str(cfg.plains_octaves)),
            mountains_scale=tk.StringVar(value=str(cfg.mountains_scale)),
            mountains_octaves=tk.StringVar(value=str(cfg.mountains_octaves)),
            mask_scale=tk.StringVar(value=str(cfg.mask_scale)),
            mountain_strength=tk.StringVar(value=str(cfg.mountain_strength)),
            height_distribution_power=tk.StringVar(value=str(cfg.height_distribution_power)),
            lacunarity=tk.StringVar(value=str(cfg.lacunarity)),
            gain=tk.StringVar(value=str(cfg.gain)),
            ocean_level_m=tk.StringVar(value=str(cfg.biome_config.ocean_level_m)),
            land_height_m=tk.StringVar(value=str(cfg.land_height_m)),
            beach_height_m=tk.StringVar(value=str(cfg.biome_config.beach_height_m)),
            rock_height_m=tk.StringVar(value=str(cfg.biome_config.rock_height_m)),
            snow_height_m=tk.StringVar(value=str(cfg.biome_config.snow_height_m)),
            max_grass_slope_deg=tk.StringVar(value=str(cfg.biome_config.max_grass_slope_deg)),
            auto_version=tk.IntVar(value=1),
            version=tk.StringVar(value=cfg.version),
            export_godot=tk.IntVar(value=int(cfg.export_for_godot))
        )

        state.width_chunks.trace_add("write", self._update_chunk_info)
        state.height_chunks.trace_add("write", self._update_chunk_info)

        return state

    def _build_ui(self):
        """Создает и размещает все виджеты пользовательского интерфейса на вкладке."""
        main_frame = ttk.Frame(self)
        main_frame.pack(side="top", fill="x", expand=False)

        r = 0

        ttk.Label(main_frame, text="* World ID:").grid(row=r, column=0, sticky="w", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.world_id).grid(row=r, column=1, sticky="we", **self.pad)
        ttk.Label(main_frame, text="* Seed:").grid(row=r, column=2, sticky="e", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.seed, width=12).grid(row=r, column=3, sticky="we", **self.pad);
        r += 1

        ttk.Label(main_frame, text="* Width (chunks):").grid(row=r, column=0, sticky="w", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.width_chunks).grid(row=r, column=1, sticky="we", **self.pad)
        ttk.Label(main_frame, text="* Height (chunks):").grid(row=r, column=2, sticky="e", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.height_chunks).grid(row=r, column=3, sticky="we", **self.pad);
        r += 1

        ttk.Label(main_frame, text="Chunk Size:").grid(row=r, column=0, sticky="w", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.chunk_size).grid(row=r, column=1, sticky="we", **self.pad)
        ttk.Label(main_frame, textvariable=self.state.chunk_info).grid(row=r, column=2, columnspan=2, sticky="w",
                                                                       **self.pad);
        r += 1

        ttk.Separator(main_frame).grid(row=r, column=0, columnspan=4, sticky="ew", pady=5);
        r += 1

        ttk.Label(main_frame, text="Равнины Scale:").grid(row=r, column=0, sticky="w", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.plains_scale).grid(row=r, column=1, sticky="we", **self.pad)
        ttk.Label(main_frame, text="Равнины Octaves:").grid(row=r, column=2, sticky="e", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.plains_octaves).grid(row=r, column=3, sticky="we", **self.pad);
        r += 1

        ttk.Label(main_frame, text="Горы Scale:").grid(row=r, column=0, sticky="w", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.mountains_scale).grid(row=r, column=1, sticky="we", **self.pad)
        ttk.Label(main_frame, text="Горы Octaves:").grid(row=r, column=2, sticky="e", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.mountains_octaves).grid(row=r, column=3, sticky="we", **self.pad);
        r += 1

        ttk.Label(main_frame, text="Маска гор Scale:").grid(row=r, column=0, sticky="w", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.mask_scale).grid(row=r, column=1, columnspan=3, sticky="we",
                                                                       **self.pad);
        r += 1

        ttk.Label(main_frame, text="Сила гор:").grid(row=r, column=0, sticky="w", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.mountain_strength).grid(row=r, column=1, sticky="we", **self.pad)
        r += 1

        ttk.Label(main_frame, text="Распределение высот:").grid(row=r, column=0, sticky="w", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.height_distribution_power).grid(row=r, column=1, sticky="we",
                                                                                      **self.pad);
        r += 1

        ttk.Label(main_frame, text="Lacunarity:").grid(row=r, column=0, sticky="w", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.lacunarity).grid(row=r, column=1, sticky="we", **self.pad)
        ttk.Label(main_frame, text="Gain:").grid(row=r, column=2, sticky="e", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.gain).grid(row=r, column=3, sticky="we", **self.pad);
        r += 1

        ttk.Separator(main_frame).grid(row=r, column=0, columnspan=4, sticky="ew", pady=5);
        r += 1

        ttk.Label(main_frame, text="Уровень океана (м):").grid(row=r, column=0, sticky="w", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.ocean_level_m).grid(row=r, column=1, sticky="we", **self.pad)
        ttk.Label(main_frame, text="Высота суши (м):").grid(row=r, column=2, sticky="e", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.land_height_m).grid(row=r, column=3, sticky="we", **self.pad);
        r += 1

        ttk.Label(main_frame, text="Высота пляжа (м):").grid(row=r, column=0, sticky="w", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.beach_height_m).grid(row=r, column=1, sticky="we", **self.pad)
        ttk.Label(main_frame, text="Высота скал (м):").grid(row=r, column=2, sticky="e", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.rock_height_m).grid(row=r, column=3, sticky="we", **self.pad);
        r += 1

        ttk.Label(main_frame, text="Высота снега (м):").grid(row=r, column=0, sticky="w", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.snow_height_m).grid(row=r, column=1, sticky="we", **self.pad)
        ttk.Label(main_frame, text="Угол склона (град):").grid(row=r, column=2, sticky="e", **self.pad)
        ttk.Entry(main_frame, textvariable=self.state.max_grass_slope_deg).grid(row=r, column=3, sticky="we",
                                                                                **self.pad);
        r += 1

        ttk.Separator(main_frame).grid(row=r, column=0, columnspan=4, sticky="ew", pady=5);
        r += 1

        ttk.Checkbutton(main_frame, text="Экспорт для Godot Terrain3D", variable=self.state.export_godot).grid(row=r,
                                                                                                               column=0,
                                                                                                               columnspan=2,
                                                                                                               sticky="w",
                                                                                                               **self.pad);
        r += 1

        cb_ts = ttk.Checkbutton(main_frame, text="Новая папка версии (timestamp)", variable=self.state.auto_version,
                                command=self._toggle_version)
        cb_ts.grid(row=r, column=0, columnspan=2, sticky="w", **self.pad)
        ttk.Label(main_frame, text="Version:").grid(row=r, column=2, sticky="e", **self.pad)
        self.e_version = ttk.Entry(main_frame, textvariable=self.state.version)
        self.e_version.grid(row=r, column=3, sticky="we", **self.pad);
        r += 1
        self._toggle_version()

        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=r, column=0, columnspan=4, sticky="we")
        self.btn = ttk.Button(btn_frame, text="Generate", command=self._run)
        self.btn.pack(side="left", expand=True, fill="x", **self.pad)
        self.help_btn = ttk.Button(btn_frame, text="Помощь", command=self._show_help)
        self.help_btn.pack(side="left", fill="x", padx=self.pad['padx'], pady=self.pad['pady']);
        r += 1

        self.status = tk.StringVar(value="Готово")
        ttk.Label(main_frame, textvariable=self.status).grid(row=r, column=0, columnspan=4, sticky="w", **self.pad)

        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(3, weight=1)

        preview_outer_frame = ttk.Frame(self)
        preview_outer_frame.pack(side="bottom", fill="both", expand=True, **self.pad)

        self.canvas = tk.Canvas(preview_outer_frame)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        v_scroll = ttk.Scrollbar(preview_outer_frame, orient="vertical", command=self.canvas.yview)
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll = ttk.Scrollbar(preview_outer_frame, orient="horizontal", command=self.canvas.xview)
        h_scroll.grid(row=1, column=0, sticky="ew")

        self.canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        preview_outer_frame.grid_rowconfigure(0, weight=1)
        preview_outer_frame.grid_columnconfigure(0, weight=1)

        self.grid_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")

        self.grid_frame.bind("<Configure>", self._on_frame_configure)

        self.chunk_labels = {}

    def _on_frame_configure(self, event):
        """
        Обновляет область прокрутки Canvas при изменении размера grid_frame.

        Args:
            event: Событие Configure.
        """
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _update_chunk_info(self, *args):
        """
        Пересчитывает и отображает информацию об общем количестве чанков и проходов.

        Вызывается при изменении полей ввода ширины или высоты.
        Обновляет текстовую метку с информацией о количестве чанков и потоков.
        """
        try:
            width = int(self.state.width_chunks.get())
            height = int(self.state.height_chunks.get())

            if width <= 0 or height <= 0:
                self.state.chunk_info.set("Неверный размер")
                return

            total_chunks = width * height
            num_processes = max(1, os.cpu_count() - 2)
            batches = math.ceil(total_chunks / num_processes)

            info_text = f"Всего чанков: {total_chunks} ({batches} проходов по {num_processes} потоков)"
            self.state.chunk_info.set(info_text)

        except (ValueError, TclError):
            self.state.chunk_info.set("Введите числа")

    def _build_config_from_state(self) -> GenConfig:
        """
        Собирает объект GenConfig из текущего состояния полей ввода в UI.

        Returns:
            GenConfig: Сконфигурированный объект для генерации мира.
        """
        out = Path(self.state.out_dir.get()).resolve()
        world = self.state.world_id.get().strip()
        version = _ts_version() if self.state.auto_version.get() else (self.state.version.get().strip() or "v1")

        chunk_size = int(self.state.chunk_size.get())
        width_val = int(self.state.width_chunks.get()) * chunk_size
        height_val = int(self.state.height_chunks.get()) * chunk_size

        biome_config = BiomeConfig(
            ocean_level_m=float(self.state.ocean_level_m.get()),
            beach_height_m=float(self.state.beach_height_m.get()),
            rock_height_m=float(self.state.rock_height_m.get()),
            snow_height_m=float(self.state.snow_height_m.get()),
            max_grass_slope_deg=float(self.state.max_grass_slope_deg.get())
        )

        return GenConfig(
            out_dir=str(out), world_id=world, version=version,
            seed=int(self.state.seed.get()),
            width=width_val, height=height_val,
            chunk=chunk_size,
            plains_scale=float(self.state.plains_scale.get()),
            plains_octaves=int(self.state.plains_octaves.get()),
            mountains_scale=float(self.state.mountains_scale.get()),
            mountains_octaves=int(self.state.mountains_octaves.get()),
            mask_scale=float(self.state.mask_scale.get()),
            mountain_strength=float(self.state.mountain_strength.get()),
            height_distribution_power=float(self.state.height_distribution_power.get()),
            lacunarity=float(self.state.lacunarity.get()),
            gain=float(self.state.gain.get()),
            with_biomes=True,
            land_height_m=float(self.state.land_height_m.get()),
            export_for_godot=bool(self.state.export_godot.get()),
            biome_config=biome_config
        )

    def _run(self):
        """
        Запускает процесс генерации мира.

        Собирает конфигурацию, проверяет ее, подготавливает UI и запускает генерацию в фоновом потоке.
        """
        try:
            cfg = self._build_config_from_state()
            cfg.validate()

            self._prepare_grid(cfg.width, cfg.height, cfg.chunk)
            self.btn.configure(state="disabled")
            self.help_btn.configure(state="disabled")
            self.status.set("Генерация...")
            self.after(100, self._process_queue)

            def job():
                generate_world(cfg, update_queue=self.update_queue)

            def done(result):
                self.btn.configure(state="normal")
                self.help_btn.configure(state="normal")
                full_path = Path(cfg.out_dir) / cfg.world_id / cfg.version
                self.status.set(f"Готово: {full_path}")
                messagebox.showinfo("OK", f"Готово: {full_path}")

            run_bg(job, on_done=done, master_widget=self)
        except (ValueError, Exception) as e:
            self.btn.configure(state="normal")
            self.help_btn.configure(state="normal")
            messagebox.showerror("Ошибка", str(e))

    def _prepare_grid(self, width, height, chunk_size):
        """
        Очищает и пересоздает сетку для предварительного просмотра сгенерированных чанков.

        Args:
            width (int): Общая ширина карты в пикселях.
            height (int): Общая высота карты в пикселях.
            chunk_size (int): Размер одного чанка в пикселях.
        """
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        self.chunk_labels.clear()
        self.photos.clear()
        cols = math.ceil(width / chunk_size)
        rows = math.ceil(height / chunk_size)
        for r in range(rows):
            for c in range(cols):
                wrapper = ttk.Frame(self.grid_frame, width=128, height=128)
                wrapper.grid(row=r, column=c, padx=1, pady=1)
                wrapper.grid_propagate(False)
                label = ttk.Label(wrapper, text=f"{c},{r}", relief="solid", anchor="center")
                label.pack(expand=True, fill="both")
                self.chunk_labels[(c, r)] = label

    def _process_queue(self):
        """
        Обрабатывает очередь обновлений от фонового потока генерации.

        Периодически проверяет очередь на наличие новых сообщений (например, изображений чанков) и обновляет UI.
        """
        try:
            while not self.update_queue.empty():
                msg = self.update_queue.get_nowait()
                if msg is None: continue

                cx, cy, img_data = msg
                if cx == "done":
                    return
                if (cx, cy) in self.chunk_labels:
                    label = self.chunk_labels[(cx, cy)]
                    img = Image.fromarray(img_data)
                    img.thumbnail((128, 128), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.photos.append(photo)
                    label.config(image=photo, text="")
        finally:
            self.after(100, self._process_queue)

    def _show_help(self):
        """Отображает окно справки для вкладки генерации."""
        create_help_window(
            parent=self,
            title="Справка: Этап 1 - Генерация мира",
            help_content=HELP_TEXTS["generate"]
        )

    def _toggle_version(self):
        """Переключает состояние поля ввода версии (активно/неактивно) в зависимости от чекбокса 'Новая папка версии'."""
        self.e_version.configure(state=("disabled" if self.state.auto_version.get() else "normal"))

    def _choose_out(self):
        """Открывает диалоговое окно для выбора папки вывода."""
        d = filedialog.askdirectory(title="Выбери папку вывода")
        if d: self.state.out_dir.set(d)