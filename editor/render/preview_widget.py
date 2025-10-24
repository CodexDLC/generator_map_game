# editor/render/preview_widget.py
from __future__ import annotations
import gc
import logging
# УДАЛЕНО: math
import numpy as np
from PySide6 import QtWidgets, QtCore
from vispy import scene

from editor.core.render_settings import RenderSettings

from editor.render.region import region_mesh_builder

logger = logging.getLogger(__name__)


class Preview3DWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._mesh = None
        self._settings = RenderSettings()

        self.canvas = scene.SceneCanvas(keys="interactive", show=False, config={"samples": 4})
        self.view = self.canvas.central_widget.add_view()
        self.view.bgcolor = 'black'
        self.view.camera = scene.cameras.TurntableCamera(up='z', fov=self._settings.fov, azimuth=45.0, elevation=30.0)

        self._compass = scene.visuals.Arrow(
            pos=np.array([[0, 0, 0], [0, 25, 0]]),
            color='white',
            arrow_size=12.0,
            arrow_type='triangle_60',
            parent=self.canvas.scene
        )
        self._compass.transform = scene.transforms.STTransform()
        self._compass.visible = False

        scene.visuals.XYZAxis(parent=self.view.scene)
        lay = QtWidgets.QVBoxLayout(self);
        lay.setContentsMargins(0, 0, 0, 0);
        lay.addWidget(self.canvas.native)

    def _clear_scene(self) -> None:
        if self._mesh is not None:
            self._mesh.parent = None
            self._mesh = None
        gc.collect()

    def apply_render_settings(self, s: RenderSettings) -> None:
        self._settings = s
        cam = self.view.camera
        if hasattr(cam, "fov"): cam.fov = float(s.fov)
        if self.parent() and hasattr(self.parent(), '_on_apply_clicked'):
            QtCore.QTimer.singleShot(0, self.parent()._on_apply_clicked)

    def update_mesh(self, height_map: np.ndarray, cell_size: float, **kwargs) -> None:
        self._clear_scene()
        if not isinstance(height_map, np.ndarray) or height_map.shape[0] < 2 or height_map.shape[1] < 2:
            return
        if not np.all(np.isfinite(height_map)):
            return

        s = self._settings
        z = np.ascontiguousarray(height_map * float(s.height_exaggeration), dtype=np.float32)

        # --- ИЗМЕНЕНИЕ ЗДЕСЬ: Вызываем функцию из нового модуля ---
        mesh_data = region_mesh_builder._create_solid_mesh_data(z, cell_size, s)
        # --------------------------------------------------------

        if not mesh_data:
            return

        self._mesh = scene.visuals.Mesh(
            vertices=mesh_data["vertices"],
            faces=mesh_data["faces"],
            vertex_colors=mesh_data["vertex_colors"],
            shading=None,
            parent=self.view.scene
        )

        north_vector_2d = kwargs.get("north_vector_2d")
        if north_vector_2d is not None and np.linalg.norm(north_vector_2d) > 1e-6:
            angle_deg = np.rad2deg(np.arctan2(north_vector_2d[1], north_vector_2d[0])) - 90
            canvas_w, canvas_h = self.canvas.size
            pos = (40, canvas_h - 40, 0)

            logger.debug(f"Compass: vector={north_vector_2d}, angle={angle_deg:.1f}, pos={pos}")

            self._compass.transform.translate = pos
            self._compass.transform.rotation = angle_deg
            self._compass.visible = True
        else:
            self._compass.visible = False

        if s.auto_frame:
            h, w = height_map.shape
            zmin, zmax = float(np.nanmin(z)), float(np.nanmax(z))
            self.view.camera.set_range(x=(0, w * cell_size), y=(0, h * cell_size), z=(zmin, zmax))
            self.view.camera.distance = 1.8 * max(w * cell_size, h * cell_size)

        self.canvas.update()

    def closeEvent(self, e):
        self._clear_scene()
        self.canvas.close()
        super().closeEvent(e)