# editor/render/region/region_mesh_builder.py
"""
Отвечает за создание 3D-меша для превью региона.
(Модифицирован для Фазы 3.1: теперь строит ТОЛЬКО верхнюю поверхность)
"""
from __future__ import annotations
import logging
import numpy as np

from editor.render.palettes import map_height_to_grayscale, map_palette_cpu
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


def _create_solid_mesh_data(z_data: np.ndarray, cell_size: float, s: RenderSettings) -> dict:
    """
    (Модифицировано для Фазы 3.1)
    Создает сырые данные (вершины, полигоны, цвета, нормали)
    ТОЛЬКО ДЛЯ ВЕРХНЕЙ ПОВЕРХНОСТИ ландшафта.
    """
    h, w = z_data.shape
    if h < 2 or w < 2:
        return {}

    # --- УДАЛЕНО: z_min = 0.0 ---

    # 1. Создаем сетку координат
    x = np.linspace(0, (w - 1) * cell_size, w, dtype=np.float32)
    y = np.linspace(0, (h - 1) * cell_size, h, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)

    # 2. Создаем вершины (ТОЛЬКО ВЕРХ)
    all_verts = np.stack([xx, yy, z_data], axis=-1).reshape(-1, 3)

    # --- УДАЛЕНО: bottom_verts, all_verts = vstack, bottom_offset ---

    # 3. Создаем полигоны (ТОЛЬКО ВЕРХ)
    faces = []
    for r in range(h - 1):
        for c in range(w - 1):
            i00, i10, i01, i11 = r * w + c, (r + 1) * w + c, r * w + (c + 1), (r + 1) * w + (c + 1)
            faces.extend([[i00, i10, i11], [i00, i11, i01]])

    all_faces = np.array(faces, dtype=np.uint32)

    # --- УДАЛЕНО: Код для полигонов дна и стенок ---

    # 4. Генерируем НОРМАЛИ для вершин (ТОЛЬКО ВЕРХ)
    gy, gx = np.gradient(z_data, cell_size)
    all_normals_flat = np.stack([-gx, -gy, np.ones_like(z_data)], axis=-1)
    all_normals_flat /= np.linalg.norm(all_normals_flat, axis=2, keepdims=True)
    all_normals = all_normals_flat.reshape(-1, 3)

    # --- УДАЛЕНО: bottom_normals, side_normals, vstack ---

    # 5. Генерируем БАЗОВЫЕ ЦВЕТА для вершин (ТОЛЬКО ВЕРХ)
    z01, _, _ = _normalize_01(z_data)
    if s.use_palette:
        rgb_height = map_palette_cpu(z01, s.palette_name, sea_level_pct=None)
    else:
        rgb_height = map_height_to_grayscale(z01)

    all_colors = rgb_height.reshape(-1, 3)

    # --- УДАЛЕНО: side_color, bottom_colors, vstack ---

    return {
        "vertices": all_verts.astype(np.float32),
        "faces": all_faces.astype(np.uint32),
        "base_colors": all_colors.astype(np.float32),
        "normals": all_normals.astype(np.float32)
    }