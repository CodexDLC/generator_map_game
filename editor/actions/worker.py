# ==============================================================================
# Файл: editor/actions/worker.py
# ВЕРСИЯ 2.0: Исправлена ошибка 0xC0000005 (Access Violation) в TiledComputeWorker
#             путем добавления параметров тайла в сигнал partial_ready.
# ==============================================================================

from __future__ import annotations
import numpy as np
from PySide6 import QtCore

from ..graph_runner import run_graph


class ComputeWorker(QtCore.QObject):
    # ... (этот класс остается без изменений) ...
    set_busy = QtCore.Signal(bool)
    progress = QtCore.Signal(int, str)
    finished = QtCore.Signal(object, str)
    error = QtCore.Signal(str)

    def __init__(self, graph, context: dict):
        super().__init__()
        self._graph = graph
        self._ctx = dict(context or {})
        self._cancelled = False

    @QtCore.Slot()
    def run(self):
        try:
            self._cancelled = False
            self.set_busy.emit(True)
            self.progress.emit(0, "Инициализация…")

            def _tick(p, msg):
                if self._cancelled: return False
                self.progress.emit(int(p), str(msg))
                return True

            res = run_graph(self._graph, self._ctx, on_tick=_tick)
            if self._cancelled:
                self.set_busy.emit(False);
                self.error.emit("Отменено");
                return

            self.progress.emit(100, "Готово")
            self.set_busy.emit(False)
            self.finished.emit(res, "Single-compute завершён")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.set_busy.emit(False)
            self.error.emit(f"{e}\n--- TRACEBACK ---\n{tb}")

    @QtCore.Slot()
    def cancel(self):
        self._cancelled = True


class TiledComputeWorker(QtCore.QObject):
    set_busy = QtCore.Signal(bool)
    progress = QtCore.Signal(int, str)
    # --- ИЗМЕНЕНИЕ: Добавляем в сигнал параметры cs, rs, cell_size ---
    partial_ready = QtCore.Signal(int, int, object, int, int, float)  # tx, tz, tile, cs, rs, cell_size
    finished = QtCore.Signal(object, str)
    error = QtCore.Signal(str)

    def __init__(self, graph, base_context: dict, chunk_size: int, region_size: int):
        super().__init__()
        self._graph = graph
        self._base = dict(base_context or {})
        self._cs = int(chunk_size)
        self._rs = int(region_size)
        self._cancelled = False

    @QtCore.Slot()
    def run(self):
        try:
            self._cancelled = False
            self.set_busy.emit(True)
            cs, rs = self._cs, self._rs
            # --- ИЗМЕНЕНИЕ: Получаем cell_size один раз в начале ---
            cell_size = float(self._base.get("cell_size", 1.0))
            tiles_total = rs * rs

            full = np.zeros((cs * rs, cs * rs), dtype=np.float32)
            self.progress.emit(0, f"Старт тайлов: {rs}×{rs}")

            done = 0
            for tz in range(rs):
                if self._cancelled: self.error.emit("Отменено"); return
                for tx in range(rs):
                    if self._cancelled: self.error.emit("Отменено"); return

                    gx = float(self._base.get("global_x_offset", 0.0))
                    gz = float(self._base.get("global_z_offset", 0.0))
                    tile_size_with_apron = cs + 1
                    xs = np.arange(tile_size_with_apron, dtype=np.float32) + gx + tx * cs
                    zs = np.arange(tile_size_with_apron, dtype=np.float32) + gz + tz * cs
                    X, Z = np.meshgrid(xs, zs)

                    ctx = dict(self._base)
                    ctx.update({
                        "x_coords": X, "z_coords": Z,
                        "chunk_size": cs, "region_size_in_chunks": rs,
                        "tile_index": (tx, tz),
                    })
                    msg = f"Тайл ({tx + 1},{tz + 1})"

                    def _tick(p, m):
                        if self._cancelled: return False
                        self.progress.emit(int(((done + p / 100.0) / tiles_total) * 100), f"{msg}: {m}")
                        return True

                    tile_with_apron = run_graph(self._graph, ctx, on_tick=_tick)
                    visible_part = tile_with_apron[:-1, :-1]
                    z0, z1 = tz * cs, (tz + 1) * cs
                    x0, x1 = tx * cs, (tx + 1) * cs
                    full[z0:z1, x0:x1] = visible_part

                    # --- ИЗМЕНЕНИЕ: Отправляем сигнал с дополнительными параметрами ---
                    self.partial_ready.emit(tx, tz, tile_with_apron, cs, rs, cell_size)

                    done += 1
                    self.progress.emit(int(done / tiles_total * 100), f"{msg}: готов")

            self.set_busy.emit(False)
            self.progress.emit(100, "Все тайлы собраны")
            self.finished.emit(full, "Tiled-compute завершён")
        except Exception as e:
            self.set_busy.emit(False)
            self.error.emit(f"{e.__class__.__name__}: {e}")

    @QtCore.Slot()
    def cancel(self):
        self._cancelled = True