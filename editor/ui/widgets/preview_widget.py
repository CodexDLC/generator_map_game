# editor/ui/widgets/preview_widget.py
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


def _create_solid_mesh_data(z_data: np.ndarray, cell_size: float, s: RenderSettings) -> dict:
    """
    Создает вершины и полигоны для объемного блока ландшафта.
    """
    h, w = z_data.shape
    if h < 2 or w < 2:
        return {}

    z_min = 0.0

    # 1. Создаем сетку координат
    x = np.linspace(0, (w - 1) * cell_size, w, dtype=np.float32)
    y = np.linspace(0, (h - 1) * cell_size, h, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)

    # 2. Создаем вершины
    top_verts = np.stack([xx, yy, z_data], axis=-1)
    bottom_verts = np.stack([xx, yy, np.full_like(z_data, z_min)], axis=-1)
    all_verts = np.vstack([top_verts.reshape(-1, 3), bottom_verts.reshape(-1, 3)])

    bottom_offset = h * w

    # 3. Создаем полигоны (треугольники)
    faces = []
    # Верхняя поверхность
    for r in range(h - 1):
        for c in range(w - 1):
            i00, i10, i01, i11 = r * w + c, (r + 1) * w + c, r * w + (c + 1), (r + 1) * w + (c + 1)
            faces.extend([[i00, i10, i11], [i00, i11, i01]])
    # Нижняя поверхность (обратный порядок вершин)
    for r in range(h - 1):
        for c in range(w - 1):
            i00, i10, i01, i11 = bottom_offset + r * w + c, bottom_offset + (r + 1) * w + c, bottom_offset + r * w + (
                        c + 1), bottom_offset + (r + 1) * w + (c + 1)
            faces.extend([[i00, i11, i10], [i00, i01, i11]])
    # Стенки
    for c in range(w - 1):  # Передняя и задняя
        faces.extend([[c, c + 1, bottom_offset + c + 1], [c, bottom_offset + c + 1, bottom_offset + c]])
        i0, i1 = (h - 1) * w + c, (h - 1) * w + c + 1
        faces.extend([[i0, bottom_offset + i0, bottom_offset + i1], [i0, bottom_offset + i1, i1]])
    for r in range(h - 1):  # Левая и правая
        i0, i1 = r * w, (r + 1) * w
        faces.extend([[i0, bottom_offset + i0, bottom_offset + i1], [i0, bottom_offset + i1, i1]])
        i0, i1 = r * w + w - 1, (r + 1) * w + w - 1
        faces.extend([[i0, i1, bottom_offset + i1], [i0, bottom_offset + i1, bottom_offset + i0]])

    all_faces = np.array(faces, dtype=np.uint32)

    # 4. Генерируем цвета вершин
    # Верх
    z01, _, _ = _normalize_01(z_data)
    gy, gx = np.gradient(z_data, cell_size)
    normals = np.stack([-gx, -gy, np.ones_like(z_data)], axis=-1)
    normals /= np.linalg.norm(normals, axis=2, keepdims=True)
    light_dir = np.array(_dir_from_angles(s.light_azimuth_deg, s.light_altitude_deg), dtype=np.float32)
    diffuse = np.maximum(0, np.dot(normals, -light_dir))
    light = s.ambient + s.diffuse * diffuse
    rgb_height = map_palette_cpu(z01, s.palette_name)

    slope_mult = np.ones_like(z_data, dtype=np.float32)
    if s.use_slope_darkening:
        slope = np.sqrt(gx * gx + gy * gy)
        slope_mult = 1.0 - s.slope_strength * np.clip(slope * 0.5, 0.0, 1.0)

    final_rgb = np.clip(rgb_height * light[..., None] * slope_mult[..., None], 0.0, 1.0)
    top_colors = np.concatenate([final_rgb, np.ones_like(final_rgb[..., :1])], axis=-1).reshape(-1, 4)

    # Бока и низ - темно-серые
    side_color = np.array([0.15, 0.15, 0.18, 1.0], dtype=np.float32)
    bottom_colors = np.tile(side_color, (h * w, 1))

    all_colors = np.vstack([top_colors, bottom_colors])

    return {"vertices": all_verts, "faces": all_faces, "vertex_colors": all_colors}


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

        mesh_data = _create_solid_mesh_data(z, cell_size, s)
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