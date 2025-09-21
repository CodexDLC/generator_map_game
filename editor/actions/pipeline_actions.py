# ==============================================================================
# Файл: editor/actions/pipeline_actions.py
# Назначение: Логика для действий, связанных с файлами пайплайнов (графов).
# ==============================================================================
import json
from PySide6 import QtWidgets


def on_save_pipeline(main_window):
    """
    Обрабатывает сохранение текущего графа в JSON-файл.
    """
    # Проверяем, открыт ли проект. Если да, предлагаем сохраниться в его папку.
    start_dir = ""
    if main_window.current_project_path:
        start_dir = str(Path(main_window.current_project_path) / "pipelines")

    file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
        main_window, "Сохранить файл пайплайна", start_dir, "JSON Files (*.json)"
    )
    if not file_path:
        return

    try:
        graph_data = main_window.graph.serialize_session()
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, indent=2, ensure_ascii=False)
        main_window.statusBar.showMessage(f"Пайплайн успешно сохранен: {file_path}", 5000)
        print(f"Pipeline saved to: {file_path}")
    except Exception as e:
        main_window.statusBar.showMessage(f"Ошибка сохранения: {e}", 5000)
        print(f"ERROR saving pipeline: {e}")


def on_load_pipeline(main_window):
    """
    Обрабатывает загрузку графа из JSON-файла.
    """
    start_dir = ""
    if main_window.current_project_path:
        start_dir = str(Path(main_window.current_project_path) / "pipelines")

    file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
        main_window, "Загрузить файл пайплайна", start_dir, "JSON Files (*.json)"
    )
    if not file_path:
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)
        main_window.graph.clear_session()
        main_window.graph.deserialize_session(graph_data)
        main_window.statusBar.showMessage(f"Пайплайн успешно загружен: {file_path}", 5000)
        print(f"Pipeline loaded from: {file_path}")
    except Exception as e:
        main_window.statusBar.showMessage(f"Ошибка загрузки: {e}", 5000)
        print(f"ERROR loading pipeline: {e}")