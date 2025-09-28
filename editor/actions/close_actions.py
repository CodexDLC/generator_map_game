# editor/actions/close_actions.py
import logging
from PySide6 import QtWidgets

# Импортируем все необходимые зависимости из других модулей
from .project_actions import on_save_project
from .preset_actions import handle_save_active_preset
from ..ui_panels.project_binding import collect_context_from_ui

logger = logging.getLogger(__name__)


def _is_project_dirty(main_window) -> bool:
    """Сравнивает текущие настройки в UI с сохраненными в project.json."""
    try:
        current_data_from_ui = collect_context_from_ui(main_window)
        saved_data = main_window.get_project_data()
        if not saved_data:
            return True  # Если не удалось прочитать файл, лучше считать, что есть изменения

        # Сравниваем ключевые поля
        if current_data_from_ui["seed"] != saved_data.get("seed"): return True
        if current_data_from_ui["chunk_size"] != saved_data.get("chunk_size"): return True
        if current_data_from_ui["region_size_in_chunks"] != saved_data.get("region_size_in_chunks"): return True
        if current_data_from_ui["cell_size"] != saved_data.get("cell_size"): return True
        if current_data_from_ui.get("global_noise") != saved_data.get("global_noise"): return True

    except Exception as e:
        logger.warning(f"Ошибка при проверке изменений проекта: {e}")
        return True  # В случае ошибки лучше перестраховаться

    return False


def handle_close_event(main_window, event):
    """
    Обрабатывает событие закрытия окна, проверяя несохраненные изменения.
    """
    graph_changed = main_window.graph.session_changed
    project_settings_changed = _is_project_dirty(main_window)

    if not graph_changed and not project_settings_changed:
        event.accept()
        return

    msg_box = QtWidgets.QMessageBox(main_window)
    msg_box.setWindowTitle("Несохраненные изменения")
    msg_box.setText("У вас есть несохраненные изменения в проекте или активном пресете.")
    msg_box.setInformativeText("Хотите сохранить их перед выходом?")
    msg_box.setIcon(QtWidgets.QMessageBox.Icon.Question)

    save_button = msg_box.addButton("Сохранить", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
    discard_button = msg_box.addButton("Не сохранять", QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
    cancel_button = msg_box.addButton("Отмена", QtWidgets.QMessageBox.ButtonRole.RejectRole)

    msg_box.exec()

    clicked_button = msg_box.clickedButton()

    if clicked_button == save_button:
        logger.info("User chose to save changes on exit.")
        if project_settings_changed:
            on_save_project(main_window)
        if graph_changed:
            handle_save_active_preset(main_window)
        event.accept()
    elif clicked_button == discard_button:
        logger.info("User chose to discard changes on exit.")
        event.accept()
    else:  # Cancel
        logger.info("User cancelled the exit operation.")
        event.ignore()