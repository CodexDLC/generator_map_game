# editor/preview_widget.py
# -----------------------------------------------------------------------------
# Минималистичная версия 3D-превью на VisPy.
# - Использует SurfacePlot как самый надёжный способ.
# - Убраны все лишние функции и старый код.
# - Принимает на вход те же данные: height_map и cell_size.
# -----------------------------------------------------------------------------

from __future__ import annotations

import gc
import logging
import numpy as np
from PySide6 import QtWidgets
from vispy import scene

logger = logging.getLogger(__name__)


## --- ОСНОВНОЙ КЛАСС ВИДЖЕТА ---

class Preview3DWidget(QtWidgets.QWidget):
    """
    Виджет для отображения 3D-превью карты высот.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # 1. Инициализация переменных
        self._mesh = None

        # 2. Создание холста и 3D-вида
        self.canvas = scene.SceneCanvas(keys="interactive", show=False, config={"samples": 4})
        self.view = self.canvas.central_widget.add_view()
        self.view.bgcolor = 'black'

        # 3. Настройка камеры
        # Используем 'z' как ось высоты, это стандарт для SurfacePlot
        self.view.camera = scene.cameras.TurntableCamera(up='z', fov=45.0, azimuth=45.0, elevation=30.0)

        # 4. Добавление осей для ориентации в пространстве
        scene.visuals.XYZAxis(parent=self.view.scene)

        # 5. Настройка вёрстки Qt
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas.native)

    ## --- ОСНОВНЫЕ МЕТОДЫ ---

    def update_mesh(self, height_map: np.ndarray, cell_size: float, **kwargs) -> None:
        """
        Самая простая и совместимая версия.
        Создаёт 3D-ландшафт с освещением, но без цветовой карты.
        """
        # 1. Очищаем предыдущий ландшафт
        self._clear_scene()

        # 2. Проверяем, что карта не слишком маленькая
        if height_map.shape[0] < 2 or height_map.shape[1] < 2:
            return

        # --- Диагностика и защита ---
        assert height_map.dtype == np.float32, f"Карта высот должна быть float32, а не {height_map.dtype}"
        assert np.all(np.isfinite(height_map)), "В карте высот есть бесконечные или NaN значения"
        logger.debug("Height map for preview: dtype=%s min=%.6f max=%.6f",
                     height_map.dtype, float(height_map.min()), float(height_map.max()))
        # --- Конец диагностики ---

        # 3. Создаём 3D-ландшафт (без cmap)
        self._mesh = scene.visuals.SurfacePlot(
            z=height_map,  # Уже float32
            parent=self.view.scene,
            shading='smooth',  # Включаем встроенное освещение
            color=(0.8, 0.8, 0.9, 1.0)  # Задаем базовый цвет
        )
        if hasattr(self._mesh, 'light'):
            # Убираем глянцевые блики, делая зеркальный цвет черным
            self._mesh.light.specular = (0.0, 0.0, 0.0, 1.0)

            # Немного увеличиваем рассеянное освещение, чтобы тени не были слишком темными
            self._mesh.light.ambient = 0.4

        # 4. Масштабируем модель согласно размеру ячейки
        self._mesh.transform = scene.transforms.MatrixTransform()
        self._mesh.transform.scale((cell_size, cell_size, 1.0))

        # 5. Настраиваем камеру, чтобы она смотрела на новый ландшафт
        h, w = height_map.shape
        z_min, z_max = height_map.min(), height_map.max()

        self.view.camera.set_range(
            x=(0, w * cell_size),
            y=(0, h * cell_size),
            z=(z_min, z_max)
        )
        self.view.camera.distance = 1.8 * max(w * cell_size, h * cell_size)

        # 6. Обновляем холст, чтобы показать изменения
        self.canvas.update()

    ## --- СЛУЖЕБНЫЕ МЕТОДЫ ---

    def _clear_scene(self) -> None:
        """
        Удаляет старый меш из сцены.
        """
        if self._mesh is not None:
            self._mesh.parent = None  # Отвязываем от сцены
            self._mesh = None
            gc.collect()  # Собираем мусор

    def closeEvent(self, e):
        """
        Корректно закрывает холст VisPy при закрытии виджета.
        """
        self._clear_scene()
        self.canvas.close()
        super().closeEvent(e)
