# editor/ui/widgets/preview_widget.py
from __future__ import annotations
import gc
import logging
import math
from typing import Optional, Tuple, List # Убедись, что List импортирован

import numpy as np
from PySide6 import QtWidgets, QtCore, QtGui
# <<< ИСПРАВЛЕННЫЙ ИМПОРТ >>>
from vispy import scene
from vispy.scene import transforms # Импортируем модуль transforms из vispy.scene
# <<< КОНЕЦ ИСПРАВЛЕНИЯ >>>

from editor.core.render_settings import RenderSettings
# Убедись, что EPS импортирован или определен
try:
    from editor.logic.preview_logic import EPS
except ImportError:
    EPS = 1e-9 # Запасной вариант
from editor.render_palettes import map_palette_cpu

logger = logging.getLogger(__name__)


# --- Функции _normalize_01, _dir_from_angles, _create_solid_mesh_data (без изменений) ---
def _normalize_01(z: np.ndarray) -> tuple[np.ndarray, float, float]:
    zmin = float(np.nanmin(z)) if np.any(np.isfinite(z)) else 0.0
    zmax = float(np.nanmax(z)) if np.any(np.isfinite(z)) else 1.0
    if zmax - zmin < 1e-12:
        return np.zeros_like(z, dtype=np.float32), zmin, zmax
    # Добавим np.nan_to_num для безопасности перед вычитанием
    safe_z = np.nan_to_num(z, nan=zmin)
    out = (safe_z - zmin) / (zmax - zmin)
    return out.astype(np.float32, copy=False), zmin, zmax

def _dir_from_angles(az_deg: float, alt_deg: float) -> tuple[float, float, float]:
    az = math.radians(az_deg)
    alt = math.radians(alt_deg)
    x = math.cos(alt) * math.cos(az)
    y = math.cos(alt) * math.sin(az)
    z = math.sin(alt)
    return (-x, -y, -z)

def _create_solid_mesh_data(z_data: np.ndarray, cell_size: float, s: RenderSettings) -> dict:
    h, w = z_data.shape
    if h < 2 or w < 2: return {}
    z_min = 0.0 # Базовая плоскость на Z=0
    x = np.linspace(0, (w - 1) * cell_size, w, dtype=np.float32)
    y = np.linspace(0, (h - 1) * cell_size, h, dtype=np.float32) # Используем Y для второй горизонтальной оси VisPy
    xx, yy = np.meshgrid(x, y)
    top_verts = np.stack([xx, yy, z_data], axis=-1)
    bottom_verts = np.stack([xx, yy, np.full_like(z_data, z_min)], axis=-1)
    all_verts = np.vstack([top_verts.reshape(-1, 3), bottom_verts.reshape(-1, 3)])
    bottom_offset = h * w
    faces = []
    # Верхняя поверхность
    for r in range(h - 1):
        for c in range(w - 1):
            i00, i10, i01, i11 = r * w + c, (r + 1) * w + c, r * w + (c + 1), (r + 1) * w + (c + 1)
            faces.extend([[i00, i10, i11], [i00, i11, i01]])
    # Нижняя поверхность (обратный порядок вершин)
    for r in range(h - 1):
        for c in range(w - 1):
            i00, i10, i01, i11 = bottom_offset + r * w + c, bottom_offset + (r + 1) * w + c, bottom_offset + r * w + (c + 1), bottom_offset + (r + 1) * w + (c + 1)
            faces.extend([[i00, i11, i10], [i00, i01, i11]])
    # Стенки
    for c in range(w - 1): # Передняя и задняя (вдоль оси Y VisPy)
        faces.extend([[c, c + 1, bottom_offset + c + 1], [c, bottom_offset + c + 1, bottom_offset + c]]) # Нижний край y=0
        i0, i1 = (h - 1) * w + c, (h - 1) * w + c + 1
        faces.extend([[i0, bottom_offset + i0, bottom_offset + i1], [i0, bottom_offset + i1, i1]]) # Верхний край y=max
    for r in range(h - 1): # Левая и правая (вдоль оси X VisPy)
        i0, i1 = r * w, (r + 1) * w
        faces.extend([[i0, bottom_offset + i0, bottom_offset + i1], [i0, bottom_offset + i1, i1]]) # Левый край x=0
        i0, i1 = r * w + w - 1, (r + 1) * w + w - 1
        faces.extend([[i0, i1, bottom_offset + i1], [i0, bottom_offset + i1, bottom_offset + i0]]) # Правый край x=max
    all_faces = np.array(faces, dtype=np.uint32)

    # Генерация цветов вершин
    z01, _, _ = _normalize_01(z_data)
    # Важно: np.gradient возвращает (d/dy, d/dx) для осей VisPy (y - вторая ось)
    dy, dx = np.gradient(z_data, cell_size) # dy соответствует градиенту по нашей Z, dx по нашей X
    # Нормаль (nx, ny, nz) = (-dx, -dy, 1) - Z=Up
    normals = np.stack([-dx, -dy, np.ones_like(z_data)], axis=-1)
    norm = np.linalg.norm(normals, axis=2, keepdims=True)
    norm[norm < EPS] = 1.0 # Защита от деления на ноль
    normals /= norm
    light_dir = np.array(_dir_from_angles(s.light_azimuth_deg, s.light_altitude_deg), dtype=np.float32)
    diffuse = np.maximum(0, np.dot(normals, -light_dir))
    light = s.ambient + s.diffuse * diffuse
    rgb_height = map_palette_cpu(z01, s.palette_name)
    slope_mult = np.ones_like(z_data, dtype=np.float32)
    if s.use_slope_darkening:
        slope_magnitude = np.sqrt(dx * dx + dy * dy) # Тангенс угла наклона
        slope_mult = 1.0 - s.slope_strength * np.clip(slope_magnitude * 0.5, 0.0, 1.0) # Уменьшаем яркость на склонах
    final_rgb = np.clip(rgb_height * light[..., None] * slope_mult[..., None], 0.0, 1.0)
    top_colors = np.concatenate([final_rgb, np.ones_like(final_rgb[..., :1])], axis=-1).reshape(-1, 4)
    side_color = np.array([0.15, 0.15, 0.18, 1.0], dtype=np.float32)
    bottom_colors = np.tile(side_color, (h * w, 1))
    all_colors = np.vstack([top_colors, bottom_colors])
    return {"vertices": all_verts, "faces": all_faces, "vertex_colors": all_colors}
# --- Конец хелперов ---


class Preview3DWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._mesh = None
        self._settings = RenderSettings()

        self.canvas = scene.SceneCanvas(keys="interactive", show=False, config={"samples": 4})
        self.view = self.canvas.central_widget.add_view()
        self.view.bgcolor = 'black'
        # Камера с Z-up остается правильной
        self.view.camera = scene.cameras.TurntableCamera(up='z', fov=self._settings.fov, azimuth=45.0, elevation=30.0)

        # --- КОМПАС: Настраиваем стрелку ---
        self._compass_arrow = scene.visuals.Arrow(
            pos=np.array([[0, -15, 0], [0, 15, 0]]), # Длина 30 вдоль оси Y VisPy
            color='red', # Яркий цвет
            arrow_size=10.0,
            arrow_type='triangle_60',
            parent=self.view # Привязан к View
        )
        # --- ИСПОЛЬЗУЕМ ПРАВИЛЬНЫЙ ИМПОРТ transforms ---
        self._compass_transform_chain = transforms.ChainTransform([
            transforms.MatrixTransform(),       # Для поворота
            transforms.PixelTransform()         # Для позиционирования
        ])
        self._compass_arrow.transform = self._compass_transform_chain
        # --- КОНЕЦ ИСПРАВЛЕНИЯ КОМПАСА ---
        self._compass_arrow.visible = False # Скрываем по умолчанию

        # scene.visuals.XYZAxis(parent=self.view.scene) # Оси для отладки

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.canvas.native)

    # --- Остальные методы ---

    def _clear_scene(self) -> None:
        if self._mesh is not None:
            # Добавим проверку существования родителя перед удалением
            if self._mesh.parent is not None:
                self._mesh.parent = None
            self._mesh = None
        gc.collect()

    def apply_render_settings(self, s: RenderSettings) -> None:
        self._settings = s
        cam = self.view.camera
        if hasattr(cam, "fov"): cam.fov = float(s.fov)
        # Запускаем полное обновление меша, т.к. цвет и свет изменились
        if self.parent() and hasattr(self.parent(), '_on_apply_clicked'):
             # Используем QTimer.singleShot для вызова Apply после возврата в цикл событий
             QtCore.QTimer.singleShot(0, self.parent()._on_apply_clicked)
        else:
             # Если нет родителя с Apply, просто обновляем отрисовку
             self.canvas.update()

    def update_mesh(self, height_map: np.ndarray, cell_size: float, *,
                    north_vector_2d: Optional[List[float]] = None) -> None:
        self._clear_scene() # Очищаем старый меш
        # Проверки входных данных
        if not isinstance(height_map, np.ndarray) or height_map.ndim != 2 or height_map.shape[0] < 2 or height_map.shape[1] < 2:
            logger.warning("Invalid height_map received in update_mesh. Skipping.")
            self._compass_arrow.visible = False
            self.canvas.update()
            return
        if not np.all(np.isfinite(height_map)):
            logger.warning("Height map contains non-finite values, replacing with 0.")
            height_map = np.nan_to_num(height_map, nan=0.0, posinf=0.0, neginf=0.0) # Заменяем NaN/Inf на 0

        s = self._settings
        # Убедимся, что преувеличение высоты > 0
        height_exaggeration = max(float(s.height_exaggeration), EPS)
        z_meters_exaggerated = np.ascontiguousarray(height_map * height_exaggeration, dtype=np.float32)

        # Создаем данные меша
        mesh_data = _create_solid_mesh_data(z_meters_exaggerated, cell_size, s)
        if not mesh_data or 'vertices' not in mesh_data or mesh_data['vertices'].size == 0:
            logger.warning("Failed to create mesh data.")
            self._compass_arrow.visible = False
            self.canvas.update()
            return

        # Создаем сам меш
        try:
            self._mesh = scene.visuals.Mesh(
                vertices=mesh_data["vertices"],
                faces=mesh_data["faces"],
                vertex_colors=mesh_data["vertex_colors"],
                shading=None, # Используем цвета вершин
                parent=self.view.scene
            )
        except Exception as e:
            logger.error(f"Error creating VisPy Mesh: {e}", exc_info=True)
            self._compass_arrow.visible = False
            self.canvas.update()
            return

        # --- ЛОГИКА ОБНОВЛЕНИЯ КОМПАСА (без изменений) ---
        if north_vector_2d is not None and len(north_vector_2d) == 2 and np.linalg.norm(north_vector_2d) > EPS:
            nx, nz = north_vector_2d # Оси U(X) и V(Z_up) вида
            angle_rad = math.atan2(nx, nz) # Угол от оси +Z (Up)
            angle_deg = np.rad2deg(angle_rad)
            canvas_w, canvas_h = self.canvas.size
            pixel_pos = (40, canvas_h - 40) # Левый верхний угол

            # Обновляем трансформации компаса
            self._compass_transform_chain.transforms[0].matrix = \
                transforms.rotate(angle_deg, (0, 0, 1)) # Поворот вокруг Z
            self._compass_transform_chain.transforms[1].offset = pixel_pos # Пиксельное смещение

            logger.debug(f"Compass: vector=({nx:.3f}, {nz:.3f}), angle={angle_deg:.1f} deg from +Z, pixel_pos={pixel_pos}")
            self._compass_arrow.visible = True
        else:
            self._compass_arrow.visible = False
            logger.debug("Compass: No north vector provided or zero length.")
        # --- КОНЕЦ ЛОГИКИ КОМПАСА ---

        # Автоматическое кадрирование
        if s.auto_frame:
            h, w = height_map.shape
            # Используем z_meters_exaggerated для расчета zmin/zmax
            z_mesh = mesh_data["vertices"][:, 2] # Берем Z из вершин *уже созданного* меша
            try:
                # Добавим проверку на пустой массив
                if z_mesh.size == 0: raise ValueError("Mesh vertices Z are empty")
                zmin_val = float(np.min(z_mesh))
                zmax_val = float(np.max(z_mesh))
                # Добавим проверку на NaN/Inf на всякий случай
                if not np.isfinite(zmin_val) or not np.isfinite(zmax_val):
                     raise ValueError("Non-finite Z values in mesh")
                if zmax_val <= zmin_val: zmax_val = zmin_val + 1.0 # Если плоско
            except Exception as e:
                logger.warning(f"Could not determine Z range for auto-frame: {e}. Using defaults.")
                zmin_val, zmax_val = 0.0, 50.0 # Запасные значения

            center_x = (w - 1) * cell_size / 2.0
            center_y = (h - 1) * cell_size / 2.0 # Y в Vispy
            center_z = (zmax_val + zmin_val) / 2.0 # Z в Vispy
            self.view.camera.center = (center_x, center_y, center_z)

            max_dim_xy = max(w * cell_size, h * cell_size, 1.0) # Защита от нулевого размера
            max_dim_z = max(zmax_val - zmin_val, 1.0)
            effective_size = max(max_dim_xy, max_dim_z * 0.5)
            fov_rad = np.radians(self.view.camera.fov / 2.0)
            distance = effective_size / max(np.tan(fov_rad), EPS) if fov_rad > EPS else effective_size * 2
            # Увеличим максимальную дистанцию и добавим небольшой запас
            self.view.camera.distance = np.clip(distance * 1.2, 1.1, 1000.0) # Запас 20% и макс. 1000

        self.canvas.update() # Запрашиваем перерисовку

    def closeEvent(self, e):
        self._clear_scene()
        self.canvas.close()
        super().closeEvent(e)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        self._last_mouse_pos = event.position().toPoint()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        # Стандартное вращение VisPy TurntableCamera
        pass

    def wheelEvent(self, event: QtGui.QWheelEvent):
        # Стандартный зум VisPy TurntableCamera
        pass