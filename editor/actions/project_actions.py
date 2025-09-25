# ==============================================================================
# Файл: editor/actions/project_actions.py
# ВЕРСИЯ 2.1: Добавлена поддержка блока global_noise.
# ==============================================================================
import logging
import json
import os
from pathlib import Path
from PySide6 import QtWidgets

from editor.graph_utils import create_default_graph_session

logger = logging.getLogger(__name__)

def _ask_dir(parent, title: str) -> str | None:
    d = QtWidgets.QFileDialog.getExistingDirectory(parent, title)
    return d if d else None

def load_project_data(project_path_str: str) -> dict | None:
    """Загружает и возвращает данные из файла project.json."""
    if not project_path_str:
        return None
    try:
        with open(Path(project_path_str) / "project.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения файла проекта: {e}")
        return None

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _atomic_write_json(path: Path, data: dict) -> None:
    tmp_path = path.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)

def _default_project_dict(project_name: str) -> dict:
    """Единый формат project.json, теперь с поддержкой пресетов регионов."""
    return {
        "version": 3, # <-- Повышаем версию
        "project_name": project_name,
        "seed": 1,
        "chunk_size": 128,
        "region_size_in_chunks": 4,
        "cell_size": 1.0,
        "global_x_offset": 0.0,
        "global_z_offset": 0.0,
        "global_noise": {
            "scale_tiles": 6000.0,
            "octaves": 3,
            "amp_m": 400.0,
            "ridge": False
        },
        # --- НОВЫЙ БЛОК ДЛЯ ПРЕСЕТОВ ---
        "active_preset_name": "default",
        "region_presets": {
            "default": {
                "description": "Пресет по умолчанию",
                "landscape_graph": "pipelines/default_landscape.json",
                "climate_graph": "pipelines/default_climate.json",
                "biome_graph": "pipelines/default_biome.json"
            }
        }
    }


def on_new_project(parent_widget) -> str | None:
    """Создает новый проект, включая файлы пресета по умолчанию с нодами."""
    logger.info("Action triggered: on_new_project.")
    base_dir = _ask_dir(parent_widget, "Выберите папку для проектов")
    if not base_dir: return None

    project_name, ok = QtWidgets.QInputDialog.getText(parent_widget, "Новый проект", "Введите имя проекта:")
    if not (ok and project_name.strip()): return None

    project_name = project_name.strip()
    project_path = Path(base_dir) / project_name

    try:
        _ensure_dir(project_path)
        pipelines_dir = project_path / "pipelines"
        _ensure_dir(pipelines_dir)
        _ensure_dir(project_path / "output")

        # 1. Создаем структуру project.json
        project_data = _default_project_dict(project_name)
        _atomic_write_json(project_path / "project.json", project_data)

        # 2. Создаем корректные файлы для пресета 'default'
        default_graph_data = create_default_graph_session()

        default_preset_info = project_data["region_presets"]["default"]
        for key in ["landscape_graph", "climate_graph", "biome_graph"]:
            file_path = project_path / default_preset_info[key]
            _atomic_write_json(file_path, default_graph_data)

        logger.info(f"Project '{project_name}' created at: {project_path}")
        return str(project_path)
    except Exception as e:
        logger.exception("Failed to create new project.")
        QtWidgets.QMessageBox.critical(parent_widget, "Ошибка", f"Ошибка создания проекта: {e}")
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


def on_save_project(main_window, data_to_write: dict = None) -> None:
    """
    Собирает все настройки из UI и сохраняет их в project.json.
    Может также принимать готовый словарь для прямой записи.
    """
    logger.info("Action triggered: on_save_project.")
    if not main_window.current_project_path:
        logger.warning("Project save skipped: No project loaded.")
        main_window.statusBar.showMessage("Проект не загружен.", 3000)
        return

    try:
        project_file_path = Path(main_window.current_project_path) / "project.json"
        final_data = {}

        if data_to_write:
            # РЕЖИМ 1: Нам передали готовые данные (например, после создания пресета).
            # Просто используем их.
            logger.debug("Saving project with provided data (programmatic save).")
            final_data = data_to_write
        else:
            # РЕЖИМ 2: Данные не переданы, значит это ручное сохранение.
            # Собираем все данные из виджетов интерфейса.
            logger.debug("Saving project with data from UI (manual save).")

            # Читаем существующий файл, чтобы не потерять данные, которых нет в UI (список пресетов)
            with open(project_file_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)

            # Собираем данные из UI
            project_data_from_ui = {
                "seed": main_window.seed_input.value(),
                "chunk_size": main_window.chunk_size_input.value(),
                "region_size_in_chunks": main_window.region_size_input.value(),
                "cell_size": main_window.cell_size_input.value(),
                "global_x_offset": main_window.global_x_offset_input.value(),
                "global_z_offset": main_window.global_z_offset_input.value(),
                "global_noise": {
                    "scale_tiles": main_window.gn_scale_input.value(),
                    "octaves": main_window.gn_octaves_input.value(),
                    "amp_m": main_window.gn_amp_input.value(),
                    "ridge": main_window.gn_ridge_checkbox.isChecked()
                }
            }

            # Обновляем существующие данные данными из UI
            existing_data.update(project_data_from_ui)
            if "global_noise" in existing_data:
                existing_data["global_noise"].update(project_data_from_ui["global_noise"])

            final_data = existing_data

        # Атомарно записываем финальные данные в файл
        _atomic_write_json(project_file_path, final_data)

        logger.info(f"Project saved successfully to: {project_file_path}")
        main_window.statusBar.showMessage(f"Проект сохранен: {project_file_path}", 4000)

    except Exception as e:
        msg = f"Ошибка сохранения проекта: {e}"
        main_window.statusBar.showMessage(msg, 6000)
        QtWidgets.QMessageBox.critical(main_window, "Ошибка сохранения", msg)
        logger.exception("Failed to save project.")
