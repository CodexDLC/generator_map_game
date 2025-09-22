import numpy as np
from PySide6 import QtCore, QtWidgets
from vispy import scene
import sys, time

TILES_PER_TICK = 3
DRAIN_INTERVAL_MS = 16


def _vtrace(msg):
    print(f"[TRACE/VIEW] {msg}", flush=True, file=sys.stdout)


class Preview3DWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = scene.SceneCanvas(keys="interactive", show=False, config={"samples": 4})
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = "turntable"
        scene.visuals.XYZAxis(parent=self.view.scene)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas.native)

        # Узел-контейнер для всех тайлов
        self._tile_root = scene.Node(parent=self.view.scene)

        # Состояние чанкового рендера
        self._cs = 0
        self._rs = 0
        self._cell_size = 1.0
        self._tiles = {}
        self._tile_queue = []
        self._drain_timer = QtCore.QTimer(self)
        self._drain_timer.timeout.connect(self._drain_tile_queue)
        self._last_layout_key = None

    def _reset_chunk_scene(self, cs: int, rs: int, cell_size: float):
        self._cs = int(cs)
        self._rs = int(rs)
        self._cell_size = float(cell_size)
        self._tiles.clear()
        self._tile_queue.clear()

        # Очищаем контейнер от старых тайлов
        self._tile_root.parent = None
        self._tile_root = scene.Node(parent=self.view.scene)

        # Настраиваем камеру на весь регион
        world_size = self._cs * self._rs * self._cell_size
        self.view.camera.set_range(x=(0, world_size), y=(0, world_size), z=(-world_size, world_size))
        self.view.camera.center = (world_size / 2, world_size / 2, 0)

        self._last_layout_key = (self._cs, self._rs, self._cell_size)
        _vtrace(f"Chunk scene reset: cs={cs}, rs={rs}, cell_size={cell_size}")

    def _make_or_update_tile_visual(self, tx: int, tz: int, tile_np: np.ndarray):
        cs = self._cs

        tile_size_with_apron = cs + 1
        # Проверка размера остается, она важна
        assert tile_np.shape == (tile_size_with_apron, tile_size_with_apron), "Tile has incorrect shape!"

        x0 = tx * cs * self._cell_size
        z0 = tz * cs * self._cell_size

        # --- ИСПРАВЛЕНИЕ: Создаем ОДНОМЕРНЫЕ массивы для x и y ---
        x_coords_1d = x0 + np.arange(tile_size_with_apron, dtype=np.float32) * self._cell_size
        z_coords_1d = z0 + np.arange(tile_size_with_apron, dtype=np.float32) * self._cell_size
        # Meshgrid больше не передается в SurfacePlot

        key = (tx, tz)
        vis = self._tiles.get(key)
        if vis is None:
            # --- ИСПРАВЛЕНИЕ: Передаем 1D массивы в x и y ---
            vis = scene.visuals.SurfacePlot(
                x=x_coords_1d, y=z_coords_1d, z=tile_np, # <-- ИСПРАВЛЕНО
                shading='smooth',
                color=(0.72, 0.72, 0.76, 1.0),
                parent=self._tile_root
            )
            units = float((tx + tz) & 7)
            vis.set_gl_state(polygon_offset=(1.0, units), depth_test=True)
            self._tiles[key] = vis
        else:
            # --- ИСПРАВЛЕНИЕ: set_data тоже ожидает 1D массивы ---
            vis.set_data(x=x_coords_1d, y=z_coords_1d, z=tile_np)

    def _drain_tile_queue(self):
        n = min(TILES_PER_TICK, len(self._tile_queue))
        if n <= 0:
            self._drain_timer.stop()
            return

        for _ in range(n):
            tx, tz, tile_np = self._tile_queue.pop(0)
            self._make_or_update_tile_visual(tx, tz, tile_np)

    @QtCore.Slot(object, str)
    def on_compute_finished(self, result, message):
        # Этот слот теперь будет вызываться для всего региона целиком
        # Если мы в чанковом режиме, то он просто сигнализирует о завершении
        if self._tile_queue:
            # Даем таймеру шанс обработать оставшиеся тайлы
            QtCore.QTimer.singleShot(DRAIN_INTERVAL_MS * 2, lambda: self.on_compute_finished(result, message))
        _vtrace(f"Compute finished: {message}")

    @QtCore.Slot(int, int, object)
    def update_tile(self, tx: int, tz: int, tile_map: np.ndarray):
        # Этот слот был в старой версии, теперь мы получаем все данные
        # из partial_ready воркера, поэтому он может быть не нужен,
        # но оставим его для совместимости, если где-то используется.
        pass

    def on_tile_ready(self, tx: int, tz: int, tile_with_apron: np.ndarray, cs: int, rs: int, cell_size: float):
        # Этот метод будет вызываться напрямую из MainWindow

        # Используем переданные параметры для проверки, нужно ли сбросить сцену
        key = (cs, rs, cell_size)
        if self._last_layout_key != key:
            self._reset_chunk_scene(cs, rs, cell_size)

        self._tile_queue.append((tx, tz, tile_with_apron.copy()))
        if not self._drain_timer.isActive():
            self._drain_timer.start(DRAIN_INTERVAL_MS)

    def update_mesh(self, height_map, cell_size):
        # Этот метод для монолитного рендера (кнопка APPLY)
        # Он должен сбросить сцену под размер 1x1 чанк
        self._reset_chunk_scene(height_map.shape[1], 1, cell_size)

        # --- ИСПРАВЛЕНИЕ: Искусственно создаем "фартук" для монолитного блока ---
        # np.pad добавляет 1 пиксель по краям, дублируя крайние значения
        padded_map = np.pad(height_map, ((0, 1), (0, 1)), 'edge')

        # Вызываем _make_or_update_tile_visual, который теперь получит данные
        # правильного размера (например, 513x513)
        self._make_or_update_tile_visual(0, 0, padded_map)