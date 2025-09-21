# ==============================================================================
# Файл: editor/preview_widget.py
# ВЕРСИЯ 2.1: Исправлена математика геометрии и камеры.
# ==============================================================================
import numpy as np
from vispy import scene
from PySide6 import QtWidgets


class Preview3DWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.vispy_canvas = scene.SceneCanvas(keys='interactive', show=False)
        self.view = self.vispy_canvas.central_widget.add_view()
        self.view.camera = 'turntable'
        self.view.camera.fov = 45
        scene.visuals.XYZAxis(parent=self.view.scene)
        self.surface_mesh = None
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.vispy_canvas.native)

    def update_mesh(self, height_map: np.ndarray, cell_size: float = 1.0):
        if height_map is None or height_map.size == 0:
            if self.surface_mesh: self.surface_mesh.visible = False
            return

        if self.surface_mesh: self.surface_mesh.visible = True

        print(f"[3D Preview] Обновление меша. Размер данных: {height_map.shape}")
        h, w = height_map.shape

        # ИСПРАВЛЕНИЕ (п.6.1): Правильный расчет координат сетки.
        x = np.linspace(0, (w - 1) * cell_size, w)
        z = np.linspace(0, (h - 1) * cell_size, h)

        if self.surface_mesh is None:
            self.surface_mesh = scene.visuals.SurfacePlot(x, z, height_map, shading='smooth',
                                                          color=(0.5, 0.5, 0.6, 1.0))
            self.view.add(self.surface_mesh)
        else:
            # ИСПРАВЛЕНИЕ (п.6.2): Обновляем все данные, включая сетку X/Z.
            self.surface_mesh.set_data(x=x, y=z, z=height_map)

        # ИСПРАВЛЕНИЕ (п.6.3): Адаптивная дистанция камеры.
        self.view.camera.set_range()
        self.view.camera.distance = max(w, h) * cell_size * 1.5