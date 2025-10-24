# editor/render/region/region_mesh_builder.py
"""
(Код перенесен из editor/ui/widgets/preview_widget.py)
Отвечает за создание 3D-меша для превью региона (vispy).
"""
from __future__ import annotations
import logging
import math
import numpy as np

# ИСПОЛЬЗУЕМ НОВЫЕ ПАЛИТРЫ ИЗ ШАГА 1
# --- ИЗМЕНЕНИЕ: Импортируем обе функции ---
from editor.render.palettes import map_height_to_grayscale, map_palette_cpu
# -----------------------------------------------
from editor.core.render_settings import RenderSettings

logger = logging.getLogger(__name__)


def _normalize_01(z: np.ndarray) -> tuple[np.ndarray, float, float]:
    """ (Перенесено из preview_widget.py) """
    zmin = float(np.nanmin(z));
    zmax = float(np.nanmax(z))
    if zmax - zmin < 1e-12:
        return np.zeros_like(z, dtype=np.float32), zmin, zmax
    out = (z - zmin) / (zmax - zmin)
    return out.astype(np.float32, copy=False), zmin, zmax


def _dir_from_angles(az_deg: float, alt_deg: float) -> tuple[float, float, float]:
    """ (Перенесено из preview_widget.py) """
    az = math.radians(az_deg);
    alt = math.radians(alt_deg)
    x = math.cos(alt) * math.cos(az)
    y = math.cos(alt) * math.sin(az)
    z = math.sin(alt)
    return (-x, -y, -z)


def _create_solid_mesh_data(z_data: np.ndarray, cell_size: float, s: RenderSettings) -> dict:
    """
    (Перенесено из preview_widget.py)
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
    # (Код создания полигонов не изменился)
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

    # --- ИЗМЕНЕНИЕ ЗДЕСЬ: Уважаем настройку use_palette ---
    if s.use_palette:
        # (sea_level_pct=None означает, что красим только сушу)
        rgb_height = map_palette_cpu(z01, s.palette_name, sea_level_pct=None)
    else:
        rgb_height = map_height_to_grayscale(z01)
    # -------------------------------------------------------------

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