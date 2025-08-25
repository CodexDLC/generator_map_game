import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path
import queue
import math
from PIL import Image, ImageTk

from setting.config import GenConfig
from worldgen_core.pipeline import generate_world
from ..utils.run_bg import run_bg
from ..widgets.tooltip import tip
from ..descriptions.tooltips import *
from ..descriptions.help_texts import HELP_TEXTS


def _ts_version() -> str: return "v" + datetime.now().strftime("%Y%m%d_%H%M%S")


class GenerateTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        pad = {"padx": 6, "pady": 4}

        # --- Переменные ---
        self.out = tk.StringVar(value=str(Path("./out").resolve()))
        self.world = tk.StringVar(value="demo")
        self.seed = tk.StringVar(value="12345")
        self.width = tk.StringVar(value="2")
        self.height = tk.StringVar(value="2")
        self.chunk = tk.StringVar(value="512")
        self.scale = tk.StringVar(value="600")
        self.oct = tk.StringVar(value="6")
        self.lac = tk.StringVar(value="2.0")
        self.gain = tk.StringVar(value="0.5")
        self.biomes = tk.IntVar(value=1)
        self.ocean = tk.StringVar(value="0.12")
        self.land_height = tk.StringVar(value="500")
        self.inland = tk.IntVar(value=1)
        self.edge_boost = tk.StringVar(value="0.25")
        self.edge_margin = tk.StringVar(value="0.12")
        self.auto_ver = tk.IntVar(value=1)
        self.version = tk.StringVar(value="v1")
        self.export_godot = tk.IntVar(value=0)
        self.flat_edges = tk.IntVar(value=0)

        r = 0
        l_out = ttk.Label(self, text="* Output dir:")
        l_out.grid(row=r, column=0, sticky="w", **pad)
        e_out = ttk.Entry(self, textvariable=self.out)
        e_out.grid(row=r, column=1, columnspan=2, sticky="we", **pad)
        b_out = ttk.Button(self, text="...", width=4, command=self._choose_out)
        b_out.grid(row=r, column=3, **pad)
        tip(l_out, GEN_OUTPUT_DIR_TIP)
        r += 1
        l_world = ttk.Label(self, text="* World ID:")
        l_world.grid(row=r, column=0, sticky="w", **pad)
        e_world = ttk.Entry(self, textvariable=self.world)
        e_world.grid(row=r, column=1, sticky="we", **pad)
        l_seed = ttk.Label(self, text="* Seed:")
        l_seed.grid(row=r, column=2, sticky="e", **pad)
        e_seed = ttk.Entry(self, textvariable=self.seed, width=12)
        e_seed.grid(row=r, column=3, sticky="we", **pad)
        tip(l_world, GEN_WORLD_ID_TIP)
        tip(l_seed, GEN_SEED_TIP)
        r += 1
        l_wh = ttk.Label(self, text="* Width:")
        l_wh.grid(row=r, column=0, sticky="w", **pad)
        e_width = ttk.Entry(self, textvariable=self.width)
        e_width.grid(row=r, column=1, sticky="we", **pad)
        l_height = ttk.Label(self, text="* Height:")
        l_height.grid(row=r, column=2, sticky="e", **pad)
        e_height = ttk.Entry(self, textvariable=self.height)
        e_height.grid(row=r, column=3, sticky="we", **pad)
        tip(l_wh, GEN_WIDTH_TIP)
        r += 1
        l_chunk = ttk.Label(self, text="Chunk:")
        l_chunk.grid(row=r, column=0, sticky="w", **pad)
        e_chunk = ttk.Entry(self, textvariable=self.chunk)
        e_chunk.grid(row=r, column=1, sticky="we", **pad)
        l_scale = ttk.Label(self, text="Scale:")
        l_scale.grid(row=r, column=2, sticky="e", **pad)
        e_scale = ttk.Entry(self, textvariable=self.scale)
        e_scale.grid(row=r, column=3, sticky="we", **pad)
        tip(l_scale, GEN_SCALE_TIP)
        r += 1
        l_oct = ttk.Label(self, text="Octaves:")
        l_oct.grid(row=r, column=0, sticky="w", **pad)
        e_oct = ttk.Entry(self, textvariable=self.oct)
        e_oct.grid(row=r, column=1, sticky="we", **pad)
        l_lac = ttk.Label(self, text="Lacunarity:")
        l_lac.grid(row=r, column=2, sticky="e", **pad)
        e_lac = ttk.Entry(self, textvariable=self.lac)
        e_lac.grid(row=r, column=3, sticky="we", **pad)
        tip(l_oct, GEN_OCTAVES_TIP)
        r += 1
        l_gain = ttk.Label(self, text="Gain:")
        l_gain.grid(row=r, column=0, sticky="w", **pad)
        e_gain = ttk.Entry(self, textvariable=self.gain)
        e_gain.grid(row=r, column=1, sticky="we", **pad)
        cb_biomes = ttk.Checkbutton(self, text="Biomes", variable=self.biomes)
        cb_biomes.grid(row=r, column=2, sticky="w", **pad)
        tip(cb_biomes, GEN_BIOMES_TIP)
        r += 1

        l_ocean = ttk.Label(self, text="Ocean lvl:")
        l_ocean.grid(row=r, column=0, sticky="w", **pad)
        e_ocean = ttk.Entry(self, textvariable=self.ocean)
        e_ocean.grid(row=r, column=1, sticky="we", **pad)
        l_land_h = ttk.Label(self, text="Высота суши (м):")
        l_land_h.grid(row=r, column=2, sticky="e", **pad)
        e_land_h = ttk.Entry(self, textvariable=self.land_height)
        e_land_h.grid(row=r, column=3, sticky="we", **pad)
        tip(l_ocean, GEN_OCEAN_LEVEL_TIP)
        tip(l_land_h, GEN_LAND_HEIGHT_TIP)
        r += 1

        cb_inland = ttk.Checkbutton(self, text="Без океана по краям", variable=self.inland)
        cb_inland.grid(row=r, column=0, columnspan=2, sticky="w", **pad)
        tip(cb_inland, GEN_INLAND_TIP)
        r += 1
        l_edge_b = ttk.Label(self, text="Edge boost:")
        l_edge_b.grid(row=r, column=0, sticky="w", **pad)
        e_edge_b = ttk.Entry(self, textvariable=self.edge_boost)
        e_edge_b.grid(row=r, column=1, sticky="we", **pad)
        l_edge_m = ttk.Label(self, text="Edge margin:")
        l_edge_m.grid(row=r, column=2, sticky="e", **pad)
        e_edge_m = ttk.Entry(self, textvariable=self.edge_margin)
        e_edge_m.grid(row=r, column=3, sticky="we", **pad)
        tip(l_edge_b, GEN_EDGE_BOOST_TIP)
        tip(l_edge_m, GEN_EDGE_MARGIN_TIP)
        r += 1
        cb_godot = ttk.Checkbutton(self, text="Экспорт для Godot Terrain3D", variable=self.export_godot)
        cb_godot.grid(row=r, column=0, columnspan=2, sticky="w", **pad)
        tip(cb_godot, GEN_EXPORT_GODOT_TIP)
        r += 1
        cb_ts = ttk.Checkbutton(self, text="Новая папка версии (timestamp)", variable=self.auto_ver,
                                command=self._toggle_version)
        cb_ts.grid(row=r, column=0, columnspan=2, sticky="w", **pad)
        tip(cb_ts, GEN_AUTO_VERSION_TIP)
        l_ver = ttk.Label(self, text="Version:")
        l_ver.grid(row=r, column=2, sticky="e", **pad)
        self.e_version = ttk.Entry(self, textvariable=self.version)
        self.e_version.grid(row=r, column=3, sticky="we", **pad)
        r += 1
        self._toggle_version()

        cb_flat_edges = ttk.Checkbutton(self, text="Выровнять края чанков", variable=self.flat_edges)
        cb_flat_edges.grid(row=r, column=0, columnspan=2, sticky="w", **pad)
        tip(cb_flat_edges, "Выравнивает края каждого чанка до высоты 0 для бесшовных переходов.")
        r += 1

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=r, column=0, columnspan=4, sticky="we")
        self.btn = ttk.Button(btn_frame, text="Generate", command=self._run)
        self.btn.pack(side="left", expand=True, fill="x", **pad)
        self.help_btn = ttk.Button(btn_frame, text="Помощь", command=self._show_help)
        self.help_btn.pack(side="left", fill="x", padx=pad['padx'], pady=pad['pady'])
        r += 1

        self.status = tk.StringVar(value="Готово")
        ttk.Label(self, textvariable=self.status).grid(row=r, column=0, columnspan=4, sticky="w", **pad)
        r += 1

        # --- Сетка ---
        self.preview_container = ttk.Frame(self)
        self.preview_container.grid(row=r, column=0, columnspan=4, sticky="nsew", **pad)
        self.preview_container.grid_rowconfigure(0, weight=1)
        self.preview_container.grid_columnconfigure(0, weight=1)
        self.grid_frame = ttk.Frame(self.preview_container)
        self.grid_frame.grid(row=0, column=0)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(3, weight=1)
        self.rowconfigure(r, weight=1)
        self.chunk_labels = {}
        self.update_queue = queue.Queue()
        self.photos = []

    def _run(self):
        try:
            out = Path(self.out.get()).resolve()
            world = self.world.get().strip()
            version = _ts_version() if self.auto_ver.get() else (self.version.get().strip() or "v1")

            chunk_size = int(self.chunk.get())
            width_val = int(self.width.get()) * chunk_size
            height_val = int(self.height.get()) * chunk_size

            cfg = GenConfig(
                out_dir=str(out), world_id=world, version=version,
                seed=int(self.seed.get()),
                width=width_val, height=height_val,
                chunk=chunk_size, scale=float(self.scale.get()),
                octaves=int(self.oct.get()), lacunarity=float(self.lac.get()), gain=float(self.gain.get()),
                with_biomes=bool(self.biomes.get()), ocean_level=float(self.ocean.get()),
                land_height_m=float(self.land_height.get()),
                edge_boost=(float(self.edge_boost.get()) if self.inland.get() else 0.0),
                edge_margin_frac=float(self.edge_margin.get()),
                export_for_godot=bool(self.export_godot.get()),
                flat_edges=bool(self.flat_edges.get())
            )

            cfg.validate()
            if not cfg.with_biomes:
                messagebox.showwarning("Внимание", "Для отображения превью необходимо включить галочку 'Biomes'.")
                return
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
                self.status.set(f"Готово: {out / world / version}")
                messagebox.showinfo("OK", f"Готово: {out / world / version}")

            run_bg(job, on_done=done, master_widget=self)
        except (ValueError, Exception) as e:
            self.btn.configure(state="normal")
            self.help_btn.configure(state="normal")
            messagebox.showerror("Ошибка", str(e))

    def _prepare_grid(self, width, height, chunk_size):
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
        try:
            while not self.update_queue.empty():
                cx, cy, img_data = self.update_queue.get_nowait()
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
        win = tk.Toplevel(self)
        win.title("Справка: Этап 1 - Генерация мира")
        win.geometry("650x600")
        text_widget = tk.Text(win, wrap="word", padx=10, pady=10, relief="flat", background="#f0f0f0")
        text_widget.pack(expand=True, fill="both")
        text_widget.tag_configure("h1", font=("TkDefaultFont", 14, "bold"), spacing3=10)
        text_widget.tag_configure("h2", font=("TkDefaultFont", 11, "bold"), spacing1=10, spacing3=5)
        text_widget.tag_configure("h3", font=("TkDefaultFont", 10, "bold"), spacing1=5, spacing3=3)
        text_widget.tag_configure("p", lmargin1=10, lmargin2=10)

        for tag, content in HELP_TEXTS["generate"]:
            text_widget.insert("end", content + "\n\n", tag)

        text_widget.configure(state="disabled")

    def _toggle_version(self):
        self.e_version.configure(state=("disabled" if self.auto_ver.get() else "normal"))

    def _choose_out(self):
        d = filedialog.askdirectory(title="Выбери папку вывода")
        if d: self.out.set(d)