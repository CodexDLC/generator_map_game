# ==============================================================================
# Файл: editor/actions/generation_actions.py
# ВЕРСИЯ 2.1: Исправлена логика асинхронной генерации и прогресс-бара.
# ==============================================================================
from pathlib import Path
from PySide6 import QtCore, QtWidgets

# Импортируем наши новые классы

from .progress_dialog import ProgressDialog
from .generation_dialog import GenerationDialog


def on_generate_world(main_window):
    """
    Открывает диалог настроек и запускает ПОЛНУЮ генерацию мира
    в фоновом потоке.
    """
    if not main_window.current_project_path:
        main_window.statusBar.showMessage("Сначала откройте или создайте проект!", 5000)
        return

    project_data = main_window.get_project_data()
    if not project_data: return

    dialog = GenerationDialog(main_window, project_name=project_data.get("project_name"))
    default_artifacts_path = Path(main_window.current_project_path).parent / "artifacts"
    dialog.artifacts_path_input.setText(str(default_artifacts_path))

    if dialog.exec():
        settings = dialog.get_values()
        artifacts_root = Path(settings["artifacts_path"])
        radius = settings["radius"]
        world_seed = project_data.get("world_seed")

        graph_data = {
            "initial_load_radius": radius,
            "region_size": project_data.get("region_size", 3),
            "size": project_data.get("chunk_size", 512),
            "cell_size": project_data.get("cell_size", 1.0),
            "export": {},
            "elevation": {"max_height_m": 800.0},
            "node_graph": main_window.graph.serialize_session()
        }

        # --- НАЧАЛО ИСПРАВЛЕННОЙ ЛОГИКИ С ПОТОКАМИ ---

        # 1. Создаем прогресс-диалог
        progress_dialog = ProgressDialog(main_window)

        # 2. Создаем Worker и QThread
        main_window.thread = QtCore.QThread()

        main_window.worker.moveToThread(main_window.thread)

        # 3. Настраиваем сигналы и слоты

        # Соединяем сигнал начала потока с запуском задачи
        main_window.thread.started.connect(main_window.worker.run)

        # Сигналы для безопасного завершения потока
        main_window.worker.finished.connect(main_window.thread.quit)
        main_window.worker.error.connect(main_window.thread.quit)
        main_window.worker.finished.connect(main_window.worker.deleteLater)
        main_window.thread.finished.connect(main_window.thread.deleteLater)

        # Обновление прогресс-бара
        main_window.worker.progress.connect(progress_dialog.update_progress)

        # Обработка успешного завершения
        def on_finished(message):
            progress_dialog.close() # Закрываем диалог
            main_window.statusBar.showMessage(message, 10000)
            # Сбрасываем ссылки, чтобы избежать повторного использования
            main_window.thread = None
            main_window.worker = None

        # Обработка ошибки
        def on_error(message):
            progress_dialog.close() # Закрываем диалог
            QtWidgets.QMessageBox.critical(main_window, "Ошибка Генерации", message)
            # Сбрасываем ссылки
            main_window.thread = None
            main_window.worker = None

        main_window.worker.finished.connect(on_finished)
        main_window.worker.error.connect(on_error)

        # Кнопка отмены в диалоге
        def cancel_generation():
            if main_window.worker:
                main_window.worker.stop()
                # Текст в диалоге можно поменять на "Отмена..."
                progress_dialog.status_label.setText("Отмена...")

        progress_dialog.cancel_button.clicked.connect(cancel_generation)

        # 4. Запускаем поток и показываем НЕМОДАЛЬНЫЙ диалог
        main_window.thread.start()
        progress_dialog.open() # <-- ИСПОЛЬЗУЕМ open() ВМЕСТО exec()

        # --- КОНЕЦ ИСПРАВЛЕННОЙ ЛОГИКИ ---