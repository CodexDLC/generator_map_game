# ==============================================================================
# Файл: editor/ui_panels/menu.py
# ВЕРСИЯ 2.2 (ИНТЕГРАЦИЯ): Добавлена опция "Удалить проект".
# ==============================================================================

from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6 import QtGui
from editor.core.theme import APP_STYLE_SHEET

# --- ИЗМЕНЕНИЕ: Импортируем обработчики действий ---
from editor.actions.pipeline_actions import on_save_pipeline, on_load_pipeline
# --- ИЗМЕНЕНИЕ: Импортируем действие удаления проекта ---
from editor.actions.project_actions import on_delete_project

if TYPE_CHECKING:
    from editor.core.main_window import MainWindow


def build_menus(main_window: "MainWindow") -> None:
    """Создает и настраивает меню для главного окна."""

    menu_bar = main_window.menuBar()
    menu_bar.setStyleSheet(APP_STYLE_SHEET)

    # --- Меню "Файл" ---
    file_menu = menu_bar.addMenu("&Файл")

    new_action = file_menu.addAction("Новый проект...")
    new_action.triggered.connect(main_window.new_project)

    open_action = file_menu.addAction("Открыть проект...")
    open_action.triggered.connect(main_window.open_project)

    file_menu.addSeparator()

    save_action = file_menu.addAction("Сохранить проект")
    save_action.setShortcut(QtGui.QKeySequence.StandardKey.Save)
    save_action.triggered.connect(main_window.save_project)

    file_menu.addSeparator()

    save_pipeline_action = file_menu.addAction("Сохранить пайплайн...")
    save_pipeline_action.triggered.connect(lambda: on_save_pipeline(main_window))

    load_pipeline_action = file_menu.addAction("Загрузить пайплайн...")
    load_pipeline_action.triggered.connect(lambda: on_load_pipeline(main_window))

    file_menu.addSeparator()

    # --- ИЗМЕНЕНИЕ: Добавляем действие удаления проекта ---
    delete_project_action = file_menu.addAction("Удалить проект...")
    delete_project_action.triggered.connect(lambda: on_delete_project(main_window))

    file_menu.addSeparator()

    exit_action = file_menu.addAction("Выход")
    exit_action.triggered.connect(main_window.close)

    # --- Меню "Вид" ---
    view_menu = menu_bar.addMenu("&Вид")
    
    map_action = view_menu.addAction("Карта Мира...")
    map_action.triggered.connect(main_window.show_world_map)

    # --- Меню "Помощь" ---
    help_menu = menu_bar.addMenu("&Помощь")

    about_action = help_menu.addAction("О программе")
    # TODO: Подключить к диалогу "О программе"
