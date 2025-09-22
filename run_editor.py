# ==============================================================================
# Файл: run_editor.py
# Назначение: Главная точка входа для запуска нового редактора.
# ВЕРСЯ 2.0: Добавлен запуск через "Менеджер Проектов".
# ==============================================================================

import sys
from PySide6 import QtWidgets

# Импортируем наш новый класс MainWindow и стили
from editor.main_window import MainWindow
from editor.theme import APP_STYLE_SHEET
# --- НОВЫЙ ИМПОРТ ---
# Импортируем функцию, которая показывает наш новый диалог
from editor.project_manager import show_project_manager


def run_editor():
    """
    Инициализирует и запускает приложение.
    """
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE_SHEET)

    # --- ИЗМЕНЕННАЯ ЛОГИКА ЗАПУСКА ---
    # 1. Сначала показываем менеджер проектов. Он вернет путь или None.
    project_path = show_project_manager()

    # 2. Если пользователь выбрал или создал проект, запускаем главный редактор
    if project_path:
        # Передаем полученный путь к проекту в конструктор MainWindow
        window = MainWindow(project_path=project_path)
        window.show()
        sys.exit(app.exec())
    else:
        # Если project_path равен None, значит пользователь закрыл диалог.
        # В этом случае приложение просто завершает работу.
        print("--- Запуск отменен пользователем ---")
        sys.exit(0)


if __name__ == "__main__":
    print("--- Запуск редактора ---")
    run_editor()