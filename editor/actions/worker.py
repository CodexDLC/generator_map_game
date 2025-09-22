# ==============================================================================
# Файл: editor/actions/worker.py
# Назначение: Чистые воркеры для single/tiled вычислений графа.
# НИКАКИХ импортов VisPy/Qt-виджетов/движка. Только numpy и graph_runner.
# ==============================================================================

from __future__ import annotations
import numpy as np
from PySide6 import QtCore

# Воркеры лежат в editor/actions, а раннер — в editor/graph_runner.py
from ..graph_runner import run_graph


class ComputeWorker(QtCore.QObject):
    set_busy = QtCore.Signal(bool)
    progress = QtCore.Signal(int, str)
    finished = QtCore.Signal(object, str)   # (result_array, message)
    error    = QtCore.Signal(str)

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
                if self._cancelled:
                    return False
                self.progress.emit(int(p), str(msg))
                return True

            res = run_graph(self._graph, self._ctx, on_tick=_tick)
            if self._cancelled:
                self.set_busy.emit(False)
                self.error.emit("Отменено")
                return

            self.progress.emit(100, "Готово")
            self.set_busy.emit(False)
            self.finished.emit(res, "Single-compute завершён")
        except Exception as e:
            self.set_busy.emit(False)
            self.error.emit(f"{e}")

    @QtCore.Slot()
    def cancel(self):
        self._cancelled = True


class TiledComputeWorker(QtCore.QObject):
    set_busy      = QtCore.Signal(bool)
    progress      = QtCore.Signal(int, str)
    partial_ready = QtCore.Signal(int, int, object)  # tx, tz, tile_array
    finished      = QtCore.Signal(object, str)       # full_array, message
    error         = QtCore.Signal(str)

    def __init__(self, graph, base_context: dict, chunk_size: int, region_size: int):
        super().__init__()
        self._graph = graph
        self._base  = dict(base_context or {})
        self._cs    = int(chunk_size)
        self._rs    = int(region_size)
        self._cancelled = False

    @QtCore.Slot()
    def run(self):
        try:
            self._cancelled = False
            self.set_busy.emit(True)
            cs, rs = self._cs, self._rs
            tiles_total = rs * rs
            H = cs * rs
            full = np.zeros((H, H), dtype=np.float32)
            self.progress.emit(0, f"Старт тайлов: {rs}×{rs}")

            done = 0
            for tz in range(rs):
                if self._cancelled:
                    self.set_busy.emit(False); self.error.emit("Отменено"); return
                for tx in range(rs):
                    if self._cancelled:
                        self.set_busy.emit(False); self.error.emit("Отменено"); return

                    gx = float(self._base.get("global_x_offset", 0.0))
                    gz = float(self._base.get("global_z_offset", 0.0))

                    # Локальные координаты тайла
                    xs = np.arange(cs, dtype=np.float32) + gx + tx * cs
                    zs = np.arange(cs, dtype=np.float32) + gz + tz * cs
                    X, Z = np.meshgrid(xs, zs)

                    ctx = dict(self._base)
                    ctx.update({
                        "x_coords": X,
                        "z_coords": Z,
                        "chunk_size": cs,
                        "region_size_in_chunks": rs,
                        "tile_index": (tx, tz),
                    })

                    msg = f"Тайл ({tx+1},{tz+1})"
                    def _tick(p, m):
                        if self._cancelled: return False
                        self.progress.emit(int(((done + p/100.0)/tiles_total)*100), f"{msg}: {m}")
                        return True

                    tile = run_graph(self._graph, ctx, on_tick=_tick)

                    # Вставка и событие о частичном результате
                    z0, z1 = tz*cs, (tz+1)*cs
                    x0, x1 = tx*cs, (tx+1)*cs
                    full[z0:z1, x0:x1] = tile
                    self.partial_ready.emit(tx, tz, tile)

                    done += 1
                    self.progress.emit(int(done / tiles_total * 100), f"{msg}: готов")

            self.set_busy.emit(False)
            self.progress.emit(100, "Все тайлы собраны")
            self.finished.emit(full, "Tiled-compute завершён")
        except Exception as e:
            self.set_busy.emit(False)
            self.error.emit(f"{e}")

    @QtCore.Slot()
    def cancel(self):
        self._cancelled = True
