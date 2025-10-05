# editor/core/project_manager.py
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6 import QtWidgets, QtCore

from editor.actions.project_actions import (
    on_new_project, on_open_project, load_project_data
)
from editor.graph.graph_utils import create_default_graph_session
from editor.core.theme import APP_STYLE_SHEET

from editor.actions.preset_actions import load_preset_into_graph
from editor.ui.bindings.project_bindings import apply_project_to_ui, collect_context_from_ui

if TYPE_CHECKING:
    from editor.core.main_window import MainWindow

logger = logging.getLogger(__name__)

# --- Константы для QSettings ---
ORGANIZATION_NAME = "WorldForge"
APPLICATION_NAME = "WorldForgeEditor"
LAST_PROJECT_DIR_KEY = "last_project_directory"


class ProjectManager:
    def __init__(self, main_window: "MainWindow"):
        self._mw = main_window
        self.current_project_path: str | None = None
        self.current_project_data: dict | None = None
        self.is_dirty: bool = False

    def mark_dirty(self, dirty: bool = True):
        if self.is_dirty == dirty: return
        self.is_dirty = dirty
        title = self._mw.windowTitle()
        if dirty and not title.endswith("*"):
            self._mw.setWindowTitle(title + "*")
        elif not dirty and title.endswith("*"):
            self._mw.setWindowTitle(title[:-1])
        logger.debug(f"Project dirty state set to: {self.is_dirty}")

    def load_project(self, project_path: str):
        logger.info(f"Loading project from: {project_path}")
        project_data = load_project_data(project_path)
        if not project_data:
            QtWidgets.QMessageBox.critical(self._mw, "Ошибка", f"Не удалось загрузить данные проекта из {project_path}")
            return

        self.current_project_path = project_path
        self.current_project_data = project_data

        apply_project_to_ui(self._mw, project_data)

        self._mw._load_presets_list()

        active_preset_name = project_data.get("active_preset_name")
        if active_preset_name:
            preset_info = project_data.get("region_presets", {}).get(active_preset_name)
            if preset_info:
                load_preset_into_graph(self._mw, preset_info)

        self.mark_dirty(False)
        self._status_msg(f"Проект '{Path(project_path).name}' загружен.")

    def collect_ui_context(self, for_preview: bool = True) -> dict:
        """
        Собирает все параметры из UI в единый словарь-контекст для генератора.
        """
        context = collect_context_from_ui(self._mw, for_preview=for_preview)
        context['project'] = self.current_project_data
        return context

    def new_project(self):
        new_path = on_new_project(self._mw)
        if new_path:
            self.load_project(new_path)

    def open_project(self):
        path_to_open = show_project_manager()

        if path_to_open:
            if self.close_project_with_confirmation():
                self.load_project(path_to_open)

    # --- ИЗМЕНЕНИЕ: Удалена некорректная функция save_project ---

    def close_project_with_confirmation(self) -> bool:
        if not self.is_dirty:
            return True
        res = QtWidgets.QMessageBox.question(self._mw, "Выход",
                                             "Сохранить изменения в проекте перед выходом?",
                                             QtWidgets.QMessageBox.StandardButton.Save |
                                             QtWidgets.QMessageBox.StandardButton.Discard |
                                             QtWidgets.QMessageBox.StandardButton.Cancel)
        if res == QtWidgets.QMessageBox.StandardButton.Save:
            # --- ИЗМЕНЕНИЕ: Теперь вызывается правильный метод сохранения из MainWindow ---
            return self._mw.save_project()
        elif res == QtWidgets.QMessageBox.StandardButton.Discard:
            return True
        else:  # Cancel
            return False

    def _status_msg(self, text: str, msec: int = 4000) -> None:
        try:
            self._mw.statusBar().showMessage(text, msec)
        except Exception:
            pass


# ==============================================================================
# Диалог выбора проекта (тот, который вам нужен)
# ==============================================================================

class ProjectDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Менеджер Проектов")
        self.setMinimumSize(400, 300)
        self.selected_path: str | None = None
        self.settings = QtCore.QSettings(ORGANIZATION_NAME, APPLICATION_NAME)

        self.setStyleSheet(APP_STYLE_SHEET)

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
        # Вызываем функцию создания проекта, передавая родительский виджет
        path = _create_new_project_dialog(self)
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


def _create_new_project_dialog(parent) -> str | None:
    # Эта функция была частью on_new_project, выносим ее для вызова из диалога
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