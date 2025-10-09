# editor/actions/project_actions.py
import logging
import json
import os
import shutil
from pathlib import Path
from PySide6 import QtWidgets

from editor.graph.graph_utils import create_default_graph_session
from editor.ui.bindings.project_bindings import collect_project_data_from_ui

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
        "version": 3,
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
        _ensure_dir(project_path / "pipelines")
        _ensure_dir(project_path / "output")
        _ensure_dir(project_path / "cache")

        project_data = _default_project_dict(project_name)
        _atomic_write_json(project_path / "project.json", project_data)

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
            json.load(f)
        logger.info(f"Project opened from: {project_path}")
        return str(project_path)
    except Exception as e:
        msg = f"Ошибка открытия проекта: {e}"
        logger.exception(f"Failed to open project file: {proj_json}")
        QtWidgets.QMessageBox.critical(parent_widget, "Ошибка", msg)
        return None

def _status_msg(main_window, text: str, msec: int = 4000) -> None:
    try:
        bar = main_window.statusBar()
        bar.showMessage(text, msec)
    except Exception:
        QtWidgets.QMessageBox.information(main_window, "Статус", text)


def on_save_project(main_window, data_to_write: dict = None) -> None:
    logger.info("Action triggered: on_save_project.")

    if not main_window.project_manager.current_project_path:
        _status_msg(main_window, "Проект не загружен.", 3000)
        return

    try:
        project_file_path = Path(main_window.project_manager.current_project_path) / "project.json"

        final_data = {}
        if data_to_write:
            logger.debug("Saving project with provided data (programmatic save).")
            final_data = data_to_write
        else:
            logger.debug("Saving project with data from UI (manual save).")
            with open(project_file_path, "r", encoding="utf-8") as f:
                final_data = json.load(f)

            ui_settings = collect_project_data_from_ui(main_window)
            final_data.update(ui_settings)

        _atomic_write_json(project_file_path, final_data)
        main_window.project_manager.current_project_data = final_data
        main_window.project_manager.mark_dirty(False)
        _status_msg(main_window, f"Проект сохранен: {project_file_path}", 4000)

    except Exception as e:
        msg = f"Ошибка сохранения проекта: {e}"
        _status_msg(main_window, msg, 6000)
        QtWidgets.QMessageBox.critical(main_window, "Ошибка сохранения", msg)
        logger.exception("Failed to save project.")

def on_delete_project(main_window) -> None:
    logger.info("Action triggered: on_delete_project.")
    pm = main_window.project_manager
    if not pm.current_project_path:
        _status_msg(main_window, "Нет загруженного проекта для удаления.", 3000)
        return

    project_path = Path(pm.current_project_path)
    project_name = project_path.name

    reply = QtWidgets.QMessageBox.warning(
        main_window,
        "Подтверждение удаления",
        f"Вы уверены, что хотите удалить проект '{project_name}'?\n\nЭто действие необратимо и удалит всю папку проекта с диска:\n{project_path}",
        QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.Cancel,
        QtWidgets.QMessageBox.StandardButton.Cancel
    )

    if reply == QtWidgets.QMessageBox.StandardButton.Yes:
        logger.warning(f"Deleting project: {project_path}")
        try:
            pm.current_project_path = None
            pm.current_project_data = None
            main_window.setWindowTitle("Редактор Миров")
            if main_window.graph:
                main_window.graph.clear_session()
            shutil.rmtree(project_path)
            _status_msg(main_window, f"Проект '{project_name}' успешно удален.", 5000)
            logger.info(f"Project '{project_name}' deleted successfully.")
            main_window.new_project()
        except Exception as e:
            msg = f"Не удалось удалить проект: {e}"
            logger.exception(f"Failed to delete project directory: {project_path}")
            QtWidgets.QMessageBox.critical(main_window, "Ошибка удаления", msg)
            pm.current_project_path = str(project_path)

# --- ИЗМЕНЕНИЕ: Удаляем ошибочную функцию отсюда ---