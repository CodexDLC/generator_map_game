# ==============================================================================
# Файл: run_editor.py
# ВЕРСИЯ 3.1 (HOTFIX): Принудительная установка стиля Fusion.
# - Это гарантирует корректное применение QSS на всех платформах.
# ==============================================================================

import sys
import logging

from PySide6 import QtWidgets

from editor.core.main_window import MainWindow
from editor.core.setup_logging import setup_logging
from editor.core.theme import APP_STYLE_SHEET
from editor.core.project_manager import show_project_manager

logger = logging.getLogger(__name__)


def run_editor():
    """
    Инициализирует и запускает приложение.
    """
    setup_logging()
    app = QtWidgets.QApplication(sys.argv)

    # --- РЕФАКТОРИНГ: Принудительно устанавливаем стиль 'Fusion' ---
    # Это гарантирует, что наша таблица стилей будет применена корректно
    # на всех платформах, игнорируя нативные стили ОС.
    app.setStyle('Fusion')
    # -------------------------------------------------------------

    app.setStyleSheet(APP_STYLE_SHEET)

    project_path = show_project_manager()

    if not project_path:
        print("--- Запуск отменен пользователем, выход ---")
        return

    window = MainWindow(project_path=project_path)
    window.show()

    app.exec()
    print("--- Окно закрыто, выход из приложения ---")

if __name__ == "__main__":
    print("--- Запуск редактора ---")
    run_editor()
