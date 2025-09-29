# ==============================================================================
# Файл: editor/project_manager.py
# ВЕРСИЯ 3.2 (РЕФАКТОРИНГ): Восстановлена полная логика сохранения из UI.
# - Метод save_project теперь напрямую читает данные из виджетов MainWindow.
# ==============================================================================

from __future__ import annotations
import logging
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, List

from PySide6 import QtWidgets, QtCore

from editor.graph_utils import create_default_graph_session

if TYPE_CHECKING:
    from editor.main_window import MainWindow

logger = logging.getLogger(__name__)

# --- Константы для QSettings ---
ORGANIZATION_NAME = "WorldForge"
APPLICATION_NAME = "WorldForgeEditor"
LAST_PROJECT_DIR_KEY = "last_project_directory"

# ==============================================================================
# Класс для управления проектом ВНУТРИ MainWindow
# ==============================================================================
class ProjectManager:
    """Инкапсулирует всю логику работы с файлами уже открытого проекта."""
    def __init__(self, main_window: "MainWindow"):
        self._mw = main_window
        self.current_project_path: str | None = None
        self.is_dirty: bool = False

    def mark_dirty(self, dirty: bool = True):
        if self.is_dirty == dirty: return
        self.is_dirty = dirty
        logger.debug(f"Project dirty state set to: {self.is_dirty}")

    def load_project(self, project_path: str):
        logger.info(f"Loading project from: {project_path}")
        self.current_project_path = project_path
        self._mw.setWindowTitle(f"Редактор Миров - {Path(project_path).name}")
        # TODO: Загрузка данных из project.json в UI виджеты
        self.mark_dirty(False)
        self._status_msg(f"Проект '{Path(project_path).name}' загружен.")

    def save_project(self) -> bool:
        """РЕФАКТОРИНГ: Восстановлена полная логика сохранения."""
        if not self.current_project_path:
            self._status_msg("Проект не загружен.", 3000)
            return False
        try:
            # 1. Сохраняем граф
            graph_data = self._mw.graph.serialize_session()
            # TODO: Определить, в какой файл сохранять граф (зависит от активного пресета)
            graph_file_path = Path(self.current_project_path) / "pipelines/default_landscape.json"
            _atomic_write_json(graph_file_path, graph_data)

            # 2. Собираем данные из UI и сохраняем project.json
            project_file_path = Path(self.current_project_path) / "project.json"
            try:
                with open(project_file_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                existing_data = {}

            # Напрямую читаем данные из виджетов MainWindow
            project_data_from_ui = {
                "seed": self._mw.seed_input.value(),
                "chunk_size": self._mw.chunk_size_input.value(),
                "region_size_in_chunks": self._mw.region_size_in_chunks_input.value(),
                "cell_size": self._mw.cell_size_input.value(),
                "global_x_offset": self._mw.global_x_offset_input.value(),
                "global_z_offset": self._mw.global_z_offset_input.value(),
                "global_noise": {
                    "scale_tiles": self._mw.gn_scale_input.value(),
                    "octaves": self._mw.gn_octaves_input.value(),
                    "amp_m": self._mw.gn_amp_input.value(),
                    "ridge": self._mw.gn_ridge_checkbox.isChecked()
                }
            }

            existing_data.update(project_data_from_ui)
            # Убедимся, что вложенный словарь тоже обновляется, а не перезаписывается
            if "global_noise" in existing_data and "global_noise" in project_data_from_ui:
                 existing_data["global_noise"].update(project_data_from_ui["global_noise"])

            _atomic_write_json(project_file_path, existing_data)

            self._status_msg(f"Проект сохранен.", 4000)
            self.mark_dirty(False)
            return True
        except Exception as e:
            msg = f"Ошибка сохранения проекта: {e}"
            self._status_msg(msg, 6000)
            logger.exception("Failed to save project.")
            return False

    def close_project_with_confirmation(self) -> bool:
        if not self.is_dirty:
            return True
        res = QtWidgets.QMessageBox.question(self._mw, "Выход",
                                             "Сохранить проект перед выходом?",
                                             QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel)
        if res == QtWidgets.QMessageBox.Yes:
            return self.save_project()
        elif res == QtWidgets.QMessageBox.No:
            return True
        else: # Cancel
            return False

    def _status_msg(self, text: str, msec: int = 4000) -> None:
        try:
            self._mw.statusBar().showMessage(text, msec)
        except Exception:
            pass

# ==============================================================================
# Диалог выбора проекта
# ==============================================================================

class ProjectDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Менеджер Проектов")
        self.setMinimumSize(400, 300)
        self.selected_path: str | None = None
        self.settings = QtCore.QSettings(ORGANIZATION_NAME, APPLICATION_NAME)

        layout = QtWidgets.QVBoxLayout(self)
        
        self.btn_select_folder = QtWidgets.QPushButton("Выбрать папку с проектами...")
        self.btn_select_folder.clicked.connect(self._select_and_scan_folder)
        layout.addWidget(self.btn_select_folder)

        self.project_list = QtWidgets.QListWidget()
        self.project_list.itemDoubleClicked.connect(self._on_open_selected)
        layout.addWidget(self.project_list)

        button_box = QtWidgets.QHBoxLayout()
        self.btn_open = QtWidgets.QPushButton("Открыть выбранный")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self._on_open_selected)
        self.project_list.currentItemChanged.connect(lambda: self.btn_open.setEnabled(True))

        self.btn_new = QtWidgets.QPushButton("Создать новый...")
        self.btn_new.clicked.connect(self._on_new)

        button_box.addWidget(self.btn_new)
        button_box.addStretch()
        button_box.addWidget(self.btn_open)
        layout.addLayout(button_box)

        self._load_initial_dir()

    def _load_initial_dir(self):
        last_dir = self.settings.value(LAST_PROJECT_DIR_KEY)
        if last_dir and Path(last_dir).exists():
            self._scan_folder(last_dir)

    def _select_and_scan_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Выберите папку с проектами")
        if folder:
            self.settings.setValue(LAST_PROJECT_DIR_KEY, folder)
            self._scan_folder(folder)

    def _scan_folder(self, folder_path: str):
        self.project_list.clear()
        self.btn_open.setEnabled(False)
        root = Path(folder_path)
        found_projects = [item for item in root.iterdir() if item.is_dir() and (item / "project.json").exists()]
        if not found_projects:
            self.project_list.addItem("Проекты не найдены")
            return
        for project_path in sorted(found_projects, key=lambda p: p.name.lower()):
            list_item = QtWidgets.QListWidgetItem(project_path.name)
            list_item.setData(QtCore.Qt.UserRole, str(project_path))
            self.project_list.addItem(list_item)

    def _on_open_selected(self):
        current_item = self.project_list.currentItem()
        if not current_item or not current_item.data(QtCore.Qt.UserRole):
            return
        self.selected_path = current_item.data(QtCore.Qt.UserRole)
        self.accept()

    def _on_new(self):
        path = _create_new_project(self)
        if path:
            self.selected_path = path
            self.accept()

def show_project_manager() -> str | None:
    dialog = ProjectDialog()
    if dialog.exec() == QtWidgets.QDialog.Accepted:
        return dialog.selected_path
    return None

# --- Вспомогательные функции для создания проекта ---

def _atomic_write_json(path: Path, data: dict):
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)

def _default_project_dict(project_name: str) -> dict:
    return {
        "version": 3,
        "project_name": project_name,
        "active_preset_name": "default",
        "region_presets": {
            "default": {
                "description": "Пресет по умолчанию",
                "landscape_graph": "pipelines/default_landscape.json",
            }
        }
    }

def _create_new_project(parent) -> str | None:
    base_dir = QtWidgets.QFileDialog.getExistingDirectory(parent, "Выберите папку для нового проекта")
    if not base_dir: return None
    project_name, ok = QtWidgets.QInputDialog.getText(parent, "Новый проект", "Введите имя проекта:")
    if not (ok and project_name.strip()): return None
    project_path = Path(base_dir) / project_name
    try:
        (project_path / "pipelines").mkdir(parents=True, exist_ok=True)
        project_data = _default_project_dict(project_name)
        _atomic_write_json(project_path / "project.json", project_data)
        default_graph_data = create_default_graph_session()
        graph_path = project_path / project_data["region_presets"]["default"]["landscape_graph"]
        _atomic_write_json(graph_path, default_graph_data)
        return str(project_path)
    except Exception as e:
        QtWidgets.QMessageBox.critical(parent, "Ошибка", f"Ошибка создания проекта: {e}")
        return None
