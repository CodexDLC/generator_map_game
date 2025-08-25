import tkinter as tk
from tkinter import ttk

# Временно используем список-заглушку, пока не научились читать его из мира
BIOME_LIST = ["Океан", "Пляж", "Равнина", "Лес", "Горы", "Снег"]


class RuleEditorWindow(tk.Toplevel):
    def __init__(self, master, rule=None, on_save=None):
        super().__init__(master)
        self.title("Редактор правила")
        self.geometry("450x400")  # Немного увеличим окно
        self.transient(master)
        self.grab_set()

        self.rule_data = rule if rule is not None else {}
        self.on_save_callback = on_save

        # --- Переменные для всех полей ввода ---
        self.object_id = tk.StringVar(value=self.rule_data.get("id", "pine_tree"))
        self.target_biome = tk.StringVar(value=self.rule_data.get("biome", BIOME_LIST[2]))  # По умолчанию "Равнина"
        self.min_slope = tk.StringVar(value=self.rule_data.get("min_slope", "0"))
        self.max_slope = tk.StringVar(value=self.rule_data.get("max_slope", "30"))
        self.min_alt = tk.StringVar(value=self.rule_data.get("min_alt", "0"))
        self.max_alt = tk.StringVar(value=self.rule_data.get("max_alt", "1000"))
        self.density_scale = tk.StringVar(value=self.rule_data.get("density_scale", "50"))
        self.density_threshold = tk.StringVar(value=self.rule_data.get("density_threshold", "0.5"))

        # --- Создание интерфейса ---
        pad = {"padx": 6, "pady": 4}
        frame = ttk.Frame(self, padding=pad)
        frame.pack(expand=True, fill="both")

        r = 0
        # --- Основные ---
        ttk.Label(frame, text="ID Объекта:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.object_id).grid(row=r, column=1, columnspan=3, sticky="we", **pad)
        r += 1
        ttk.Label(frame, text="Целевой биом:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Combobox(frame, textvariable=self.target_biome, values=BIOME_LIST, state="readonly").grid(row=r, column=1,
                                                                                                      columnspan=3,
                                                                                                      sticky="we",
                                                                                                      **pad)
        r += 1

        # --- Уклон (Slope) ---
        ttk.Label(frame, text="Уклон (градусы):").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.min_slope, width=8).grid(row=r, column=1, sticky="w", **pad)
        ttk.Label(frame, text="до").grid(row=r, column=2)
        ttk.Entry(frame, textvariable=self.max_slope, width=8).grid(row=r, column=3, sticky="w", **pad)
        r += 1

        # --- Высота (Altitude) ---
        ttk.Label(frame, text="Высота (метры):").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.min_alt, width=8).grid(row=r, column=1, sticky="w", **pad)
        ttk.Label(frame, text="до").grid(row=r, column=2)
        ttk.Entry(frame, textvariable=self.max_alt, width=8).grid(row=r, column=3, sticky="w", **pad)
        r += 1

        # --- Плотность (Density) ---
        ttk.Separator(frame, orient="horizontal").grid(row=r, column=0, columnspan=4, sticky="we", pady=10)
        r += 1
        ttk.Label(frame, text="Масштаб плотности:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.density_scale).grid(row=r, column=1, columnspan=3, sticky="we", **pad)
        r += 1
        ttk.Label(frame, text="Порог плотности:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.density_threshold).grid(row=r, column=1, columnspan=3, sticky="we", **pad)
        r += 1

        # --- Кнопки Сохранить / Отмена ---
        btn_frame = ttk.Frame(self)
        btn_frame.pack(side="bottom", fill="x", padx=pad['padx'], pady=pad['pady'])
        ttk.Button(btn_frame, text="Сохранить", command=self._on_save).pack(side="right")
        ttk.Button(btn_frame, text="Отмена", command=self.destroy).pack(side="right", padx=pad['padx'])

        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

    def _on_save(self):
        """Собирает данные из полей и передает их обратно."""
        try:
            # Собираем данные с проверкой
            self.rule_data["id"] = self.object_id.get().strip()
            if not self.rule_data["id"]:
                raise ValueError("ID Объекта не может быть пустым.")

            self.rule_data["biome"] = self.target_biome.get()
            self.rule_data["min_slope"] = float(self.min_slope.get())
            self.rule_data["max_slope"] = float(self.max_slope.get())
            self.rule_data["min_alt"] = float(self.min_alt.get())
            self.rule_data["max_alt"] = float(self.max_alt.get())
            self.rule_data["density_scale"] = float(self.density_scale.get())
            self.rule_data["density_threshold"] = float(self.density_threshold.get())

            if self.on_save_callback:
                self.on_save_callback(self.rule_data)

            self.destroy()

        except ValueError as e:
            messagebox.showerror("Ошибка ввода", f"Проверьте правильность введенных данных.\n({e})", parent=self)