# ==============================================================================
# Файл: editor/actions/project_actions.py
# ВЕРСИЯ 2.1: Добавлена поддержка блока global_noise.
# ==============================================================================
import logging
import json
import os
from pathlib import Path
from PySide6 import QtWidgets

logger = logging.getLogger(__name__)

def _ask_dir(parent, title: str) -> str | None:
    d = QtWidgets.QFileDialog.getExistingDirectory(parent, title)
    return d if d else None


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _atomic_write_json(path: Path, data: dict) -> None:
    tmp_path = path.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)

def _default_project_dict(project_name: str) -> dict:
    """Единый формат project.json, теперь с блоком global_noise."""
    return {
        "version": 2,
        "project_name": project_name,
        "seed": 1,
        "chunk_size": 128,
        "region_size_in_chunks": 4,
        "cell_size": 1.0,
        "global_x_offset": 0.0,
        "global_z_offset": 0.0,
        # --- НОВЫЙ БЛОК ---
        "global_noise": {
            "scale_tiles": 6000.0,
            "octaves": 3,
            "amp_m": 400.0,
            "ridge": False
        }
    }


def on_new_project(parent_widget) -> str | None:
    logger.info("Action triggered: on_new_project.")
    base_dir = _ask_dir(parent_widget, "Выберите папку для проектов")
    if not base_dir:
        logger.warning("Project creation cancelled: No base directory selected.")
        return None
    project_name, ok = QtWidgets.QInputDialog.getText(parent_widget, "Новый проект", "Введите имя проекта:")
    if not ok or not project_name.strip():
        logger.warning("Project creation cancelled: No project name entered.")
        return None

    project_path = Path(base_dir) / project_name.strip()
    try:
        _ensure_dir(project_path)
        _ensure_dir(project_path / "pipelines")
        _ensure_dir(project_path / "output")
        project_data = _default_project_dict(project_name.strip())
        with open(project_path / "project.json", "w", encoding="utf-8") as f:
            json.dump(project_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Project '{project_name.strip()}' created at: {project_path}")
        return str(project_path)
    except Exception as e:
        msg = f"Ошибка создания проекта: {e}"
        logger.exception("Failed to create new project.")
        QtWidgets.QMessageBox.critical(parent_widget, "Ошибка", msg)
        return None


def on_open_project(parent_widget) -> str | None:
    logger.info("Action triggered: on_open_project.")
    project_dir = _ask_dir(parent_widget, "Выберите папку проекта (внутри project.json)")
    if not project_dir:
        logger.warning("Project opening cancelled: No directory selected.")
        return None

    project_path = Path(project_dir)
    proj_json = project_path / "project.json"
    if not proj_json.exists():
        logger.error(f"Failed to open project: 'project.json' not found in {project_dir}")
        QtWidgets.QMessageBox.warning(parent_widget, "Ошибка", "В выбранной папке нет project.json.")
        return None
    try:
        with open(proj_json, "r", encoding="utf-8") as f:
            json.load(f)  # Просто проверяем, что файл читается как JSON
        logger.info(f"Project opened from: {project_path}")
        return str(project_path)
    except Exception as e:
        msg = f"Ошибка открытия проекта: {e}"
        logger.exception(f"Failed to open project file: {proj_json}")
        QtWidgets.QMessageBox.critical(parent_widget, "Ошибка", msg)
        return None


def on_save_project(main_window) -> None:
    """
    Собирает все настройки из UI и сохраняет их в project.json,
    включая новый блок global_noise.
    """
    logger.info("Action triggered: on_save_project.")
    if not main_window.current_project_path:
        logger.warning("Project save skipped: No project loaded.")
        main_window.statusBar.showMessage("Проект не загружен.", 3000)
        return

    try:
        # 1. Собрать текущие значения из виджетов
        project_data_from_ui = {
            "seed": main_window.seed_input.value(),
            "chunk_size": main_window.chunk_size_input.value(),
            "region_size_in_chunks": main_window.region_size_input.value(),
            "cell_size": main_window.cell_size_input.value(),
            "global_x_offset": main_window.global_x_offset_input.value(),
            "global_z_offset": main_window.global_z_offset_input.value(),
            # --- СОБИРАЕМ ДАННЫЕ ИЗ НОВОЙ ПАНЕЛИ ---
            "global_noise": {
                "scale_tiles": main_window.gn_scale_input.value(),
                "octaves": main_window.gn_octaves_input.value(),
                "amp_m": main_window.gn_amp_input.value(),
                "ridge": main_window.gn_ridge_checkbox.isChecked()
            }
        }

        project_file_path = Path(main_window.current_project_path) / "project.json"
        logger.debug(f"Reading existing project file: {project_file_path}")

        # 2. Читаем существующий файл, чтобы не потерять то, чего нет в UI
        with open(project_file_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)

        # 3. Обновляем данные (глубокое слияние)
        existing_data.update(project_data_from_ui)
        # Отдельно обновим вложенный словарь
        if "global_noise" in existing_data:
            existing_data["global_noise"].update(project_data_from_ui["global_noise"])
        else:
            existing_data["global_noise"] = project_data_from_ui["global_noise"]

        # 4. Атомарно записать обновленный JSON обратно
        _atomic_write_json(project_file_path, existing_data)  # <--- Используем новую атомарную запись

        logger.info(f"Project saved successfully to: {project_file_path}")
        main_window.statusBar.showMessage(f"Проект сохранен: {project_file_path}", 4000)

    except Exception as e:
        msg = f"Ошибка сохранения проекта: {e}"
        main_window.statusBar.showMessage(msg, 6000)
        QtWidgets.QMessageBox.critical(main_window, "Ошибка сохранения", msg)
        print(f"[Project] -> SAVE ERROR: {msg}")

