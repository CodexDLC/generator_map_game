# editor/widgets/preview_widget.py
from __future__ import annotations
import gc
import logging
import math
import numpy as np
from PySide6 import QtWidgets, QtCore
from vispy import scene

from editor.core.render_settings import RenderSettings
from editor.render_palettes import map_palette_cpu

logger = logging.getLogger(__name__)

def _normalize_01(z: np.ndarray) -> tuple[np.ndarray, float, float]:
    zmin = float(np.nanmin(z));
    zmax = float(np.nanmax(z))
    if zmax - zmin < 1e-12:
        return np.zeros_like(z, dtype=np.float32), zmin, zmax
    out = (z - zmin) / (zmax - zmin)
    return out.astype(np.float32, copy=False), zmin, zmax

def _dir_from_angles(az_deg: float, alt_deg: float) -> tuple[float, float, float]:
    az = math.radians(az_deg);
    alt = math.radians(alt_deg)
    x = math.cos(alt) * math.cos(az)
    y = math.cos(alt) * math.sin(az)
    z = math.sin(alt)
    return (-x, -y, -z)

class Preview3DWidget(QtWidgets.QWidget):
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
        lay = QtWidgets.QVBoxLayout(self);
        lay.setContentsMargins(0, 0, 0, 0);
        lay.addWidget(self.canvas.native)

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
        
        z = (height_map * float(s.height_exaggeration)).astype(np.float32, copy=False)
        
        self._mesh = scene.visuals.SurfacePlot(z=z, parent=self.view.scene)
        self._mesh.unfreeze()

        if s.use_palette:
            self._mesh.shading = None
            z01, _, _ = _normalize_01(z)
            gy, gx = np.gradient(z, cell_size)
            normals = np.stack([-gx, -gy, np.ones_like(z)], axis=-1)
            norm = np.linalg.norm(normals, axis=2, keepdims=True)
            normals /= np.maximum(norm, 1e-6)
            light_dir = np.array(_dir_from_angles(s.light_azimuth_deg, s.light_altitude_deg), dtype=np.float32)
            diffuse_intensity = np.maximum(0, np.dot(normals, -light_dir))
            light_intensity = s.ambient + s.diffuse * diffuse_intensity
            rgb_height = map_palette_cpu(z01, s.palette_name)
            slope_mult = np.ones_like(z, dtype=np.float32)
            if s.use_slope_darkening:
                slope = np.sqrt(gx * gx + gy * gy)
                slope_clipped = np.clip(slope * 0.5, 0.0, 1.0)
                slope_mult = 1.0 - s.slope_strength * slope_clipped
            final_rgb = rgb_height * light_intensity[..., None] * slope_mult[..., None]
            final_rgb = np.clip(final_rgb, 0.0, 1.0)
            alpha = np.ones((*final_rgb.shape[:2], 1), dtype=np.float32)
            rgba_3d = np.concatenate([final_rgb, alpha], axis=-1)
            self._mesh.mesh_data.set_vertex_colors(rgba_3d.reshape(-1, 4))
            self._mesh._need_color_update = True
        else:
            self._mesh.shading = 'smooth'
            base = float(max(0.05, min(2.0, s.diffuse)))
            self._mesh.color = (0.8 * base, 0.8 * base, 0.8 * base, 1.0)
            if hasattr(self._mesh, 'light'):
                L = _dir_from_angles(s.light_azimuth_deg, s.light_altitude_deg)
                self._mesh.light.direction = L
                self._mesh.light.ambient = float(s.ambient)
                self._mesh.light.specular = (s.specular, s.specular, s.specular, 1.0)
                self._mesh.light.shininess = float(s.shininess)

        self._mesh.freeze()
        self._mesh.transform = scene.transforms.MatrixTransform()
        self._mesh.transform.scale((cell_size, cell_size, 1.0))

        if s.auto_frame:
            h, w = height_map.shape
            zmin, zmax = float(np.nanmin(z)), float(np.nanmax(z))
            self.view.camera.set_range(x=(0, w * cell_size), y=(0, h * cell_size), z=(zmin, zmax))
            self.view.camera.distance = 1.8 * max(w * cell_size, h * cell_size)

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
