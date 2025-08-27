import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import json
import math
from PIL import Image, ImageTk

from .ui_utils import create_help_window
from ..widgets.tooltip import tip
from ..descriptions.tooltips import *
from ..descriptions.help_texts import HELP_TEXTS
from worldgen_core.pipeline import detail_world_chunk, detail_entire_world
from ..utils.run_bg import run_bg



class ExtractTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        pad = {"padx": 6, "pady": 4}

        # --- ИЗМЕНЕНИЕ: Система закладок ---
        self.bookmarks_path = Path("world_bookmarks.json")
        self.bookmarks = []
        self.selected_bookmark = tk.StringVar()

        # --- Верхняя панель управления ---
        top_panel = ttk.Frame(self)
        top_panel.pack(side="top", fill="x", **pad)

        # --- Панель закладок (НОВАЯ) ---
        bookmarks_frame = ttk.LabelFrame(top_panel, text="Закладки миров")
        bookmarks_frame.pack(side="left", fill="x", expand=True, **pad)

        self.bookmarks_combo = ttk.Combobox(bookmarks_frame, textvariable=self.selected_bookmark, state="readonly")
        self.bookmarks_combo.pack(side="left", fill="x", expand=True, padx=pad['padx'], pady=2)
        self.bookmarks_combo.bind("<<ComboboxSelected>>", self._on_bookmark_select)

        btn_save_bookmark = ttk.Button(bookmarks_frame, text="Сохранить", command=self._add_current_path_to_bookmarks)
        btn_save_bookmark.pack(side="left", padx=(0, 2))
        btn_del_bookmark = ttk.Button(bookmarks_frame, text="Удалить", command=self._delete_selected_path)
        btn_del_bookmark.pack(side="left")

        self.btn_load = ttk.Button(top_panel, text="Загрузить новый мир...", command=self._load_world)
        self.btn_load.pack(side="left", **pad)
        tip(self.btn_load, EXT_LOAD_WORLD_TIP)

        # --- Панель настроек ---
        settings_frame = ttk.LabelFrame(self, text="Настройки детализации")
        settings_frame.pack(side="top", fill="x", **pad)
        self.detail_scale = tk.StringVar(value="150")
        self.detail_strength = tk.StringVar(value="0.25")
        self.upscale_factor = tk.StringVar(value="4")

        l_ds = ttk.Label(settings_frame, text="Масштаб деталей:")
        l_ds.grid(row=0, column=0, sticky="w", **pad)
        e_ds = ttk.Entry(settings_frame, textvariable=self.detail_scale, width=10)
        e_ds.grid(row=0, column=1, sticky="w", **pad)
        tip(l_ds, EXT_DETAIL_SCALE_TIP)
        l_str = ttk.Label(settings_frame, text="Сила деталей:")
        l_str.grid(row=0, column=2, sticky="w", **pad)
        e_str = ttk.Entry(settings_frame, textvariable=self.detail_strength, width=10)
        e_str.grid(row=0, column=3, sticky="w", **pad)
        tip(l_str, EXT_DETAIL_STRENGTH_TIP)
        l_up = ttk.Label(settings_frame, text="Увеличение x:")
        l_up.grid(row=0, column=4, sticky="w", **pad)
        e_up = ttk.Entry(settings_frame, textvariable=self.upscale_factor, width=10)
        e_up.grid(row=0, column=5, sticky="w", **pad)
        tip(l_up, EXT_UPSCALE_TIP)

        self.btn_detail_all = ttk.Button(settings_frame, text="Детализировать весь мир", command=self._detail_all,
                                         state="disabled")
        self.btn_detail_all.grid(row=0, column=6, sticky="e", **pad)
        tip(self.btn_detail_all, EXT_DETAIL_ALL_TIP)
        settings_frame.columnconfigure(6, weight=1)

        # --- Статус и помощь ---
        status_frame = ttk.Frame(self)
        status_frame.pack(side="top", fill="x", padx=pad['padx'], pady=2)
        self.status_label = ttk.Label(status_frame, text="<- Загрузите или выберите мир для начала работы")
        self.status_label.pack(side="left", **pad)
        self.btn_help = ttk.Button(status_frame, text="Помощь", command=self._show_help)
        self.btn_help.pack(side="right", **pad)

        # --- Контейнер для сетки ---
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

        self._resize_job_id = None
        self.bind("<Configure>", self._on_resize)

        # Загружаем закладки при старте
        self._load_bookmarks()

    # --- Новые функции для работы с закладками ---
    def _load_bookmarks(self):
        if self.bookmarks_path.is_file():
            try:
                with open(self.bookmarks_path, "r", encoding="utf-8") as f:
                    self.bookmarks = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Ошибка загрузки закладок: {e}")
                self.bookmarks = []
        self._update_bookmarks_combo()

    def _save_bookmarks(self):
        try:
            with open(self.bookmarks_path, "w", encoding="utf-8") as f:
                json.dump(self.bookmarks, f, indent=2)
        except IOError as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить закладки:\n{e}")

    def _update_bookmarks_combo(self):
        self.bookmarks_combo['values'] = self.bookmarks
        if not self.bookmarks:
            self.selected_bookmark.set("")

    def _add_current_path_to_bookmarks(self):
        if not self.loaded_path:
            messagebox.showwarning("Внимание", "Сначала загрузите мир, чтобы сохранить путь.")
            return

        path_str = str(self.loaded_path)
        if path_str not in self.bookmarks:
            self.bookmarks.append(path_str)
            self._save_bookmarks()
            self._update_bookmarks_combo()
            self.selected_bookmark.set(path_str)
            messagebox.showinfo("Сохранено", f"Путь сохранен в закладки:\n{path_str}")
        else:
            messagebox.showinfo("Информация", "Этот путь уже есть в закладках.")

    def _delete_selected_path(self):
        selected = self.selected_bookmark.get()
        if not selected:
            messagebox.showwarning("Внимание", "Сначала выберите путь в списке, чтобы удалить.")
            return

        if selected in self.bookmarks:
            if messagebox.askyesno("Удаление", f"Вы уверены, что хотите удалить закладку?\n{selected}"):
                self.bookmarks.remove(selected)
                self._save_bookmarks()
                self._update_bookmarks_combo()

    def _on_bookmark_select(self, event):
        path_str = self.selected_bookmark.get()
        if path_str:
            self._load_world_from_path(Path(path_str))

    # --- Функции загрузки мира ---
    def _load_world(self):
        dir_path = filedialog.askdirectory(title="Выберите папку с версией мира (напр. v2025...)")
        if not dir_path: return

        world_path = Path(dir_path)
        if self._load_world_from_path(world_path):
            # Если мир успешно загружен, добавляем в закладки
            self._add_current_path_to_bookmarks()

    def _load_world_from_path(self, world_path: Path):
        meta_path = world_path / "metadata.json"
        if not meta_path.is_file():
            messagebox.showerror("Ошибка", f"Файл 'metadata.json' не найден.")
            return False

        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                self.meta = json.load(f)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось прочитать metadata.json:\n{e}")
            return False

        self.loaded_path = world_path
        self._build_grid_structure()
        self._update_grid_images()

        self.btn_detail_all.config(state="normal")
        self.status_label.config(text=f"Загружен мир: {world_path.parent.name}/{world_path.name}")

        # Обновляем комбобокс, если этого пути там еще нет
        if str(world_path) not in self.bookmarks:
            self.selected_bookmark.set(str(world_path))
        return True

    # ... (остальные функции: _build_grid_structure, _on_resize, etc. остаются без изменений) ...
    def _build_grid_structure(self):
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
        if self._resize_job_id:
            self.after_cancel(self._resize_job_id)
        self._resize_job_id = self.after(250, self._update_grid_images)

    def _update_grid_images(self):
        if not self.chunk_widgets or not self.loaded_path: return
        container_w = self.grid_container.winfo_width()
        container_h = self.grid_container.winfo_height()
        if container_w <= 1 or container_h <= 1: return
        cols = len(self.grid_frame.grid_slaves(row=0))
        rows = len(self.grid_frame.grid_slaves(column=0))
        if cols == 0 or rows == 0: return
        cell_size = int(min(container_w / cols, container_h / rows))
        if cell_size <= 4: return
        self.photos.clear()

        for (c, r), label in self.chunk_widgets.items():
            chunk_img_path = self.loaded_path / f"chunk_{c}_{r}" / "biome.png"
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
            self.btn_load.config(state="normal")
            self.btn_detail_all.config(state="normal")
            self.btn_help.config(state="normal")
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
            self.btn_load.config(state="normal")
            self.btn_detail_all.config(state="normal")
            self.btn_help.config(state="normal")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")
            self.btn_load.config(state="normal")
            self.btn_detail_all.config(state="normal")
            self.btn_help.config(state="normal")

    def _show_help(self):
        create_help_window(
            parent=self,
            title="Справка: Этап 2 - Детализация мира",
            help_content=HELP_TEXTS["extract"]
        )