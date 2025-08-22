import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path

from worldgen_core import GenConfig
from worldgen_core.pipeline import generate_world
from ..utils.run_bg import run_bg
from ..widgets.tooltip import tip

def _ts_version() -> str: return "v" + datetime.now().strftime("%Y%m%d_%H%M%S")

class GenerateTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        pad = {"padx":6,"pady":4}

        # vars (дефолты короткие)
        self.out = tk.StringVar(value=str(Path("./out").resolve()))
        self.world = tk.StringVar(value="demo")
        self.seed = tk.StringVar(value="12345")
        self.width = tk.StringVar(value="1024"); self.height = tk.StringVar(value="1024")
        self.chunk = tk.StringVar(value="512");  self.scale = tk.StringVar(value="600")
        self.oct = tk.StringVar(value="6"); self.lac = tk.StringVar(value="2.0"); self.gain = tk.StringVar(value="0.5")
        self.ocean = tk.StringVar(value="0.12"); self.inland = tk.IntVar(value=1)
        self.edge_boost = tk.StringVar(value="0.25"); self.edge_margin = tk.StringVar(value="0.12")
        self.biomes = tk.IntVar(value=1)
        self.auto_ver = tk.IntVar(value=1); self.version = tk.StringVar(value="v1")

        r=0
        ttk.Label(self, text="* Output dir:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.out).grid(row=r, column=1, columnspan=2, sticky="we", **pad)
        ttk.Button(self, text="...", width=4, command=self._choose_out).grid(row=r, column=3, **pad); r+=1

        ttk.Label(self, text="* World ID:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.world).grid(row=r, column=1, sticky="we", **pad)
        ttk.Label(self, text="* Seed:").grid(row=r, column=2, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.seed, width=12).grid(row=r, column=3, sticky="we", **pad); r+=1

        ttk.Label(self, text="* Width:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.width).grid(row=r, column=1, sticky="we", **pad)
        ttk.Label(self, text="* Height:").grid(row=r, column=2, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.height).grid(row=r, column=3, sticky="we", **pad); r+=1

        ttk.Label(self, text="Chunk:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.chunk).grid(row=r, column=1, sticky="we", **pad)
        ttk.Label(self, text="Scale:").grid(row=r, column=2, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.scale).grid(row=r, column=3, sticky="we", **pad); r+=1

        ttk.Label(self, text="Octaves:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.oct).grid(row=r, column=1, sticky="we", **pad)
        ttk.Label(self, text="Lacunarity:").grid(row=r, column=2, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.lac).grid(row=r, column=3, sticky="we", **pad); r+=1

        ttk.Label(self, text="Gain:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.gain).grid(row=r, column=1, sticky="we", **pad)
        ttk.Checkbutton(self, text="Biomes", variable=self.biomes).grid(row=r, column=2, sticky="w", **pad); r+=1

        ttk.Label(self, text="Ocean lvl:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.ocean).grid(row=r, column=1, sticky="we", **pad)
        ttk.Checkbutton(self, text="Без океана по краям", variable=self.inland).grid(row=r, column=2, sticky="w", **pad); r+=1

        ttk.Label(self, text="Edge boost:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.edge_boost).grid(row=r, column=1, sticky="we", **pad)
        ttk.Label(self, text="Edge margin:").grid(row=r, column=2, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.edge_margin).grid(row=r, column=3, sticky="we", **pad); r+=1

        ttk.Checkbutton(self, text="Новая папка версии (timestamp)", variable=self.auto_ver,
                        command=self._toggle_version).grid(row=r, column=0, columnspan=2, sticky="w", **pad)
        ttk.Label(self, text="Version:").grid(row=r, column=2, sticky="e", **pad)
        self.e_version = ttk.Entry(self, textvariable=self.version); self.e_version.grid(row=r, column=3, sticky="we", **pad); r+=1
        self._toggle_version()

        self.btn = ttk.Button(self, text="Generate", command=self._run)
        self.btn.grid(row=r, column=0, columnspan=4, sticky="we", **pad); r+=1
        self.status = tk.StringVar(value="Готово")
        ttk.Label(self, textvariable=self.status).grid(row=r, column=0, columnspan=4, sticky="w", **pad); r+=1
        self.log = tk.Text(self, height=10); self.log.grid(row=r, column=0, columnspan=4, sticky="nsew", **pad)
        self.columnconfigure(1, weight=1); self.columnconfigure(3, weight=1); self.rowconfigure(r, weight=1)

        # подсказки (кратко)
        tip(self.e_version, "Имя папки версии. При включённом timestamp выдаётся автоматически.")

    def _toggle_version(self):
        self.e_version.configure(state=("disabled" if self.auto_ver.get() else "normal"))

    def _choose_out(self):
        d = filedialog.askdirectory(title="Выбери папку вывода")
        if d: self.out.set(d)

    def _run(self):
        try:
            out = Path(self.out.get()).resolve()
            world = self.world.get().strip()
            if not out or not world: raise ValueError("Укажи Output dir и World ID.")
            version = _ts_version() if self.auto_ver.get() else (self.version.get().strip() or "v1")

            cfg = GenConfig(
                out_dir=str(out), world_id=world, version=version,
                seed=int(self.seed.get()),
                width=int(self.width.get()), height=int(self.height.get()),
                chunk=int(self.chunk.get()), scale=float(self.scale.get()),
                octaves=int(self.oct.get()), lacunarity=float(self.lac.get()), gain=float(self.gain.get()),
                with_biomes=bool(self.biomes.get()), ocean_level=float(self.ocean.get()),
                edge_boost=(float(self.edge_boost.get()) if self.inland.get() else 0.0),
                edge_margin_frac=float(self.edge_margin.get())
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
