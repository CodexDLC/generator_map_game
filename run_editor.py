# run_editor.py
import sys
import logging
from PySide6 import QtWidgets, QtCore  # <-- ИЗМЕНЕНИЕ: Добавляем импорт QtCore

from editor.core.main_window import MainWindow
from editor.core.setup_logging import setup_logging
from editor.core.theme import APP_STYLE_SHEET
from editor.core.project_manager import show_project_manager

logger = logging.getLogger(__name__)


def run_editor():
    setup_logging()
    app = QtWidgets.QApplication(sys.argv)

    # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
    # Эта функция будет вызвана, когда приложение будет готово к закрытию.
    # Она дожидается, пока все задачи в фоновых потоках завершатся.
    def cleanup_threads():
        logger.info("Завершение работы фоновых потоков...")
        QtCore.QThreadPool.globalInstance().waitForDone()
        logger.info("Все фоновые потоки успешно завершены.")

    # Привязываем нашу функцию к сигналу "приложение скоро закроется"
    app.aboutToQuit.connect(cleanup_threads)
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    app.setStyle('Fusion')
    app.setStyleSheet(APP_STYLE_SHEET)

    project_path = show_project_manager()

    if not project_path:
        logger.info("--- Запуск отменен пользователем, выход ---")
        return

    window = MainWindow(project_path=project_path)
    window.show()

    app.exec()
    logger.info("--- Цикл событий приложения завершен, выход ---")


if __name__ == "__main__":
    logger.info("--- Запуск редактора ---")
    run_editor()