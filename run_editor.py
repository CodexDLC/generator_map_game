# ==============================================================================
# Файл: run_editor.py
# Назначение: Главная точка входа для запуска нового редактора.
# ВЕРСЯ 2.0: Добавлен запуск через "Менеджер Проектов".
# ==============================================================================

import sys
from PySide6 import QtWidgets

# Импортируем наш новый класс MainWindow и стили
from editor.main_window import MainWindow
from editor.setup_logging import setup_logging
from editor.theme import APP_STYLE_SHEET
# --- НОВЫЙ ИМПОРТ ---
# Импортируем функцию, которая показывает наш новый диалог
from editor.project_manager import show_project_manager


def run_editor():
    """
    Инициализирует и запускает приложение в цикле, позволяя
    возвращаться в менеджер проектов.
    """
    setup_logging()
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE_SHEET)

    while True:  # <-- НАЧАЛО ЦИКЛА
        project_path = show_project_manager()

        if not project_path:
            # Если пользователь закрыл менеджер, выходим из цикла и приложения
            print("--- Запуск отменен пользователем, выход ---")
            break

        # Создаем и показываем главное окно
        window = MainWindow(project_path=project_path)
        window.show()

        # app.exec() блокирует выполнение до закрытия окна
        app.exec()

        # После закрытия окна проверяем, нужно ли нам перезапуститься
        # или полностью выйти из приложения.
        if not getattr(window, 'wants_restart', False):
            print("--- Окно закрыто, выход из приложения ---")
            break
        # Если wants_restart=True, цикл начнется заново


if __name__ == "__main__":
    print("--- Запуск редактора ---")
    run_editor()
