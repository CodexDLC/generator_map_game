# editor/ui/widgets/preview_widget.py
from __future__ import annotations
import gc
import logging
import math
from typing import Optional, Tuple

import numpy as np
from PySide6 import QtWidgets, QtCore
from vispy import scene

from editor.core.render_settings import RenderSettings
from editor.logic.preview_logic import EPS
from editor.render_palettes import map_palette_cpu

logger = logging.getLogger(__name__)


def _normalize_01(z: np.ndarray) -> tuple[np.ndarray, float, float]:
    zmin = float(np.nanmin(z))
    zmax = float(np.nanmax(z))
    if zmax - zmin < 1e-12:
        return np.zeros_like(z, dtype=np.float32), zmin, zmax
    out = (z - zmin) / (zmax - zmin)
    return out.astype(np.float32, copy=False), zmin, zmax


def _dir_from_angles(az_deg: float, alt_deg: float) -> tuple[float, float, float]:
    az = math.radians(az_deg)
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
        # --- ИЗМЕНЕНИЕ: Устанавливаем камеру так, чтобы Z был вверх ---
        self.view.camera = scene.cameras.TurntableCamera(up='z', fov=self._settings.fov, azimuth=45.0, elevation=30.0)

        # --- КОМПАС: Настраиваем стрелку ---
        # Стрелка будет указывать вдоль оси +Y в своей локальной системе координат
        # Мы будем вращать ее вокруг оси Z
        self._compass = scene.visuals.Arrow(
            pos=np.array([[0, 0, 0], [0, 25, 0]]),  # Стрелка от (0,0,0) до (0,25,0)
            color='white',
            arrow_size=12.0,
            arrow_type='triangle_60',
            parent=self.canvas.scene  # Добавляем на всю сцену, а не в view
        )
        self._compass.transform = scene.transforms.STTransform()  # Создаем трансформ
        self._compass.visible = False  # Скрываем по умолчанию

        # --- КОНЕЦ ИЗМЕНЕНИЙ КОМПАСА ---

        scene.visuals.XYZAxis(parent=self.view.scene)  # Оси остаются для отладки
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
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

    def update_mesh(self, height_map: np.ndarray, cell_size: float, *,
                    north_vector_2d: Optional[Tuple[float, float]] = None) -> None:
        self._clear_scene()
        if not isinstance(height_map, np.ndarray) or height_map.shape[0] < 2 or height_map.shape[1] < 2:
            return
        if not np.all(np.isfinite(height_map)):
            logger.warning("Height map contains non-finite values, skipping mesh update.")
            return

        s = self._settings
        z = np.ascontiguousarray(height_map * float(s.height_exaggeration), dtype=np.float32)

        mesh_data = _create_solid_mesh_data(z, cell_size, s)
        if not mesh_data:
            logger.warning("Failed to create mesh data.")
            return

        try:
            self._mesh = scene.visuals.Mesh(
                vertices=mesh_data["vertices"],
                faces=mesh_data["faces"],
                vertex_colors=mesh_data["vertex_colors"],
                shading=None,  # Используем vertex_colors напрямую
                parent=self.view.scene
            )
        except Exception as e:
            logger.error(f"Error creating VisPy Mesh: {e}", exc_info=True)
            return  # Не можем продолжить без меша

        # --- ЛОГИКА ОТОБРАЖЕНИЯ КОМПАСА ---
        if north_vector_2d is not None and np.linalg.norm(north_vector_2d) > EPS:
            # north_vector_2d = (nx, nz) в локальной системе координат превью
            nx, nz = north_vector_2d
            # Угол от оси +Z (вверх на экране превью) к вектору севера
            # atan2(x, z) дает угол от оси +Z
            angle_rad = math.atan2(nx, nz)
            angle_deg = np.rad2deg(angle_rad)

            # Позиционируем компас в левом верхнем углу
            # Координаты canvas идут от левого нижнего угла
            canvas_w, canvas_h = self.canvas.size
            # Позиция в пикселях от левого нижнего угла
            pos = (40, canvas_h - 40, 0)  # X=40, Y=Высота-40, Z=0

            logger.debug(f"Compass: vector=({nx:.3f}, {nz:.3f}), angle={angle_deg:.1f} deg from +Z, canvas_pos={pos}")

            # Применяем трансформации
            # Сначала перемещаем стрелку в угол
            self._compass.transform.translate = pos
            # Затем вращаем ее ВОКРУГ ОСИ Z (0,0,1) на нужный угол
            # В VisPy вращение происходит в порядке Z, Y, X
            self._compass.transform.rotation = (0, 0, angle_deg)  # Поворот вокруг Z
            self._compass.visible = True
        else:
            self._compass.visible = False
            logger.debug("Compass: No north vector provided or zero length.")
        # --- КОНЕЦ ЛОГИКИ КОМПАСА ---

        # Логика auto_frame остается
        if s.auto_frame:
            h, w = height_map.shape
            # Используем z_min/z_max из _create_solid_mesh_data, если они там считаются,
            # или считаем здесь
            try:
                zmin_val = float(np.nanmin(z)) if np.any(np.isfinite(z)) else 0.0
                zmax_val = float(np.nanmax(z)) if np.any(np.isfinite(z)) else 1.0
                if zmax_val <= zmin_val: zmax_val = zmin_val + 1.0  # Защита от плоской карты
            except Exception:
                zmin_val, zmax_val = 0.0, 1.0

            self.view.camera.set_range(x=(0, w * cell_size), y=(0, h * cell_size), z=(zmin_val, zmax_val))
            # Дистанцию можно немного увеличить, чтобы компас не перекрывал меш
            self.view.camera.distance = 2.0 * max(w * cell_size, h * cell_size)

        self.canvas.update()

    def closeEvent(self, e):
        self._clear_scene()
        self.canvas.close()
        super().closeEvent(e)