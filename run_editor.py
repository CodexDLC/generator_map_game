# run_editor.py
import sys
import logging
from PySide6 import QtWidgets

from editor.core.main_window import MainWindow
from editor.core.setup_logging import setup_logging
from editor.core.theme import APP_STYLE_SHEET
from editor.core.project_manager import show_project_manager, ProjectManager

logger = logging.getLogger(__name__)


def run_editor():
    setup_logging()
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(APP_STYLE_SHEET)

    # Вызываем наш восстановленный, правильный диалог
    project_path = show_project_manager()

    if not project_path:
        print("--- Запуск отменен пользователем, выход ---")
        return

    # Создаем главное окно
    window = MainWindow()

    # --- ВОЗВРАЩАЕМ ЛОГИКУ ProjectManager ---
    # Создаем менеджер проекта и ПЕРЕДАЕМ его в главное окно
    # (Это было удалено в моем ошибочном решении)
    project_manager = ProjectManager(window)
    window.project_manager = project_manager  # Передаем менеджер в окно
    window.project_manager.load_project(project_path)
    # --- КОНЕЦ ВОССТАНОВЛЕНИЯ ---

    window.show()
    app.exec()
    print("--- Окно закрыто, выход из приложения ---")


if __name__ == "__main__":
    print("--- Запуск редактора ---")
    run_editor()