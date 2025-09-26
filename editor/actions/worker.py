# ==============================================================================
# Файл: editor/actions/worker.py
# ВЕРСИЯ 2.4: Конструкторы обновлены для приема output_node.
# ==============================================================================
import logging
import time
import numpy as np
from PySide6 import QtCore
from pathlib import Path  # <--- Добавлен импорт

from ..graph_runner import run_graph

logger = logging.getLogger(__name__)


class ComputeWorker(QtCore.QObject):
    set_busy = QtCore.Signal(bool)
    progress = QtCore.Signal(int, str)
    finished = QtCore.Signal(object, str)
    error = QtCore.Signal(str)

    def __init__(self, output_node, context: dict):
        super().__init__()
        self._output_node = output_node
        self._ctx = dict(context or {})
        self._cancelled = False

    @QtCore.Slot()
    def run(self):
        """
        Единичный (цельный) расчёт: перед запуском графа гарантируем наличие
        двумерных сеток координат x_coords/z_coords в контексте.
        """
        try:
            # Копируем исходный контекст, чтобы не портить переданный словарь
            ctx = dict(self._ctx) if isinstance(self._ctx, dict) else {}

            # Базовые параметры из UI/проекта
            cs = int(ctx.get("chunk_size", 128))
            rs = int(ctx.get("region_size_in_chunks", 4))
            cell_size = float(ctx.get("cell_size", 1.0))
            gx = float(ctx.get("global_x_offset", 0.0))
            gz = float(ctx.get("global_z_offset", 0.0))

            # Полный размер региона (без тайловой сборки)
            H = W = rs * cs  # под превью и большинство нод этого хватает (без +1)

            # Если координат ещё нет — создаём 2D-сетки мировой системы
            if "x_coords" not in ctx or "z_coords" not in ctx:
                xs = gx + np.arange(W, dtype=np.float32) * cell_size
                zs = gz + np.arange(H, dtype=np.float32) * cell_size
                xg, zg = np.meshgrid(xs, zs, indexing="xy")  # формы (H, W)
                ctx["x_coords"] = xg
                ctx["z_coords"] = zg

            # Прогресс-колбэк (если нужен)
            def _tick(pct: int, msg: str | None = None):
                try:
                    if hasattr(self, "progress"):
                        self.progress.emit(int(pct), msg or "")
                except Exception:
                    pass

            # Запуск графа (OutputNode -> …)
            result = run_graph(self._output_node, ctx, on_tick=_tick)

            # Вернуть результат наверх (и показать сообщение)
            if hasattr(self, "finished"):
                self.finished.emit(result, "Готово")
        except Exception as e:
            logger.exception("Error in ComputeWorker.run()")
            if hasattr(self, "error"):
                self.error.emit(str(e))

    @QtCore.Slot()
    def cancel(self):
        logger.warning("ComputeWorker cancellation requested.")
        self._cancelled = True


class TiledComputeWorker(QtCore.QObject):
    set_busy = QtCore.Signal(bool)
    progress = QtCore.Signal(int, str)
    partial_ready = QtCore.Signal(int, int, object, int, int, float)
    finished = QtCore.Signal(str)
    error = QtCore.Signal(str)

    def __init__(self, output_node, base_context: dict, chunk_size: int, region_size: int):
        super().__init__()
        self._output_node = output_node
        self._base = dict(base_context or {})
        self._cs = int(chunk_size)
        self._rs = int(region_size)
        self._cancelled = False

    @QtCore.Slot()
    def run(self):
        try:
            logger.info(f"TiledComputeWorker started for {self._rs}x{self._rs} tiles.")
            total_start_time = time.perf_counter()

            self._cancelled = False
            self.set_busy.emit(True)
            cs, rs = self._cs, self._rs
            cell_size = float(self._base.get("cell_size", 1.0))
            tiles_total = rs * rs

            self.progress.emit(0, f"Старт тайлов: {rs}×{rs}")

            done = 0
            for tz in range(rs):
                if self._cancelled: self.error.emit("Отменено"); return
                for tx in range(rs):
                    if self._cancelled: self.error.emit("Отменено"); return

                    tile_start_time = time.perf_counter()

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
                        percent = int(((done + p / 100.0) / tiles_total) * 100)
                        self.progress.emit(percent, f"{msg}: {m}")
                        return True

                    tile_with_apron = run_graph(self._output_node, ctx, on_tick=_tick)

                    tile_end_time = time.perf_counter()
                    logger.debug(f"Tile ({tx},{tz}) computed in {tile_end_time - tile_start_time:.3f} seconds.")

                    self.partial_ready.emit(tx, tz, tile_with_apron, cs, rs, cell_size)

                    done += 1
                    self.progress.emit(int(done / tiles_total * 100), f"{msg}: готов")

            total_end_time = time.perf_counter()
            logger.info(f"All tiles computed in {total_end_time - total_start_time:.3f} seconds.")

            self.set_busy.emit(False)
            self.progress.emit(100, "Все тайлы собраны")
            self.finished.emit("Tiled-compute завершён")

        except Exception as e:
            logger.exception("Error during tiled computation.")
            self.set_busy.emit(False)
            self.error.emit(f"{e.__class__.__name__}: {e}")

    @QtCore.Slot()
    def cancel(self):
        logger.warning("TiledComputeWorker cancellation requested.")
        self._cancelled = True


# --- ДОБАВЛЕН НОВЫЙ КЛАСС-ЗАГЛУШКА ---
class GenerationWorker(QtCore.QObject):
    progress = QtCore.Signal(int, str)
    finished = QtCore.Signal(str)
    error = QtCore.Signal(str)

    def __init__(self, graph_data: dict, artifacts_root):
        super().__init__()
        self._graph_data = dict(graph_data)
        self._artifacts_root = Path(str(artifacts_root))
        self._is_stopped = False

    @QtCore.Slot()
    def run(self):
        try:
            logger.info(f"GenerationWorker started. Artifacts will be saved to: {self._artifacts_root}")
            self.progress.emit(5, "Подготовка артефактов…")
            if self._is_stopped: return

            self._artifacts_root.mkdir(parents=True, exist_ok=True)
            out = self._artifacts_root / "node_graph.json"

            import json
            with open(out, "w", encoding="utf-8") as f:
                json.dump(self._graph_data.get("node_graph", {}), f, ensure_ascii=False, indent=2)

            if self._is_stopped: return
            self.progress.emit(100, "Экспорт графа завершён")
            self.finished.emit(f"Артефакты сохранены: {out}")
        except Exception as e:
            logger.exception("Error in GenerationWorker.")
            self.error.emit(str(e))

    def stop(self):
        logger.warning("GenerationWorker stop requested.")
        self._is_stopped = True