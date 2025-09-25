# editor/compute_manager.py
import logging
import numpy as np
from PySide6 import QtCore, QtWidgets

from .actions.worker import ComputeWorker, TiledComputeWorker

logger = logging.getLogger(__name__)


class ComputeManager(QtCore.QObject):
    """
    Управляет всеми асинхронными вычислениями графа,
    управляет потоками и воркерами.
    """
    # Сигналы, которые менеджер отправляет в MainWindow для обновления UI
    display_mesh = QtCore.Signal(object, float)
    display_tiled_mesh = QtCore.Signal(object, float)
    display_partial_tile = QtCore.Signal(int, int, object, int, int, float)
    display_status_message = QtCore.Signal(str, int)
    show_error_dialog = QtCore.Signal(str, str)
    set_busy_mode = QtCore.Signal(bool)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.thread = None
        self.worker = None

        self.tiled_results = {}
        self.tiled_params = {}

    def _is_busy(self) -> bool:
        """Проверяет, не занят ли уже какой-то процесс."""
        if self.thread and self.thread.isRunning():
            logger.warning("A compute thread is already running.")
            QtWidgets.QMessageBox.warning(self.main_window, "Внимание", "Предыдущая операция еще не завершена.")
            return True
        return False

    def _cleanup(self):
        """Очищает ссылки на поток и воркер после завершения."""
        self.thread = None
        self.worker = None

    # --- SINGLE COMPUTE LOGIC ---

    def start_single_compute(self, output_node, context):
        if self._is_busy():
            return

        self.set_busy_mode.emit(True)
        self.thread = QtCore.QThread()
        self.worker = ComputeWorker(output_node, context)
        self.worker.moveToThread(self.thread)

        self.worker.finished.connect(self._on_single_compute_finished)
        self.worker.error.connect(self._on_compute_error)

        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self._cleanup)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.start()

    def _on_single_compute_finished(self, result, message):
        logger.info(f"Single compute finished: {message}")
        self.set_busy_mode.emit(False)
        if result is not None:
            cell_size = self.main_window.cell_size_input.value()
            self.display_mesh.emit(result, cell_size)
        self.display_status_message.emit(message or "Готово", 4000)

    # --- TILED COMPUTE LOGIC ---

    def start_tiled_compute(self, output_node, context):
        if self._is_busy():
            return

        self.tiled_results.clear()
        self.tiled_params.clear()
        self.set_busy_mode.emit(True)

        self.thread = QtCore.QThread()
        self.worker = TiledComputeWorker(
            output_node=output_node,
            base_context=context,
            chunk_size=context["chunk_size"],
            region_size=context["region_size_in_chunks"],
        )
        self.worker.moveToThread(self.thread)

        self.worker.partial_ready.connect(self._on_tile_ready)
        self.worker.finished.connect(self._on_tiled_compute_finished)
        self.worker.error.connect(self._on_compute_error)

        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self._cleanup)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.start()

    def _on_tile_ready(self, tx, tz, tile, cs, rs, cell_size):
        tile_np = np.asarray(tile, dtype=np.float32)
        if tile_np.ndim != 2 or not np.isfinite(tile_np).all():
            self.display_status_message.emit(f"Пропущен плохой тайл ({tx},{tz})", 2000)
            return

        self.tiled_results[(tx, tz)] = tile_np
        if not self.tiled_params:
            self.tiled_params = {'cs': cs, 'rs': rs, 'cell_size': cell_size}
        self.display_partial_tile.emit(tx, tz, tile_np, cs, rs, cell_size)

    def _on_tiled_compute_finished(self, message):
        logger.info(f"Tiled compute finished: {message}")
        self.set_busy_mode.emit(False)
        try:
            if not self.tiled_results or not self.tiled_params:
                return

            cs, rs, cell_size = self.tiled_params.values()
            full_map = np.zeros((rs * cs, rs * cs), dtype=np.float32)
            for (tx, tz), tile_data in self.tiled_results.items():
                tile_core = tile_data[:-1, :-1]
                x_offset, z_offset = tx * cs, tz * cs
                full_map[z_offset:z_offset + cs, x_offset:x_offset + cs] = tile_core

            self.display_tiled_mesh.emit(full_map, cell_size)
            self.display_status_message.emit("Сборка тайлов завершена.", 5000)
        except Exception as e:
            self._on_compute_error(f"Ошибка сборки тайлов: {e}")
        finally:
            self.tiled_results.clear()
            self.tiled_params.clear()

    # --- COMMON ERROR HANDLING ---

    def _on_compute_error(self, message):
        self.set_busy_mode.emit(False)
        self.show_error_dialog.emit("Ошибка вычисления", message)
        self.display_status_message.emit(f"Ошибка: {message.splitlines()[0]}", 6000)