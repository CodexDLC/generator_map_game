import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime

from worldgen_core.pipeline import extract_window
from ..utils.run_bg import run_bg

def _ts_version() -> str: return "v" + datetime.now().strftime("%Y%m%d_%H%M%S")

class ExtractTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        pad = {"padx":6,"pady":4}
        self.src = tk.StringVar()
        self.out = tk.StringVar(value=str(Path("./out").resolve()))
        self.world = tk.StringVar(value="demo_slice")
        self.auto_ver = tk.IntVar(value=1)
        self.version = tk.StringVar(value="v1")
        self.ox = tk.StringVar(value="0"); self.oy = tk.StringVar(value="0")
        self.w = tk.StringVar(value="512"); self.h = tk.StringVar(value="512")
        self.chunk = tk.StringVar(value="512")
        self.copy_biomes = tk.IntVar(value=1)

        r=0
        ttk.Label(self, text="* Source vX:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.src).grid(row=r, column=1, columnspan=2, sticky="we", **pad)
        ttk.Button(self, text="...", width=4, command=self._choose_src).grid(row=r, column=3, **pad); r+=1

        ttk.Label(self, text="* Out dir:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.out).grid(row=r, column=1, columnspan=2, sticky="we", **pad)
        ttk.Button(self, text="...", width=4, command=self._choose_out).grid(row=r, column=3, **pad); r+=1

        ttk.Label(self, text="* New World ID:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.world).grid(row=r, column=1, sticky="we", **pad)
        ttk.Checkbutton(self, text="Новая папка версии (timestamp)", variable=self.auto_ver,
                        command=self._toggle_version).grid(row=r, column=2, sticky="w", **pad)
        self.e_version = ttk.Entry(self, textvariable=self.version); self.e_version.grid(row=r, column=3, sticky="we", **pad); r+=1
        self._toggle_version()

        ttk.Label(self, text="* Origin X:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.ox).grid(row=r, column=1, sticky="we", **pad)
        ttk.Label(self, text="* Origin Y:").grid(row=r, column=2, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.oy).grid(row=r, column=3, sticky="we", **pad); r+=1

        ttk.Label(self, text="* Width:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.w).grid(row=r, column=1, sticky="we", **pad)
        ttk.Label(self, text="* Height:").grid(row=r, column=2, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.h).grid(row=r, column=3, sticky="we", **pad); r+=1

        ttk.Label(self, text="Chunk:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.chunk).grid(row=r, column=1, sticky="we", **pad)
        ttk.Checkbutton(self, text="Копировать биомы", variable=self.copy_biomes).grid(row=r, column=2, sticky="w", **pad); r+=1

        self.btn = ttk.Button(self, text="Extract", command=self._run)
        self.btn.grid(row=r, column=0, columnspan=4, sticky="we", **pad); r+=1
        self.status = tk.StringVar(value="Готово")
        ttk.Label(self, textvariable=self.status).grid(row=r, column=0, columnspan=4, sticky="w", **pad); r+=1
        self.log = tk.Text(self, height=10); self.log.grid(row=r, column=0, columnspan=4, sticky="nsew", **pad)
        self.columnconfigure(1, weight=1); self.columnconfigure(3, weight=1); self.rowconfigure(r, weight=1)

    def _toggle_version(self):
        self.e_version.configure(state=("disabled" if self.auto_ver.get() else "normal"))

    def _choose_src(self):
        d = filedialog.askdirectory(title="Выбери папку исходного vX (содержит height/biome)")
        if d: self.src.set(d)

    def _choose_out(self):
        d = filedialog.askdirectory(title="Выбери папку вывода")
        if d: self.out.set(d)

    def _run(self):
        try:
            src = Path(self.src.get()); out = Path(self.out.get())
            world = self.world.get().strip()
            if not src or not out or not world: raise ValueError("Укажи Source, Out dir и World ID.")
            version = _ts_version() if self.auto_ver.get() else (self.version.get().strip() or "v1")
            dst_base = out / world / version

            self.btn.configure(state="disabled"); self.status.set("Extract...")
            self.log.delete("1.0", tk.END)

            def job():
                extract_window(src, dst_base,
                               origin_x=int(self.ox.get()), origin_y=int(self.oy.get()),
                               width=int(self.w.get()), height=int(self.h.get()),
                               chunk=int(self.chunk.get()),
                               copy_biomes=bool(self.copy_biomes.get()))
            def done():
                self.btn.configure(state="normal")
                self.status.set(f"Готово: {dst_base}")
                messagebox.showinfo("OK", f"Готово: {dst_base}")

            run_bg(job, on_done=done)
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
