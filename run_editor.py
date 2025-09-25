# ==============================================================================
# Файл: run_editor.py
# Назначение: Главная точка входа для запуска нового редактора.
# ВЕРСЯ 2.0: Добавлен запуск через "Менеджер Проектов".
# ==============================================================================

import sys
import logging # <--- Добавьте этот импорт
from typing import cast

from PySide6 import QtWidgets, QtCore, QtGui

from editor.main_window import MainWindow
from editor.setup_logging import setup_logging
from editor.theme import APP_STYLE_SHEET
from editor.project_manager import show_project_manager

logger = logging.getLogger(__name__)

class DebugEventFilter(QtCore.QObject):
    """
    Этот класс-шпион будет перехватывать и логировать
    важные события в приложении.
    """

    def eventFilter(self, watched_object, event):
        if event.type() == QtCore.QEvent.Type.FocusIn:
            widget_class_name = watched_object.metaObject().className()
            logger.debug(f"[FOCUS] >> Фокус ПОЛУЧИЛ: {widget_class_name} ({watched_object})")

        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        if event.type() == QtCore.QEvent.Type.KeyPress:
            # Явно приводим тип, чтобы IDE поняла, с чем мы работаем
            key_event = cast(QtGui.QKeyEvent, event)

            key_name = key_event.text()
            if not key_name:
                key_enum = QtCore.Qt.Key(key_event.key())
                key_name = key_enum.name

            modifiers = key_event.modifiers()
            # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

            mod_names = []
            if modifiers & QtCore.Qt.KeyboardModifier.ControlModifier:
                mod_names.append("Ctrl")
            if modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier:
                mod_names.append("Shift")

            modifier_str = "+".join(mod_names)
            logger.debug(f"[KEYPRESS] >> Нажата клавиша: {modifier_str}{'+' if mod_names else ''}{key_name}")

        return super().eventFilter(watched_object, event)


def run_editor():
    """
    Инициализирует и запускает приложение в цикле, позволяя
    возвращаться в менеджер проектов.
    """
    setup_logging()
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE_SHEET)

    # --- НАЧАЛО ИЗМЕНЕНИЯ ---
    # Создаем и устанавливаем наш фильтр на все приложение
    event_filter = DebugEventFilter(app)
    app.installEventFilter(event_filter)
    logger.info("Отладчик событий фокуса и клавиатуры активирован.")
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

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
