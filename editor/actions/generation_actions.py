# ==============================================================================
# Файл: editor/actions/generation_actions.py
# ВЕРСИЯ 2.1: Исправлена логика асинхронной генерации и прогресс-бара.
# + ВНЕДРЕНИЕ ЛОГИРОВАНИЯ
# ==============================================================================
import logging  # <--- ДОБАВЛЕНО
from pathlib import Path
from PySide6 import QtCore, QtWidgets

# Импортируем наши новые классы
from .progress_dialog import ProgressDialog
from .generation_dialog import GenerationDialog

logger = logging.getLogger(__name__)  # <--- ДОБАВЛЕНО


def on_generate_world(main_window):
    """
    Открывает диалог настроек и запускает ПОЛНУЮ генерацию мира
    в фоновом потоке.
    """
    logger.info("Action triggered: on_generate_world.")
    if not main_window.current_project_path:
        logger.warning("World generation cancelled: No project is open.")
        main_window.statusBar.showMessage("Сначала откройте или создайте проект!", 5000)
        return

    project_data = main_window.get_project_data()
    if not project_data:
        logger.error("Could not get project data. Aborting generation.")
        return

    dialog = GenerationDialog(main_window, project_name=project_data.get("project_name"))
    default_artifacts_path = Path(main_window.current_project_path).parent / "artifacts"
    dialog.artifacts_path_input.setText(str(default_artifacts_path))

    if dialog.exec():
        settings = dialog.get_values()
        logger.info(f"Generation settings confirmed: {settings}")

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
        progress_dialog = ProgressDialog(main_window)
        main_window.thread = QtCore.QThread()

        # ПРИМЕЧАНИЕ: Предполагается, что `main_window.worker` будет создан где-то до этого вызова.
        # Если это не так, здесь может быть потенциальная ошибка.
        if not hasattr(main_window, 'worker') or main_window.worker is None:
            logger.critical("main_window.worker is not initialized! Cannot start generation.")
            QtWidgets.QMessageBox.critical(main_window, "Критическая ошибка", "Воркер для генерации не был создан.")
            return

        main_window.worker.moveToThread(main_window.thread)
        main_window.thread.started.connect(main_window.worker.run)
        main_window.worker.finished.connect(main_window.thread.quit)
        main_window.worker.error.connect(main_window.thread.quit)
        main_window.worker.finished.connect(main_window.worker.deleteLater)
        main_window.thread.finished.connect(main_window.thread.deleteLater)
        main_window.worker.progress.connect(progress_dialog.update_progress)

        def on_finished(message):
            logger.info(f"World generation finished successfully: {message}")
            progress_dialog.close()
            main_window.statusBar.showMessage(message, 10000)
            main_window.thread = None
            main_window.worker = None

        def on_error(message):
            logger.error(f"World generation failed: {message}")
            progress_dialog.close()
            QtWidgets.QMessageBox.critical(main_window, "Ошибка Генерации", message)
            main_window.thread = None
            main_window.worker = None

        main_window.worker.finished.connect(on_finished)
        main_window.worker.error.connect(on_error)

        def cancel_generation():
            logger.warning("Generation cancellation requested by user.")
            if main_window.worker:
                main_window.worker.stop()
                progress_dialog.status_label.setText("Отмена...")

        progress_dialog.cancel_button.clicked.connect(cancel_generation)

        main_window.thread.start()
        logger.debug("Generation thread started.")
        progress_dialog.open()

        # --- КОНЕЦ ИСПРАВЛЕННОЙ ЛОГИКИ ---
    else:
        logger.info("World generation was cancelled by user in the settings dialog.")