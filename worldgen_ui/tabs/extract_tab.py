import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import json
import math
from PIL import Image, ImageTk

from ..widgets.tooltip import tip
from worldgen_core.pipeline import detail_world_chunk, detail_entire_world
from ..utils.run_bg import run_bg


class ExtractTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        pad = {"padx": 6, "pady": 4}

        # --- Настройки ---
        settings_frame = ttk.LabelFrame(self, text="Настройки детализации")
        settings_frame.pack(side="top", fill="x", padx=pad['padx'], pady=pad['pady'])
        self.detail_scale = tk.StringVar(value="150")
        self.detail_strength = tk.StringVar(value="0.25")
        self.upscale_factor = tk.StringVar(value="4")
        l_ds = ttk.Label(settings_frame, text="Масштаб деталей:")
        l_ds.grid(row=0, column=0, sticky="w", **pad)
        e_ds = ttk.Entry(settings_frame, textvariable=self.detail_scale, width=10)
        e_ds.grid(row=0, column=1, sticky="w", **pad)
        tip(l_ds,
            "Задает 'размер' мелких деталей (холмы, овраги).\nМЕНЬШЕ (50-100) = частые, мелкие детали.\nБОЛЬШЕ (300+) = более крупные, пологие детали.")
        l_str = ttk.Label(settings_frame, text="Сила деталей:")
        l_str.grid(row=0, column=2, sticky="w", **pad)
        e_str = ttk.Entry(settings_frame, textvariable=self.detail_strength, width=10)
        e_str.grid(row=0, column=3, sticky="w", **pad)
        tip(l_str, "Насколько сильно детали влияют на основной рельеф (от 0.0 до 1.0).\nРекомендуется: 0.1-0.25.")
        l_up = ttk.Label(settings_frame, text="Увеличение x:")
        l_up.grid(row=0, column=4, sticky="w", **pad)
        e_up = ttk.Entry(settings_frame, textvariable=self.upscale_factor, width=10)
        e_up.grid(row=0, column=5, sticky="w", **pad)
        tip(l_up, "Во сколько раз увеличить разрешение карты.\nНапример, 4 превратит чанк 512x512 в локацию 2048x2048.")
        settings_frame.columnconfigure(6, weight=1)

        # --- Кнопки ---
        button_frame = ttk.Frame(self)
        button_frame.pack(side="top", fill="x", padx=pad['padx'], pady=pad['pady'])
        # ... (код кнопок без изменений)
        self.btn_load = ttk.Button(button_frame, text="Загрузить мир...", command=self._load_world)
        self.btn_load.pack(side="left", **pad)
        tip(self.btn_load, "Выбрать папку с ранее сгенерированным миром (например, out/demo/v2025...).")
        self.btn_detail_all = ttk.Button(button_frame, text="Детализировать весь мир", command=self._detail_all,
                                         state="disabled")
        self.btn_detail_all.pack(side="left", **pad)
        tip(self.btn_detail_all,
            "Применить настройки ко ВСЕМ чанкам мира и сохранить результат в новую папку.\nЭто может занять много времени!")
        self.btn_help = ttk.Button(button_frame, text="Помощь", command=self._show_help)
        self.btn_help.pack(side="left", **pad)
        self.status_label = ttk.Label(button_frame, text="<- Загрузите мир для начала работы")
        self.status_label.pack(side="left", **pad)

        # --- Контейнер для центрирования ---
        self.grid_container = ttk.Frame(self)
        self.grid_container.pack(side="top", fill="both", expand=True, **pad)
        self.grid_container.grid_rowconfigure(0, weight=1)
        self.grid_container.grid_columnconfigure(0, weight=1)

        self.grid_frame = ttk.Frame(self.grid_container)
        self.grid_frame.grid(row=0, column=0)

        self.loaded_path = None
        self.meta = {}
        self.chunk_widgets = {}
        self.photos = []

        # --- Переменная для "умного" обновления ---
        self._resize_job_id = None
        self.bind("<Configure>", self._on_resize)

    def _load_world(self):
        dir_path = filedialog.askdirectory(title="Выберите папку с версией мира (напр. v2025...)")
        if not dir_path: return
        world_path = Path(dir_path)
        meta_path = world_path / "metadata.json"
        if not meta_path.is_file():
            messagebox.showerror("Ошибка", f"Файл 'metadata.json' не найден.")
            return

        with open(meta_path, 'r', encoding='utf-8') as f:
            self.meta = json.load(f)
        self.loaded_path = world_path

        self._build_grid_structure()
        self._update_grid_images()

        self.btn_detail_all.config(state="normal")
        self.status_label.config(text=f"Загружен мир: {world_path.parent.name}/{world_path.name}")

    def _build_grid_structure(self):
        """Создает ячейки сетки ОДИН РАЗ."""
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        self.chunk_widgets.clear()

        cols = math.ceil(self.meta.get("width", 1) / self.meta.get("chunk_size", 512))
        rows = math.ceil(self.meta.get("height", 1) / self.meta.get("chunk_size", 512))

        for r in range(rows):
            for c in range(cols):
                label = ttk.Label(self.grid_frame, relief="solid", anchor="center")
                label.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
                label.bind("<Button-1>", lambda e, cx=c, cy=r: self._on_chunk_click(cx, cy))
                self.chunk_widgets[(c, r)] = label

    def _on_resize(self, event=None):
        """Вызывает обновление картинок с задержкой, чтобы избежать артефактов."""
        if self._resize_job_id:
            self.after_cancel(self._resize_job_id)
        # Ждем 250 мс после последнего изменения размера, и только потом обновляем
        self._resize_job_id = self.after(250, self._update_grid_images)

    def _update_grid_images(self):
        """Обновляет картинки в ячейках, подгоняя их под оптимальный размер."""
        if not self.chunk_widgets or not self.loaded_path: return

        container_w = self.grid_container.winfo_width()
        container_h = self.grid_container.winfo_height()
        if container_w <= 1 or container_h <= 1: return

        cols = len(self.grid_frame.grid_slaves(row=0))
        rows = len(self.grid_frame.grid_slaves(column=0))
        if cols == 0 or rows == 0: return

        # Рассчитываем оптимальный размер ячейки, чтобы вся сетка была квадратной
        cell_size = int(min(container_w / cols, container_h / rows))
        if cell_size <= 4: return

        self.photos.clear()
        biome_path = self.loaded_path / "biome"
        for (c, r), label in self.chunk_widgets.items():
            chunk_img_path = biome_path / f"chunk_{c}_{r}.png"
            if chunk_img_path.is_file():
                try:
                    img = Image.open(chunk_img_path)
                    img.thumbnail((cell_size - 2, cell_size - 2), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.photos.append(photo)
                    label.config(image=photo)
                except Exception as e:
                    print(f"Ошибка обновления превью для чанка {c},{r}: {e}")

    def _on_chunk_click(self, cx, cy):
        if not self.loaded_path: return
        try:
            scale = float(self.detail_scale.get())
            strength = float(self.detail_strength.get())
            upscale = int(self.upscale_factor.get())
            out_dir = self.loaded_path.parent / f"{self.loaded_path.name}_detailed"
            self.status_label.config(text=f"Детализация чанка ({cx},{cy})...")
            self.btn_load.config(state="disabled")
            self.btn_detail_all.config(state="disabled")
            self.btn_help.config(state="disabled")

            def job():
                return detail_world_chunk(self.loaded_path, out_dir, cx, cy, upscale, scale, strength)

            def done(result_path):
                if result_path:
                    self.status_label.config(text=f"Чанк сохранен в: {result_path}")
                    messagebox.showinfo("Готово", f"Детализированный чанк ({cx},{cy}) сохранен в:\n{result_path}")
                self.btn_load.config(state="normal")
                self.btn_detail_all.config(state="normal")
                self.btn_help.config(state="normal")

            run_bg(job, on_done=done, master_widget=self)
        except ValueError:
            messagebox.showerror("Ошибка", "Проверьте, что в настройках детализации указаны правильные числа.")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")
            self.btn_load.config(state="normal")
            self.btn_detail_all.config(state="normal")
            self.btn_help.config(state="normal")

    def _detail_all(self):
        if not self.loaded_path: return
        try:
            scale = float(self.detail_scale.get())
            strength = float(self.detail_strength.get())
            upscale = int(self.upscale_factor.get())
            out_dir = self.loaded_path.parent / f"{self.loaded_path.name}_detailed_x{upscale}"
            if out_dir.exists():
                if not messagebox.askyesno("Папка существует", f"Папка '{out_dir.name}' уже существует. Перезаписать?"):
                    return
            self.btn_load.config(state="disabled")
            self.btn_detail_all.config(state="disabled")
            self.btn_help.config(state="disabled")

            def job():
                return detail_entire_world(self.loaded_path, out_dir, upscale, scale, strength,
                                           on_progress=lambda k, t, msg: self.status_label.config(
                                               text=f"Прогресс: {k}/{t} - {msg}"))

            def done(result_path):
                if result_path:
                    messagebox.showinfo("Готово", f"Детализированный мир сохранен в:\n{result_path}")
                self.btn_load.config(state="normal")
                self.btn_detail_all.config(state="normal")
                self.btn_help.config(state="normal")

            run_bg(job, on_done=done, master_widget=self)
        except ValueError:
            messagebox.showerror("Ошибка", "Проверьте, что в настройках детализации указаны правильные числа.")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")
            self.btn_load.config(state="normal")
            self.btn_detail_all.config(state="normal")
            self.btn_help.config(state="normal")

    def _show_help(self):
        # (Код этой функции остается без изменений)
        win = tk.Toplevel(self)
        win.title("Справка: Этап 2 - Детализация мира")
        win.geometry("650x500")
        text_widget = tk.Text(win, wrap="word", padx=10, pady=10, relief="flat", background="#f0f0f0")
        text_widget.pack(expand=True, fill="both")
        text_widget.tag_configure("h1", font=("TkDefaultFont", 14, "bold"), spacing3=10)
        text_widget.tag_configure("h2", font=("TkDefaultFont", 11, "bold"), spacing1=10, spacing3=5)
        text_widget.tag_configure("p", lmargin1=10, lmargin2=10)
        help_text = [
            ("h1", "Этап 2: Превращение карты в локацию"),
            ("p",
             "Этот режим берет 'черновик' мира, созданный на вкладке 'Generate', и добавляет к нему мелкие детали, превращая его в высокодетализированную карту, готовую для импорта в игровой движок."),
            ("h2", "Рабочий процесс:"),
            ("p", "1. Нажмите 'Загрузить мир...' и выберите папку с версией мира (например, 'v2025...').\n"
                  "2. Настройте параметры детализации сверху.\n"
                  "3. Нажмите на любой чанк в сетке, чтобы детализировать только его, или на кнопку 'Детализировать весь мир' для обработки всей карты."),
            ("h2", "Ключевые параметры детализации:"),
            ("h2", "Масштаб деталей (Detail Scale)"),
            ("p",
             "Определяет 'размер' мелких неровностей (холмов, дюн). МЕНЬШЕ (50-100) = частые, острые детали. БОЛЬШЕ (300+) = плавные, пологие холмы."),
            ("h2", "Увеличение (Upscale Factor)"),
            ("p",
             "Во сколько раз увеличить разрешение. Значение '4' превратит чанк 512x512 в игровую локацию размером 2048x2048 пикселей."),
        ]
        for tag, content in help_text:
            text_widget.insert("end", content + "\n\n", tag)
        text_widget.configure(state="disabled")