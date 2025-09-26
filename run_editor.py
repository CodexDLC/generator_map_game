# ==============================================================================
# Файл: run_editor.py
# Назначение: Главная точка входа для запуска нового редактора.
# ВЕРСИЯ 2.3: Улучшенная система логирования событий UI.
# ==============================================================================

import sys
import logging
from typing import cast

from PySide6 import QtWidgets, QtCore, QtGui

from editor.main_window import MainWindow
from editor.setup_logging import setup_logging
from editor.theme import APP_STYLE_SHEET
from editor.project_manager import show_project_manager

logger = logging.getLogger(__name__)

# Классы, которые мы не хотим видеть в логах фокуса, чтобы уменьшить "шум"
IGNORED_FOCUS_CLASSES = [
    'QStyleSheetStyle'
]

try:
    from NodeGraphQt import BackdropNode

    def backdrop_icon_fix(self):
        return None

    BackdropNode.icon = backdrop_icon_fix
    logging.info("BackdropNode successfully patched with missing 'icon' method.")
except ImportError:
    logging.error("Could not import BackdropNode to apply patch.")

class DebugEventFilter(QtCore.QObject):
    """
    Этот класс-шпион будет перехватывать и логировать
    важные события в приложении для отладки.
    """

    def eventFilter(self, watched_object, event):
        # --- ЛОГИРОВАНИЕ ФОКУСА ---
        if event.type() == QtCore.QEvent.Type.FocusIn:
            class_name = watched_object.metaObject().className()

            # Если класс в черном списке, просто игнорируем событие
            if class_name in IGNORED_FOCUS_CLASSES:
                return super().eventFilter(watched_object, event)

            # Сначала пытаемся получить заданное имя объекта
            obj_name = watched_object.objectName()
            # Если имя есть, используем его, иначе — имя класса
            display_name = f"'{obj_name}'" if obj_name else class_name
            logger.debug(f"[FOCUS] >> Фокус ПОЛУЧИЛ: {display_name} ({watched_object})")

        # --- ЛОГИРОВАНИЕ НАЖАТИЙ КЛАВИШ ---
        if event.type() == QtCore.QEvent.Type.KeyPress:
            key_event = cast(QtGui.QKeyEvent, event)
            key_name = key_event.text()

            # Если текст не является печатаемым (служебные клавиши, Delete, Enter и т.д.),
            # то получаем имя из перечисления клавиш Qt.
            if not key_name.isprintable():
                try:
                    # Пытаемся получить имя из enum
                    key_enum = QtCore.Qt.Key(key_event.key())
                    key_name = key_enum.name
                except ValueError:
                    # Если по какой-то причине enum не найден, используем код клавиши
                    key_name = f"Unknown_Key_{key_event.key()}"

            modifiers = key_event.modifiers()
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

    # event_filter = DebugEventFilter(app)
    # app.installEventFilter(event_filter)
    # logger.info("Отладчик событий фокуса и клавиатуры активирован.")

    while True:
        project_path = show_project_manager()

        if not project_path:
            print("--- Запуск отменен пользователем, выход ---")
            break

        window = MainWindow(project_path=project_path)
        window.show()

        QtCore.QTimer.singleShot(1000, lambda: logger.debug(
            f"[FOCUS] focusWidget={QtWidgets.QApplication.focusWidget()}, "
            f"activeWindow={QtWidgets.QApplication.activeWindow()}"
        ))

        app.exec()

        if not getattr(window, 'wants_restart', False):
            print("--- Окно закрыто, выход из приложения ---")
            break

if __name__ == "__main__":
    print("--- Запуск редактора ---")
    run_editor()
