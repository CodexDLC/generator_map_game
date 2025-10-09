# editor/logic/background_workers.py
from __future__ import annotations
import traceback
from PySide6 import QtCore

# ИЗМЕНЕНИЕ: импортируем новую функцию
from editor.logic import preview_logic, planet_view_logic

class WorkerSignals(QtCore.QObject):
    finished = QtCore.Signal(object)
    error = QtCore.Signal(str)
    progress = QtCore.Signal(int, str)


class PlanetGenerationWorker(QtCore.QRunnable):
    def __init__(self, main_window):
        super().__init__()
        self.signals = WorkerSignals()
        self._mw = main_window

    @QtCore.Slot()
    def run(self):
        try:
            result_data = planet_view_logic.orchestrate_planet_update(self._mw)
            self.signals.finished.emit(result_data)
        except Exception as e:
            tb = traceback.format_exc()
            self.signals.error.emit(f"Ошибка при генерации планеты: {e}\n\n{tb}")


class PreviewGenerationWorker(QtCore.QRunnable):
    def __init__(self, main_window):
        super().__init__()
        self.signals = WorkerSignals()
        self._mw = main_window

    @QtCore.Slot()
    def run(self):
        try:
            # ИЗМЕНЕНИЕ: Вызываем функцию, которая только считает данные
            result_data = preview_logic.generate_preview_data(self._mw)
            self.signals.finished.emit(result_data)
        except Exception as e:
            tb = traceback.format_exc()
            self.signals.error.emit(f"Ошибка генерации превью: {e}\n\n{tb}")