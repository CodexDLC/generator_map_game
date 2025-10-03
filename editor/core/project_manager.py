# ==============================================================================
# Файл: editor/project_manager.py
# ВЕРСИЯ 4.1 (РЕФАКТОРИНГ): Добавлен метод для сбора UI-контекста.
# - Добавлен метод collect_ui_context() для централизованного доступа к параметрам UI.
# - Удален ошибочный дубликат метода из класса ProjectDialog.
# ==============================================================================

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6 import QtWidgets, QtCore

from editor.actions.project_actions import (
    on_new_project, on_open_project, on_save_project, load_project_data
)
from editor.graph.graph_utils import create_default_graph_session
from editor.core.theme import APP_STYLE_SHEET
from editor.ui.bindings.project_bindings import apply_project_to_ui, collect_context_from_ui
from editor.actions.preset_actions import load_preset_into_graph

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
        context = collect_context_from_ui(self._mw, for_preview=for_preview)
        context['project'] = self.current_project_data
        return context

    def new_project(self):
        new_path = on_new_project(self._mw)
        if new_path:
            self.load_project(new_path)

    def open_project(self):
        path_to_open = on_open_project(self._mw)
        if path_to_open:
            if self.close_project_with_confirmation():
                self.load_project(path_to_open)

    def save_project(self) -> bool:
        if not self.current_project_path:
            self._status_msg("Проект не загружен, сохранение отменено.", 3000)
            return False

        project_data_from_ui = self.collect_ui_context()
        if self.current_project_data:
            self.current_project_data.update(project_data_from_ui)
        else:
            self.current_project_data = project_data_from_ui

        on_save_project(self._mw, self.current_project_data)

        self.mark_dirty(False)
        return True

    def close_project_with_confirmation(self) -> bool:
        if not self.is_dirty:
            return True
        res = QtWidgets.QMessageBox.question(self._mw, "Выход",
                                             "Сохранить изменения в проекте перед выходом?",
                                             QtWidgets.QMessageBox.StandardButton.Save |
                                             QtWidgets.QMessageBox.StandardButton.Discard |
                                             QtWidgets.QMessageBox.StandardButton.Cancel)
        if res == QtWidgets.QMessageBox.StandardButton.Save:
            return self.save_project()
        elif res == QtWidgets.QMessageBox.StandardButton.Discard:
            return True
        else:  # Cancel
            return False

    def _status_msg(self, text: str, msec: int = 4000) -> None:
        try:
            self._mw.statusBar().showMessage(text, msec)
        except Exception:
            pass

# ... (rest of the file is unchanged)
