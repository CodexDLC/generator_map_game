# ==============================================================================
# Файл: editor/actions/project_actions.py
# Назначение: Действия проекта (создать / открыть), синхронные с твоими UI-полями.
# Совместимо с MainWindow, где есть:
#   chunk_size_input, region_size_input, cell_size_input,
#   seed_input, global_x_offset_input, global_z_offset_input,
#   size_input (превью), graph (NodeGraph), preview_widget, statusBar.
# ==============================================================================

from __future__ import annotations

import json
import os
from pathlib import Path
from PySide6 import QtWidgets


# -----------------------------------------------------------------------------#
# helpers
# -----------------------------------------------------------------------------#

def _ask_dir(parent, title: str) -> str | None:
    d = QtWidgets.QFileDialog.getExistingDirectory(parent, title)
    return d if d else None


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _default_project_dict(project_name: str) -> dict:
    """Единый формат project.json."""
    return {
        "version": 1,
        "project_name": project_name,
        # — генерация —
        "chunk_size": 128,               # размер чанка в пикселях
        "region_size_in_chunks": 4,      # регион в чанках
        "cell_size": 1.0,                # м/пиксель
        "seed": 1,
        "global_x_offset": 0.0,
        "global_z_offset": 0.0,
        # — предпросмотр —
        "preview_size": 512,             # размер сетки предпросмотра
    }


def _apply_project_to_ui(main_window, data: dict) -> None:
    """Записываем значения в виджеты, совпадает с текущими именами полей."""
    # числа целые
    main_window.chunk_size_input.setValue(int(data.get("chunk_size", 128)))
    main_window.region_size_input.setValue(int(data.get("region_size_in_chunks", 4)))
    main_window.seed_input.setValue(int(data.get("seed", 1)))
    main_window.size_input.setValue(int(data.get("preview_size", 512)))

    # числа float
    main_window.cell_size_input.setValue(float(data.get("cell_size", 1.0)))
    main_window.global_x_offset_input.setValue(float(data.get("global_x_offset", 0.0)))
    main_window.global_z_offset_input.setValue(float(data.get("global_z_offset", 0.0)))


# -----------------------------------------------------------------------------#
# actions
# -----------------------------------------------------------------------------#

def on_new_project(main_window):
    """
    Создание нового проекта: выбираем базовую папку, имя проекта,
    создаём структуру и project.json, пробрасываем значения в UI.
    """
    print("[Project] -> New Project")

    base_dir = _ask_dir(main_window, "Выберите папку для проектов")
    if not base_dir:
        main_window.statusBar.showMessage("Создание проекта отменено.", 3000)
        return

    project_name, ok = QtWidgets.QInputDialog.getText(main_window, "Новый проект", "Введите имя проекта:")
    if not ok or not project_name.strip():
        main_window.statusBar.showMessage("Создание проекта отменено.", 3000)
        return

    project_path = Path(base_dir) / project_name.strip()

    try:
        # структура проекта
        _ensure_dir(project_path)
        _ensure_dir(project_path / "pipelines")
        _ensure_dir(project_path / "exports")

        # дефолтные значения
        project_data = _default_project_dict(project_name.strip())

        # сохранить JSON
        with open(project_path / "project.json", "w", encoding="utf-8") as f:
            json.dump(project_data, f, ensure_ascii=False, indent=2)

        # применить к UI
        _apply_project_to_ui(main_window, project_data)

        # метаданные окна
        main_window.current_project_path = str(project_path)
        main_window.setWindowTitle(f"Редактор Миров — [{project_data['project_name']}]")
        main_window.statusBar.showMessage(f"Проект создан: {project_path}", 5000)
        print(f"[Project] -> Created at: {project_path}")

    except Exception as e:
        msg = f"Ошибка создания проекта: {e}"
        main_window.statusBar.showMessage(msg, 5000)
        print(f"[Project] -> ERROR: {msg}")


def on_open_project(main_window):
    """
    Открытие существующего проекта: выбираем папку, читаем project.json,
    применяем значения к UI.
    """
    print("[Project] -> Open Project")

    project_dir = _ask_dir(main_window, "Выберите папку проекта (внутри project.json)")
    if not project_dir:
        main_window.statusBar.showMessage("Открытие проекта отменено.", 3000)
        return

    project_path = Path(project_dir)
    proj_json = project_path / "project.json"

    if not proj_json.exists():
        main_window.statusBar.showMessage("В выбранной папке нет project.json.", 5000)
        return

    try:
        with open(proj_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        # обратная совместимость ключей
        if "region_size" in data and "region_size_in_chunks" not in data:
            data["region_size_in_chunks"] = data["region_size"]
        if "size" in data and "preview_size" not in data:
            data["preview_size"] = data["size"]

        # применить к UI
        _apply_project_to_ui(main_window, data)

        # метаданные окна
        main_window.current_project_path = str(project_path)
        title_name = data.get("project_name", project_path.name)
        main_window.setWindowTitle(f"Редактор Миров — [{title_name}]")
        main_window.statusBar.showMessage(f"Проект открыт: {project_path}", 5000)
        print(f"[Project] -> Opened from: {project_path}")

    except Exception as e:
        msg = f"Ошибка открытия проекта: {e}"
        main_window.statusBar.showMessage(msg, 5000)
        print(f"[Project] -> ERROR: {msg}")
