import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path
import math

from worldgen_core import GenConfig
from worldgen_core.pipeline import generate_world
from ..utils.run_bg import run_bg
from ..widgets.tooltip import tip

def _ts_version() -> str:
    return "v" + datetime.now().strftime("%Y%m%d_%H%M%S")

# Пресеты с «сглаживанием» (Scale/Octaves/Lacunarity/Gain)
PRESETS = {
    "Max 65 km (32×32 @ 2048 m)": dict(
        width=32*1024, height=32*1024, chunk=1024, mpp=2.0,
        scale=6000, oct=4, lac=1.9, gain=0.42, ocean=0.12, inland=0
    ),
    "Mid 32 km (32×32 @ 1024 m)": dict(
        width=32*1024, height=32*1024, chunk=1024, mpp=1.0,
        scale=4000, oct=5, lac=1.95, gain=0.45, ocean=0.12, inland=0
    ),
    "Lite 16 km (32×32 @ 512 m)": dict(
        width=32*512, height=32*512, chunk=512, mpp=1.0,
        scale=3000, oct=6, lac=2.0, gain=0.50, ocean=0.12, inland=0
    ),
    "Small test 1 km": dict(
        width=1024, height=1024, chunk=512, mpp=1.0,
        scale=800, oct=6, lac=2.0, gain=0.50, ocean=0.12, inland=0
    ),
}

class GenerateTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        pad = {"padx":6, "pady":4}

        # базовые переменные
        self.out = tk.StringVar(value=str(Path("./out").resolve()))
        self.world = tk.StringVar(value="demo")
        self.seed = tk.StringVar(value="12345")

        # размеры и генерация
        self.width = tk.StringVar(value="1024")
        self.height = tk.StringVar(value="1024")
        self.chunk = tk.StringVar(value="512")
        self.mpp = tk.StringVar(value="1.0")

        self.scale = tk.StringVar(value="600")
        self.oct = tk.StringVar(value="6")
        self.lac = tk.StringVar(value="2.0")
        self.gain = tk.StringVar(value="0.5")

        self.ocean = tk.StringVar(value="0.12")
        self.inland = tk.IntVar(value=0)  # без подъёма краёв
        self.edge_boost = tk.StringVar(value="0.25")
        self.edge_margin = tk.StringVar(value="0.12")
        self.biomes = tk.IntVar(value=1)

        self.auto_ver = tk.IntVar(value=1)
        self.version = tk.StringVar(value="v1")

        self.preset_name = tk.StringVar(value="Small test 1 km")

        # --- UI ---
        r = 0
        ttk.Label(self, text="* Output dir:").grid(row=r, column=0, sticky="w", **pad)
        e = ttk.Entry(self, textvariable=self.out); e.grid(row=r, column=1, columnspan=2, sticky="we", **pad); tip(e, "Папка для вывода файлов")
        ttk.Button(self, text="...", width=4, command=self._choose_out).grid(row=r, column=3, **pad); r += 1

        ttk.Label(self, text="* World ID:").grid(row=r, column=0, sticky="w", **pad)
        e = ttk.Entry(self, textvariable=self.world); e.grid(row=r, column=1, sticky="we", **pad); tip(e, "Имя мира (папка)")
        ttk.Label(self, text="* Seed:").grid(row=r, column=2, sticky="e", **pad)
        e = ttk.Entry(self, textvariable=self.seed, width=12); e.grid(row=r, column=3, sticky="we", **pad); tip(e, "Зерно случайности (детерминизм)"); r += 1

        ttk.Label(self, text="Preset:").grid(row=r, column=0, sticky="w", **pad)
        cb = ttk.Combobox(self, textvariable=self.preset_name, values=list(PRESETS.keys()), state="readonly")
        cb.grid(row=r, column=1, sticky="we", **pad); tip(cb, "Готовые наборы параметров и сглаживания")
        ttk.Button(self, text="Apply preset", command=self._apply_preset).grid(row=r, column=2, columnspan=2, sticky="we", **pad); r += 1

        ttk.Label(self, text="* Width px:").grid(row=r, column=0, sticky="w", **pad)
        e = ttk.Entry(self, textvariable=self.width); e.grid(row=r, column=1, sticky="we", **pad); tip(e, "Ширина мира в пикселях")
        ttk.Label(self, text="* Height px:").grid(row=r, column=2, sticky="e", **pad)
        e = ttk.Entry(self, textvariable=self.height); e.grid(row=r, column=3, sticky="we", **pad); tip(e, "Высота мира в пикселях"); r += 1

        ttk.Label(self, text="* Chunk px:").grid(row=r, column=0, sticky="w", **pad)
        e = ttk.Entry(self, textvariable=self.chunk); e.grid(row=r, column=1, sticky="we", **pad); tip(e, "Размер файла-чанка (256/512/1024)")
        ttk.Label(self, text="MPP (m/px):").grid(row=r, column=2, sticky="e", **pad)
        e = ttk.Entry(self, textvariable=self.mpp); e.grid(row=r, column=3, sticky="we", **pad); tip(e, "Метров на пиксель. region_size = chunk * MPP ≤ 2048 м"); r += 1

        ttk.Label(self, text="Scale:").grid(row=r, column=0, sticky="w", **pad)
        e = ttk.Entry(self, textvariable=self.scale); e.grid(row=r, column=1, sticky="we", **pad); tip(e, "Масштаб форм рельефа: больше — крупнее и глаже")
        ttk.Label(self, text="Octaves:").grid(row=r, column=2, sticky="e", **pad)
        e = ttk.Entry(self, textvariable=self.oct); e.grid(row=r, column=3, sticky="we", **pad); tip(e, "Слои шума. Меньше — глаже"); r += 1

        ttk.Label(self, text="Lacunarity:").grid(row=r, column=0, sticky="w", **pad)
        e = ttk.Entry(self, textvariable=self.lac); e.grid(row=r, column=1, sticky="we", **pad); tip(e, "Рост частоты. 1.8–1.95 — мягко")
        ttk.Label(self, text="Gain:").grid(row=r, column=2, sticky="e", **pad)
        e = ttk.Entry(self, textvariable=self.gain); e.grid(row=r, column=3, sticky="we", **pad); tip(e, "Затухание амплитуды. 0.35–0.5 — мягко"); r += 1

        ttk.Label(self, text="Ocean lvl:").grid(row=r, column=0, sticky="w", **pad)
        e = ttk.Entry(self, textvariable=self.ocean); e.grid(row=r, column=1, sticky="we", **pad); tip(e, "Порог воды 0..1 (меньше — воды меньше)")
        c = ttk.Checkbutton(self, text="Без океана по краям", variable=self.inland); c.grid(row=r, column=2, sticky="w", **pad); tip(c, "Поднять края мира"); r += 1

        ttk.Label(self, text="Edge boost:").grid(row=r, column=0, sticky="w", **pad)
        e = ttk.Entry(self, textvariable=self.edge_boost); e.grid(row=r, column=1, sticky="we", **pad); tip(e, "Сила подъёма краёв (если включено)")
        ttk.Label(self, text="Edge margin:").grid(row=r, column=2, sticky="e", **pad)
        e = ttk.Entry(self, textvariable=self.edge_margin); e.grid(row=r, column=3, sticky="we", **pad); tip(e, "Ширина зоны подъёма"); r += 1

        ttk.Checkbutton(self, text="Biomes", variable=self.biomes).grid(row=r, column=0, sticky="w", **pad)
        ttk.Checkbutton(self, text="Новая папка версии (timestamp)", variable=self.auto_ver,
                        command=self._toggle_version).grid(row=r, column=1, sticky="w", **pad)
        ttk.Label(self, text="Version:").grid(row=r, column=2, sticky="e", **pad)
        self.e_version = ttk.Entry(self, textvariable=self.version); self.e_version.grid(row=r, column=3, sticky="we", **pad); r += 1
        self._toggle_version()

        self.btn = ttk.Button(self, text="Generate", command=self._run)
        self.btn.grid(row=r, column=0, columnspan=4, sticky="we", **pad); r += 1

        self.status = tk.StringVar(value="Готово")
        ttk.Label(self, textvariable=self.status).grid(row=r, column=0, columnspan=4, sticky="w", **pad); r += 1
        self.log = tk.Text(self, height=10); self.log.grid(row=r, column=0, columnspan=4, sticky="nsew", **pad)

        self.columnconfigure(1, weight=1); self.columnconfigure(3, weight=1); self.rowconfigure(r, weight=1)

        # автоприменение стартового пресета
        self._apply_preset(silent=True)

    # --- helpers ---
    def _toggle_version(self):
        self.e_version.configure(state=("disabled" if self.auto_ver.get() else "normal"))

    def _choose_out(self):
        d = filedialog.askdirectory(title="Выбери папку вывода")
        if d: self.out.set(d)

    def _apply_preset(self, silent=False):
        p = PRESETS[self.preset_name.get()]
        self.width.set(str(p["width"]))
        self.height.set(str(p["height"]))
        self.chunk.set(str(p["chunk"]))
        self.mpp.set(str(p["mpp"]))
        self.scale.set(str(p["scale"]))
        self.oct.set(str(p["oct"]))
        self.lac.set(str(p["lac"]))
        self.gain.set(str(p["gain"]))
        self.ocean.set(str(p["ocean"]))
        self.inland.set(int(p["inland"]))
        if not silent:
            messagebox.showinfo("Preset", f"Применён: {self.preset_name.get()}")

    def _validate_limits(self):
        w = int(self.width.get()); h = int(self.height.get())
        chunk = int(self.chunk.get()); mpp = float(self.mpp.get())
        nx = math.ceil(w / chunk); ny = math.ceil(h / chunk)
        region_m = chunk * mpp
        errs = []
        if nx > 32 or ny > 32:
            errs.append(f"Сетка {nx}×{ny} превышает лимит 32×32.")
        if region_m > 2048:
            errs.append(f"Region Size = {region_m:.1f} м > 2048 м (chunk*MPP).")
        return errs

    def _run(self):
        try:
            errs = self._validate_limits()
            if errs:
                messagebox.showerror("Лимиты Terrain3D", "\n".join(errs)); return

            out = Path(self.out.get()).resolve()
            world = self.world.get().strip()
            if not out or not world:
                raise ValueError("Укажи Output dir и World ID.")
            version = _ts_version() if self.auto_ver.get() else (self.version.get().strip() or "v1")

            cfg = GenConfig(
                out_dir=str(out), world_id=world, version=version,
                seed=int(self.seed.get()),
                width=int(self.width.get()), height=int(self.height.get()),
                chunk=int(self.chunk.get()), scale=float(self.scale.get()),
                octaves=int(self.oct.get()), lacunarity=float(self.lac.get()), gain=float(self.gain.get()),
                with_biomes=bool(self.biomes.get()), ocean_level=float(self.ocean.get()),
                edge_boost=(float(self.edge_boost.get()) if self.inland.get() else 0.0),
                edge_margin_frac=float(self.edge_margin.get()),
                meters_per_pixel=float(self.mpp.get())
            )

            self.btn.configure(state="disabled"); self.status.set("Генерация...")
            self.log.delete("1.0", tk.END)

            def job():
                generate_world(cfg, on_progress=lambda k,t,cx,cy: self.log.insert("end", f"{k+1}/{t} chunk {cx},{cy}\n"))
            def done():
                self.btn.configure(state="normal")
                self.status.set(f"Готово: {out / world / version}")
                messagebox.showinfo("OK", f"Готово: {out / world / version}")

            run_bg(job, on_done=done)
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
