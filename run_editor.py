# ==============================================================================
# Файл: run_editor.py
# ВЕРСИЯ 3.0 (АРХИТЕКТУРНЫЙ РЕФАКТОРИНГ): Точка входа.
# - Использует show_project_manager() для выбора проекта перед запуском.
# ==============================================================================

import sys
import logging
from typing import cast

from PySide6 import QtWidgets, QtCore, QtGui

from editor.main_window import MainWindow
from editor.setup_logging import setup_logging
from editor.theme import APP_STYLE_SHEET
# РЕФАКТОРИНГ: Импортируем функцию из ее нового, правильного местоположения
from editor.project_manager import show_project_manager

logger = logging.getLogger(__name__)


def run_editor():
    """
    Инициализирует и запускает приложение.
    """
    setup_logging()
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE_SHEET)

    # Цикл перезапуска убран для простоты, можно будет вернуть позже.
    # Сначала показываем диалог выбора проекта.
    project_path = show_project_manager()

    if not project_path:
        print("--- Запуск отменен пользователем, выход ---")
        return # Выходим, если проект не выбран

    # Если проект выбран, создаем и показываем главное окно
    window = MainWindow(project_path=project_path)
    window.show()

    app.exec()
    print("--- Окно закрыто, выход из приложения ---")

if __name__ == "__main__":
    print("--- Запуск редактора ---")
    run_editor()
