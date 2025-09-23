import numpy as np
from PySide6 import QtCore, QtWidgets
from vispy import scene
import sys
import logging

logger = logging.getLogger(__name__)

# Количество тайлов, обрабатываемых за один "тик" таймера
TILES_PER_TICK = 3
# Интервал таймера в миллисекундах
DRAIN_INTERVAL_MS = 16


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

        # --- НОВАЯ ЛОГИКА ОЧЕРЕДИ ---
        self._cs = 0
        self._rs = 0
        self._cell_size = 1.0
        self._tiles = {}
        self._tile_queue = {}  # ИЗМЕНЕНИЕ: Заменяем список на словарь
        self._drain_timer = QtCore.QTimer(self)
        self._drain_timer.timeout.connect(self._drain_tile_queue)
        self._last_layout_key = None


    def _reset_chunk_scene(self, cs: int, rs: int, cell_size: float):
        """Сбрасывает сцену при изменении параметров генерации."""
        self._cs = int(cs)
        self._rs = int(rs)
        self._cell_size = float(cell_size)
        self._tiles.clear()
        self._tile_queue.clear()

        # Очищаем контейнер от старых тайлов
        self._tile_root.parent = None
        self._tile_root = scene.Node(parent=self.view.scene)

        world_size = self._cs * self._rs * self._cell_size
        self.view.camera.set_range(x=(0, world_size), y=(0, world_size), z=(-world_size, world_size))
        self.view.camera.center = (world_size / 2, world_size / 2, 0)

        self._last_layout_key = (cs, rs, cell_size)
        logger.info(f"3D Preview scene reset: cs={cs}, rs={rs}, cell_size={cell_size}")

    def _make_or_update_tile_visual(self, tx: int, tz: int, tile_np: np.ndarray):
        """Создает или обновляет один тайл в сцене VisPy."""
        cs = self._cs
        tile_size_with_apron = cs + 1

        if tile_np.shape != (tile_size_with_apron, tile_size_with_apron):
            logger.warning(
                f"Tile ({tx},{tz}) has incorrect shape: {tile_np.shape}. Expected ({tile_size_with_apron},{tile_size_with_apron}). Skipping.")
            return

        x0 = tx * cs * self._cell_size
        z0 = tz * cs * self._cell_size

        x_coords_1d = x0 + np.arange(tile_size_with_apron, dtype=np.float32) * self._cell_size
        z_coords_1d = z0 + np.arange(tile_size_with_apron, dtype=np.float32) * self._cell_size

        key = (tx, tz)
        vis = self._tiles.get(key)
        if vis is None:
            vis = scene.visuals.SurfacePlot(
                x=x_coords_1d, y=z_coords_1d, z=tile_np,
                shading='smooth',
                color=(0.72, 0.72, 0.76, 1.0),
                parent=self._tile_root
            )
            units = float((tx + tz) & 7)
            vis.set_gl_state(polygon_offset=(1.0, units), depth_test=True)
            self._tiles[key] = vis
        else:
            vis.set_data(x=x_coords_1d, y=z_coords_1d, z=tile_np)

    def _drain_tile_queue(self):
        """Обрабатывает несколько тайлов из очереди за один вызов."""
        # ИЗМЕНЕНИЕ: Логика работы со словарем
        keys_to_process = list(self._tile_queue.keys())[:TILES_PER_TICK]
        if not keys_to_process:
            self._drain_timer.stop()
            logger.info("Tile queue is empty. Stopping drain timer.")
            return

        logger.debug(f"Draining {len(keys_to_process)} tiles from queue (remaining: {len(self._tile_queue) - len(keys_to_process)}).")
        for key in keys_to_process:
            tx, tz, tile_np = self._tile_queue.pop(key)
            self._make_or_update_tile_visual(tx, tz, tile_np)

    @QtCore.Slot(int, int, object, int, int, float)
    def on_tile_ready(self, tx: int, tz: int, tile_with_apron: np.ndarray, cs: int, rs: int, cell_size: float):
        """
        СЛОТ, ВЫЗЫВАЕМЫЙ ИЗ MainWindow. Безопасно добавляет тайл в очередь.
        """
        key = (cs, rs, cell_size)
        if self._last_layout_key != key:
            self._reset_chunk_scene(cs, rs, cell_size)

        # ИЗМЕНЕНИЕ: Добавляем в словарь по ключу координат
        tile_key = (tx, tz)
        self._tile_queue[tile_key] = (tx, tz, tile_with_apron.copy())

        if not self._drain_timer.isActive():
            logger.info("Starting tile queue drain timer.")
            self._drain_timer.start(DRAIN_INTERVAL_MS)

    def update_mesh(self, height_map, cell_size):
        """Обновляет сцену для монолитного рендера (кнопка APPLY)."""
        logger.info(f"Updating mesh for single-chunk render. Shape: {height_map.shape}")


        self._reset_chunk_scene(height_map.shape[1], 1, cell_size)

        # Искусственно создаем "фартук" для бесшовного отображения
        padded_map = np.pad(height_map, ((0, 1), (0, 1)), 'edge')

        self._tile_queue[(0, 0)] = (0, 0, padded_map)

        if not self._drain_timer.isActive():
            self._drain_timer.start(DRAIN_INTERVAL_MS)