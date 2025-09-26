# editor/compute_manager.py
from __future__ import annotations
import logging
from typing import Optional, Tuple, Dict, Any

import numpy as np
from PySide6 import QtCore

# твои воркеры лежат тут же
from .actions.worker import ComputeWorker  # TiledComputeWorker нам больше не нужен

logger = logging.getLogger(__name__)


class ComputeManager(QtCore.QObject):
    """
    Диспетчер вычислений графа (только цельный расчёт).
    - Коалесинг: если пока идёт вычисление, новый запрос откладывается (pending)
      и стартует один раз после завершения текущего.
    - Корректное завершение потоков: quit()+wait(), shutdown() при закрытии окна.
    """

    # Сигналы в MainWindow/Preview
    display_mesh = QtCore.Signal(object, float)       # (heightmap, cell_size)
    display_status_message = QtCore.Signal(str, int)  # (text, msec)
    show_error_dialog = QtCore.Signal(str, str)       # (title, text)
    set_busy_mode = QtCore.Signal(bool)               # включить/выключить "занято"

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        self.thread: Optional[QtCore.QThread] = None
        self.worker: Optional[QtCore.QObject] = None

        self._running: bool = False
        self._pending: Optional[Tuple[str, Dict[str, Any]]] = None  # ('single', params)

    # ---------------------------------------------------------------- lifecycle

    def shutdown(self):
        """Остановить текущий воркер и дождаться завершения потока (на закрытии приложения)."""
        try:
            if self.worker and hasattr(self.worker, "stop"):
                try:
                    self.worker.stop()  # мягкая отмена, если поддерживается
                except Exception:
                    pass
            if self.thread:
                try:
                    self.thread.quit()
                    self.thread.wait(5000)  # до 5 секунд на корректное завершение
                except Exception:
                    pass
        finally:
            self.thread = None
            self.worker = None
            self._running = False
            self._pending = None
            self.set_busy_mode.emit(False)

    # ---------------------------------------------------------- single compute

    def start_single_compute(self, output_node, context: dict):
        """
        Запуск цельного расчёта.
        Если задача уже идёт — откладываем один повтор с последними параметрами.
        """
        if self._running:
            self._pending = ('single', {'output_node': output_node, 'context': context})
            logger.info("Compute running -> coalesce new 'single' request")
            self.display_status_message.emit("Расчёт в процессе… Перезапущу с последними параметрами.", 2000)
            return

        # Создаём воркер и поток
        self.thread = QtCore.QThread()
        self.worker = ComputeWorker(output_node, context)
        self.worker.moveToThread(self.thread)

        # Прогресс (если воркер его шлёт)
        if hasattr(self.worker, "progress"):
            # type: ignore[attr-defined]
            self.worker.progress.connect(lambda p, m: self.display_status_message.emit(m or "", 300))

        # Результат
        if hasattr(self.worker, "finished"):
            # type: ignore[attr-defined]
            self.worker.finished.connect(self._on_worker_finished)
            # после завершения — закрыть поток
            # type: ignore[attr-defined]
            self.worker.finished.connect(self._thread_quit)

        # Ошибка
        if hasattr(self.worker, "error"):
            # type: ignore[attr-defined]
            self.worker.error.connect(self._on_compute_error)
            # type: ignore[attr-defined]
            self.worker.error.connect(self._thread_quit)

        # Запуск
        self.thread.started.connect(self._thread_run_entry)
        self.thread.finished.connect(self._on_thread_finished)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

        self._running = True
        self.set_busy_mode.emit(True)

    # ---------------------------------------------------------- compatibility

    def start_tiled_compute(self, output_node, context: dict):
        """
        Совместимость со старой кнопкой «APPLY (tiled)».
        Сейчас тайлов нет: просто перенаправляем на цельный расчёт.
        """
        logger.info("Tiled compute is disabled -> redirect to single compute")
        self.start_single_compute(output_node, context)

    # --------------------------------------------------------------- slots

    @QtCore.Slot()
    def _thread_run_entry(self):
        if self.worker and hasattr(self.worker, "run"):
            try:
                # type: ignore[attr-defined]
                self.worker.run()
            except Exception as e:
                logger.exception("Worker.run() raised: %s", e)
                self._thread_quit()

    @QtCore.Slot()
    def _thread_quit(self):
        if self.thread:
            try:
                self.thread.quit()
            except Exception:
                pass

    @QtCore.Slot(object, str)
    def _on_worker_finished(self, result, message: str):
        """Результат от воркера (цельная карта)."""
        try:
            if result is not None:
                cell_size = float(self.main_window.cell_size_input.value())
                # проверим sanity, чтобы не убить превью
                arr = np.asarray(result)

                if arr.ndim == 2 and np.isfinite(arr).all():
                    self.display_mesh.emit(arr, cell_size)
                else:
                    self.display_status_message.emit("Получена некорректная карта (пропускаю).", 4000)
            if message:
                self.display_status_message.emit(message, 4000)
            else:
                self.display_status_message.emit("Готово.", 2500)
        finally:
            # поток закроется через _thread_quit -> finished -> _on_thread_finished

            pass

    @QtCore.Slot(str)
    def _on_compute_error(self, message: str):
        logger.error("Compute error: %s", message)
        self.show_error_dialog.emit("Ошибка вычисления", message)
        self.display_status_message.emit(f"Ошибка: {message.splitlines()[0]}", 6000)

    @QtCore.Slot()
    def _on_thread_finished(self):
        """Поток завершён — чистим и, если нужно, запускаем отложенный запрос."""
        self.thread = None
        self.worker = None
        self._running = False
        self.set_busy_mode.emit(False)

        if self._pending:
            job, params = self._pending
            self._pending = None
            if job == 'single':
                self.start_single_compute(**params)
