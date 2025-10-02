# editor/widgets/preview_widget.py
from __future__ import annotations
import gc
import logging
import math
import numpy as np
from PySide6 import QtWidgets, QtCore
from vispy import scene

from editor.core.render_settings import RenderSettings
from editor.render_palettes import make_colormap_from_palette, map_palette_cpu

logger = logging.getLogger(__name__)

def _normalize_01(z: np.ndarray) -> tuple[np.ndarray, float, float]:
    zmin = float(np.nanmin(z)); zmax = float(np.nanmax(z))
    if zmax - zmin < 1e-12:
        return np.zeros_like(z, dtype=np.float32), zmin, zmax
    out = (z - zmin) / (zmax - zmin)
    return out.astype(np.float32, copy=False), zmin, zmax

def _slope_mask(z: np.ndarray, cell_size: float, strength: float) -> np.ndarray:
    if strength <= 0.0:
        return np.ones_like(z, dtype=np.float32)
    gx = (np.roll(z, -1, axis=1) - np.roll(z, 1, axis=1)) / (2.0 * cell_size)
    gy = (np.roll(z, -1, axis=0) - np.roll(z, 1, axis=0)) / (2.0 * cell_size)
    slope = np.sqrt(gx*gx + gy*gy)
    slope = np.clip(slope * 0.5, 0.0, 1.0)
    mult = (1.0 - strength * slope).astype(np.float32)
    return mult

def _dir_from_angles(az_deg: float, alt_deg: float) -> tuple[float,float,float]:
    az = math.radians(az_deg); alt = math.radians(alt_deg)
    x =  math.cos(alt) * math.cos(az)
    y =  math.cos(alt) * math.sin(az)
    z =  math.sin(alt)
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
        lay = QtWidgets.QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.addWidget(self.canvas.native)

        self._headlight_timer = QtCore.QTimer(self)
        self._headlight_timer.setInterval(33)
        self._headlight_timer.timeout.connect(self._tick_headlight)
        self._last_cam_angles = (None, None)

    def _tick_headlight(self):
        if self._settings.light_mode != "headlight": return
        cam = self.view.camera
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
        if hasattr(cam, "fov"): cam.fov = float(s.fov)

        if self._mesh is not None:
            if hasattr(self._mesh, "light"): self._apply_light()
            # Если палитра не используется, цвет зависит от diffuse.
            # Обновляем цвет здесь, если палитра не активна, так как update_mesh не всегда вызывается
            if not s.use_palette:
                base = float(max(0.05, min(2.0, s.diffuse)))
                color = (0.8 * base, 0.8 * base, 0.8 * base, 1.0)
                self._mesh.unfreeze()
                self._mesh.color = color
                self._mesh.colors = None # Очищаем colors, если переключаемся на solid color
                self._mesh.freeze()

        self.canvas.update()

    def _apply_light(self):
        s = self._settings
        self._mesh.unfreeze()
        if s.light_mode == "headlight":
            self._headlight_timer.start()
            self._tick_headlight()
        else:
            self._headlight_timer.stop()
            L = _dir_from_angles(s.light_azimuth_deg, s.light_altitude_deg)
            self._mesh.light.direction = L
        
        self._mesh.light.ambient = float(s.ambient)
        self._mesh.light.specular = (s.specular, s.specular, s.specular, 1.0)
        self._mesh.light.shininess = float(s.shininess)
        self._mesh.freeze()

    def update_mesh(self, height_map: np.ndarray, cell_size: float, **kwargs) -> None:
        self._clear_scene()
        if height_map.shape[0] < 2 or height_map.shape[1] < 2: return
        assert height_map.dtype == np.float32
        assert np.all(np.isfinite(height_map))

        s = self._settings
        z = (height_map * float(s.height_exaggeration)).astype(np.float32, copy=False)

        cmap_arg = None
        clim_arg = None
        colors_arg = None
        color_arg = None

        if s.use_palette:
            if s.use_slope_darkening:
                z01, _, _ = _normalize_01(z)
                rgb = map_palette_cpu(z01, s.palette_name)
                mult = _slope_mask(z, cell_size, s.slope_strength)
                rgb = (rgb * mult[..., None]).clip(0.0, 1.0)
                a = np.ones((*rgb.shape[:2], 1), dtype=np.float32)
                colors_arg = np.concatenate([rgb, a], axis=-1)
            else:
                cmap_arg = make_colormap_from_palette(s.palette_name)
                clim_arg = (float(z.min()), float(z.max()))
        else:
            base = float(max(0.05, min(2.0, s.diffuse)))
            color_arg = (0.8 * base, 0.8 * base, 0.8 * base, 1.0)

        self._mesh = scene.visuals.SurfacePlot(z=z, parent=self.view.scene, shading='smooth',
                                               cmap=cmap_arg,
                                               clim=clim_arg,
                                               colors=colors_arg,
                                               color=color_arg)

        if hasattr(self._mesh, 'light'):
            self._apply_light()

        self._mesh.transform = scene.transforms.MatrixTransform()
        self._mesh.transform.scale((cell_size, cell_size, 1.0))

        h, w = z.shape
        zmin, zmax = float(z.min()), float(z.max())
        if s.auto_frame:
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
