# ==============================================================================
# Файл: editor/actions/generation_actions.py
# ВЕРСИЯ 2.0: Добавлена поддержка фоновой генерации с прогресс-баром.
# ==============================================================================
from pathlib import Path
from PySide6 import QtCore, QtWidgets

# Импортируем наши новые классы
from .worker import GenerationWorker
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

        # --- НАЧАЛО НОВОЙ ЛОГИКИ С ПОТОКАМИ ---

        # 1. Создаем прогресс-диалог
        progress_dialog = ProgressDialog(main_window)

        # 2. Создаем Worker и QThread
        main_window.thread = QtCore.QThread()
        main_window.worker = GenerationWorker(
            world_seed=world_seed,
            graph_data=graph_data,
            artifacts_root=artifacts_root,
            radius=radius
        )
        main_window.worker.moveToThread(main_window.thread)

        # 3. Настраиваем сигналы и слоты
        main_window.thread.started.connect(main_window.worker.run)
        main_window.worker.finished.connect(main_window.thread.quit)
        main_window.worker.error.connect(main_window.thread.quit)
        main_window.worker.finished.connect(main_window.worker.deleteLater)
        main_window.thread.finished.connect(main_window.thread.deleteLater)

        # Обновление прогресс-бара
        main_window.worker.progress.connect(progress_dialog.update_progress)

        # Обработка завершения/ошибки
        def on_finished(message):
            progress_dialog.close()
            main_window.statusBar.showMessage(message, 10000)

        def on_error(message):
            progress_dialog.close()
            QtWidgets.QMessageBox.critical(main_window, "Ошибка Генерации", message)

        main_window.worker.finished.connect(on_finished)
        main_window.worker.error.connect(on_error)

        # Кнопка отмены
        def cancel_generation():
            if main_window.worker:
                main_window.worker.stop()

        progress_dialog.cancel_button.clicked.connect(cancel_generation)

        # 4. Запускаем поток и показываем диалог
        main_window.thread.start()
        progress_dialog.exec()
        # --- КОНЕЦ НОВОЙ ЛОГИКИ ---