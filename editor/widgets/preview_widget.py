# editor/widgets/preview_widget.py
from __future__ import annotations
import gc
import logging
import math
import numpy as np
from PySide6 import QtWidgets, QtCore
from vispy import scene

# Исправлен путь импорта в соответствии с новой структурой
from editor.core.render_settings import RenderSettings

logger = logging.getLogger(__name__)


def _dir_from_angles(az_deg: float, alt_deg: float) -> tuple[float, float, float]:
    """Преобразует (азимут, высота) в единичный вектор направления света."""
    az = math.radians(az_deg)
    alt = math.radians(alt_deg)
    x = math.cos(alt) * math.cos(az)
    y = math.cos(alt) * math.sin(az)
    z = math.sin(alt)
    # Для SurfacePlot.light.direction нужен вектор «от источника света к объекту»:
    return (-x, -y, -z)


class Preview3DWidget(QtWidgets.QWidget):
    """Виджет для отображения 3D-превью карты высот с настраиваемым рендером."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mesh = None
        self._settings = RenderSettings()

        self.canvas = scene.SceneCanvas(keys="interactive", show=False, config={"samples": 4})
        self.view = self.canvas.central_widget.add_view()
        self.view.bgcolor = 'black'
        self.view.camera = scene.cameras.TurntableCamera(up='z', fov=self._settings.fov,
                                                         azimuth=45.0, elevation=30.0)
        scene.visuals.XYZAxis(parent=self.view.scene)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas.native)

        self._headlight_timer = QtCore.QTimer(self)
        self._headlight_timer.setInterval(33)  # ~30 FPS
        self._headlight_timer.timeout.connect(self._tick_headlight)
        self._last_cam_angles = (None, None)

    def _tick_headlight(self):
        if self._settings.light_mode != "headlight":
            return
        cam = self.view.camera
        # У TurntableCamera есть эти атрибуты; держим fallback
        az = getattr(cam, "azimuth", 45.0)
        el = getattr(cam, "elevation", 30.0)
        if (az, el) != self._last_cam_angles:
            self._last_cam_angles = (az, el)
            if self._mesh is not None and hasattr(self._mesh, "light"):
                self._mesh.light.direction = _dir_from_angles(az, el)
                self.canvas.update()

    def apply_render_settings(self, s: RenderSettings) -> None:
        self._settings = s
        cam = self.view.camera
        if hasattr(cam, "fov"):
            cam.fov = float(s.fov)

        if self._mesh is not None and hasattr(self._mesh, "light"):
            if s.light_mode == "headlight":
                # мгновенно синхронизируемся с камерой и запускаем «фонарик»
                az = getattr(cam, "azimuth", 45.0)
                el = getattr(cam, "elevation", 30.0)
                self._mesh.light.direction = _dir_from_angles(az, el)
                self._headlight_timer.start()
            else:
                # фиксированный «мировой» свет
                self._mesh.light.direction = _dir_from_angles(s.light_azimuth_deg, s.light_altitude_deg)
                self._headlight_timer.stop()

            self._mesh.light.ambient = float(s.ambient)
            base = float(max(0.05, min(2.0, s.diffuse)))
            self._mesh.color = (0.8 * base, 0.8 * base, 0.85 * base, 1.0)
            self._mesh.light.specular = (s.specular, s.specular, s.specular, 1.0)
            self._mesh.light.shininess = float(s.shininess)

        self.canvas.update()

    def update_mesh(self, height_map: np.ndarray, cell_size: float, **kwargs) -> None:
        """Обновляет геометрию 3D-ландшафта."""
        self._clear_scene()
        if height_map.shape[0] < 2 or height_map.shape[1] < 2:
            return
            
        assert height_map.dtype == np.float32, f"dtype={height_map.dtype}, нужен float32"
        assert np.all(np.isfinite(height_map)), "NaN/Inf в карте высот"

        s = self._settings
        z = (height_map * float(s.height_exaggeration)).astype(np.float32, copy=False)

        self._mesh = scene.visuals.SurfacePlot(
            z=z,
            parent=self.view.scene,
            shading='smooth',
            color=(0.8 * s.diffuse, 0.8 * s.diffuse, 0.85 * s.diffuse, 1.0)
        )

        if hasattr(self._mesh, 'light'):
            self.apply_render_settings(s)

        self._mesh.transform = scene.transforms.MatrixTransform()
        self._mesh.transform.scale((cell_size, cell_size, 1.0))
        
        h, w = z.shape
        zmin, zmax = float(z.min()), float(z.max())
        
        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        # Теперь сброс дистанции камеры происходит ТОЛЬКО если включен Auto frame
        if s.auto_frame:
            self.view.camera.set_range(x=(0, w * cell_size), y=(0, h * cell_size), z=(zmin, zmax))
            self.view.camera.distance = 1.8 * max(w * cell_size, h * cell_size)
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
            
        self.canvas.update()

    def _clear_scene(self) -> None:
        if self._mesh is not None:
            self._mesh.parent = None
            self._mesh = None
            gc.collect()

    def closeEvent(self, e):
        self._clear_scene()
        self.canvas.close()
        super().closeEvent(e)
