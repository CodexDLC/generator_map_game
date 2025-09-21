# ==============================================================================
# Файл: run_editor.py
# Назначение: Главная точка входа для запуска нового редактора пресетов.
# ==============================================================================

import sys
from PySide6 import QtWidgets

# Импортируем наш новый класс MainWindow и стили
from editor.main_window import MainWindow
from editor.theme import APP_STYLE_SHEET


def run_editor():
    """
    Инициализирует и запускает главное окно редактора.
    """
    app = QtWidgets.QApplication(sys.argv)

    # Применяем нашу темную тему ко всему приложению
    app.setStyleSheet(APP_STYLE_SHEET)

    # Создаем и показываем наше главное окно
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    print("--- Запуск редактора пресетов ---")
    run_editor()