import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import json

from worldgen_core.scatter import generate_scatter_map
from ..widgets.rule_editor import RuleEditorWindow


class ScatterTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        pad = {"padx": 6, "pady": 4}

        self.loaded_world_path = None  # Теперь это будет объект Path
        self.rules = []

        top_frame = ttk.Frame(self)
        top_frame.pack(side="top", fill="x", **pad)
        btn_load = ttk.Button(top_frame, text="Загрузить мир...", command=self._load_world)
        btn_load.pack(side="left", **pad)
        self.status_label = ttk.Label(top_frame, text="<- Загрузите мир для начала")
        self.status_label.pack(side="left", **pad)

        main_frame = ttk.LabelFrame(self, text="Правила размещения объектов")
        main_frame.pack(expand=True, fill="both", **pad)

        rules_frame = ttk.Frame(main_frame)
        rules_frame.pack(side="left", fill="both", expand=True, **pad)
        self.rules_listbox = tk.Listbox(rules_frame)
        self.rules_listbox.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(rules_frame, orient="vertical", command=self.rules_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.rules_listbox.config(yscrollcommand=scrollbar.set)

        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(side="left", fill="y", padx=pad['padx'])
        btn_add = ttk.Button(controls_frame, text="Добавить...", command=self._add_rule)
        btn_add.pack(fill="x", pady=pad['pady'])
        btn_edit = ttk.Button(controls_frame, text="Изменить...", command=self._edit_rule)
        btn_edit.pack(fill="x")
        btn_del = ttk.Button(controls_frame, text="Удалить", command=self._delete_rule)
        btn_del.pack(fill="x", pady=pad['pady'])

        run_button = ttk.Button(self, text="Сохранить правила и сгенерировать карту объектов",
                                command=self._run_scatter)
        run_button.pack(side="bottom", fill="x", **pad)

    def _update_rules_listbox(self):
        """Обновляет список правил в интерфейсе."""
        self.rules_listbox.delete(0, "end")
        for i, rule in enumerate(self.rules):
            display_text = f"Правило {i + 1}: Разместить '{rule.get('id', '?')}' в биоме '{rule.get('biome', '?')}'"
            self.rules_listbox.insert("end", display_text)

    def _add_rule(self):
        """Открывает окно для создания нового правила."""
        if not self.loaded_world_path:
            messagebox.showerror("Ошибка", "Сначала загрузите мир.")
            return

        def on_save(new_rule):
            self.rules.append(new_rule)
            self._update_rules_listbox()

        RuleEditorWindow(self, on_save=on_save)

    def _edit_rule(self):
        selected_indices = self.rules_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Внимание", "Сначала выберите правило в списке.")
            return

        index = selected_indices[0]
        rule_to_edit = self.rules[index]

        def on_save(edited_rule):
            self.rules[index] = edited_rule
            self._update_rules_listbox()

        RuleEditorWindow(self, rule=rule_to_edit, on_save=on_save)

    def _delete_rule(self):
        selected_indices = self.rules_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Внимание", "Сначала выберите правило в списке.")
            return

        index = selected_indices[0]
        if messagebox.askyesno("Удаление", f"Вы уверены, что хотите удалить правило {index + 1}?"):
            del self.rules[index]
            self._update_rules_listbox()

    def _load_world(self):
        dir_path = filedialog.askdirectory(title="Выберите папку с версией мира (напр. v2025...)")
        if not dir_path: return

        world_path = Path(dir_path)
        # Проверяем, что это действительно папка с миром
        if not (world_path / "metadata.json").is_file():
            messagebox.showerror("Ошибка", "Это не похоже на папку с миром. Файл 'metadata.json' не найден.")
            return

        self.loaded_world_path = world_path
        self.status_label.config(text=f"Загружен мир: {world_path.parent.name}/{world_path.name}")

        # --- НОВАЯ ЛОГИКА: Загружаем правила из файла, если он есть ---
        self._load_rules()

    def _load_rules(self):
        """Загружает правила из rules.json, если файл существует."""
        self.rules.clear()
        rules_path = self.loaded_world_path / "rules.json"
        if rules_path.is_file():
            try:
                with open(rules_path, 'r', encoding='utf-8') as f:
                    self.rules = json.load(f)
                self.status_label.config(text=self.status_label.cget("text") + " [Правила загружены]")
            except Exception as e:
                messagebox.showerror("Ошибка загрузки правил", f"Не удалось прочитать файл rules.json:\n{e}")

        self._update_rules_listbox()

    def _save_rules(self):
        """Сохраняет текущий список правил в rules.json."""
        if not self.loaded_world_path: return

        rules_path = self.loaded_world_path / "rules.json"
        try:
            with open(rules_path, 'w', encoding='utf-8') as f:
                json.dump(self.rules, f, indent=2)
        except Exception as e:
            messagebox.showerror("Ошибка сохранения правил", f"Не удалось сохранить файл rules.json:\n{e}")
            return False
        return True

    def _run_scatter(self):
        if not self.loaded_world_path:
            messagebox.showerror("Ошибка", "Сначала загрузите мир.")
            return

        # --- НОВАЯ ЛОГИКА: Сначала сохраняем правила ---
        if self._save_rules():
            messagebox.showinfo("Правила сохранены",
                                f"Правила сохранены в файл:\n{self.loaded_world_path / 'rules.json'}")

            # Теперь вызываем движок (пока он делает заглушку)
            # В будущем мы передадим ему self.rules
            result_path = generate_scatter_map(self.loaded_world_path, self.rules)
            messagebox.showinfo("Готово", f"Создан файл карты объектов:\n{result_path}")