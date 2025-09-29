# ==============================================================================
# Файл: editor/ui_panels/menu.py
# ВЕРСИЯ 2.0 (РЕФАКТОРИНГ): Явное применение стилей.
# - Стиль теперь применяется напрямую к QMenuBar, чтобы избежать проблем
#   с наследованием на разных платформах.
# ==============================================================================

from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6 import QtGui

# РЕФАКТОРИНГ: Импортируем стили, чтобы применить их явно
from editor.theme import APP_STYLE_SHEET

if TYPE_CHECKING:
    from editor.main_window import MainWindow


def build_menus(main_window: "MainWindow") -> None:
    """Создает и настраивает меню для главного окна."""

    menu_bar = main_window.menuBar()
    # РЕФАКТОРИНГ: Явно применяем стили к меню-бару
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

    exit_action = file_menu.addAction("Выход")
    exit_action.triggered.connect(main_window.close)

    # --- Меню "Вид" ---
    view_menu = menu_bar.addMenu("&Вид")

    # TODO: Добавить действия для управления панелями

    # --- Меню "Помощь" ---
    help_menu = menu_bar.addMenu("&Помощь")

    about_action = help_menu.addAction("О программе")
    # TODO: Подключить к диалогу "О программе"
