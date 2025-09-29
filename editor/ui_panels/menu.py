# ==============================================================================
# Файл: editor/ui_panels/menu.py
# ВЕРСИЯ 2.1 (ИНТЕГРАЦИЯ): Подключены pipeline_actions.
# - Добавлены пункты для сохранения/загрузки графа (пайплайна).
# - Функциональность привязана к модулю pipeline_actions.py
# ==============================================================================

from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6 import QtGui
from editor.theme import APP_STYLE_SHEET

# --- ИЗМЕНЕНИЕ: Импортируем обработчики действий ---
from editor.actions.pipeline_actions import on_save_pipeline, on_load_pipeline

if TYPE_CHECKING:
    from editor.main_window import MainWindow


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

    # --- НАЧАЛО ИЗМЕНЕНИЙ ---
    file_menu.addSeparator()

    # Действие для сохранения пайплайна (графа)
    save_pipeline_action = file_menu.addAction("Сохранить пайплайн...")
    save_pipeline_action.triggered.connect(lambda: on_save_pipeline(main_window))

    # Действие для загрузки пайплайна (графа)
    load_pipeline_action = file_menu.addAction("Загрузить пайплайн...")
    load_pipeline_action.triggered.connect(lambda: on_load_pipeline(main_window))

    file_menu.addSeparator()
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    exit_action = file_menu.addAction("Выход")
    exit_action.triggered.connect(main_window.close)

    # --- Меню "Вид" ---
    view_menu = menu_bar.addMenu("&Вид")

    # TODO: Добавить действия для управления панелями

    # --- Меню "Помощь" ---
    help_menu = menu_bar.addMenu("&Помощь")

    about_action = help_menu.addAction("О программе")
    # TODO: Подключить к диалогу "О программе"