# ==============================================================================
# Файл: editor/actions/project_actions.py
# Назначение: Логика для действий, связанных с проектом (создание, открытие).
# ==============================================================================
import json
import os
from pathlib import Path
from PySide6 import QtWidgets


def on_new_project(main_window):
    """
    Обрабатывает логику создания нового проекта.
    """
    print("[Project] -> New Project action triggered.")

    base_dir = QtWidgets.QFileDialog.getExistingDirectory(main_window, "Выберите папку для нового проекта")
    if not base_dir:
        main_window.statusBar.showMessage("Создание проекта отменено.", 3000)
        return

    project_name, ok = QtWidgets.QInputDialog.getText(main_window, "Новый Проект", "Введите имя проекта:")
    if not ok or not project_name:
        main_window.statusBar.showMessage("Создание проекта отменено.", 3000)
        return

    project_path = Path(base_dir) / project_name

    try:
        pipelines_path = project_path / "pipelines"
        os.makedirs(pipelines_path, exist_ok=True)

        project_data = {
            "project_name": project_name,
            "world_seed": main_window.seed_input.value(),
            "global_x_offset": main_window.global_x_offset_input.value(),
            "global_z_offset": main_window.global_z_offset_input.value(),
            "preview_size": main_window.size_input.value(),
            "cell_size": main_window.cell_size_input.value()
        }

        project_file_path = project_path / "project.json"
        with open(project_file_path, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=2, ensure_ascii=False)

        main_window.current_project_path = str(project_path)
        main_window.setWindowTitle(f"Редактор Миров - [{project_name}]")
        main_window.statusBar.showMessage(f"Проект '{project_name}' успешно создан.", 5000)
        print(f"[Project] -> Project created at: {main_window.current_project_path}")

    except Exception as e:
        error_msg = f"Ошибка создания проекта: {e}"
        main_window.statusBar.showMessage(error_msg, 5000)
        print(f"[Project] -> ERROR: {error_msg}")


def on_open_project(main_window):
    """
    Обрабатывает логику открытия существующего проекта.
    """
    print("[Project] -> Open Project action triggered.")

    file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
        main_window, "Открыть Проект", "", "Project Files (*.json)"
    )
    if not file_path:
        main_window.statusBar.showMessage("Открытие проекта отменено.", 3000)
        return

    try:
        project_path = Path(file_path).parent

        with open(file_path, 'r', encoding='utf-8') as f:
            project_data = json.load(f)

        main_window.seed_input.setValue(project_data.get("world_seed", 0))
        main_window.global_x_offset_input.setValue(project_data.get("global_x_offset", 0))
        main_window.global_z_offset_input.setValue(project_data.get("global_z_offset", 0))
        main_window.size_input.setValue(project_data.get("preview_size", 512))
        main_window.cell_size_input.setValue(project_data.get("cell_size", 1.0))

        project_name = project_data.get("project_name", "Безымянный")
        main_window.current_project_path = str(project_path)
        main_window.setWindowTitle(f"Редактор Миров - [{project_name}]")
        main_window.statusBar.showMessage(f"Проект '{project_name}' успешно открыт.", 5000)
        print(f"[Project] -> Project opened from: {main_window.current_project_path}")

    except Exception as e:
        error_msg = f"Ошибка открытия проекта: {e}"
        main_window.statusBar.showMessage(error_msg, 5000)
        print(f"[Project] -> ERROR: {error_msg}")