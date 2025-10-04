# editor/logic/planet_view_logic.py
import logging
import math
import numpy as np
from PySide6 import QtGui

# Импорты, которые раньше были в main_window
from generator_logic.topology.icosa_grid import build_hexplanet

logger = logging.getLogger(__name__)


def _generate_faceted_geometry(planet_data: dict, sphere_params: dict, disp_scale: float, context: dict) -> tuple[
    np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Собирает 3D-модель и генерирует массивы высот и цветов для каждой вершины.
    Возвращает: (вершины, индексы заливки, индексы линий, высоты вершин, цвета вершин)
    """
    from generator_logic.terrain.global_sphere_noise import global_sphere_noise_wrapper

    centers_xyz = planet_data['centers_xyz']
    polys_lonlat = planet_data['cell_polys_lonlat_rad']
    pent_ids = set(planet_data.get('pent_ids', []))
    num_cells = len(centers_xyz)

    heights_per_cell = global_sphere_noise_wrapper(context, sphere_params, coords_xyz=centers_xyz)
    if heights_per_cell.ndim > 1:
        heights_per_cell = heights_per_cell.ravel()

    final_vertices = []
    final_heights = []
    final_colors = []
    fill_indices = []
    line_indices = []

    color_ocean = np.array([0.2, 0.3, 0.7], dtype=np.float32)
    color_land = np.array([0.4, 0.6, 0.3], dtype=np.float32)
    color_pentagon = np.array([0.8, 0.2, 0.2], dtype=np.float32)

    def lonlat_to_xyz(lon, lat):
        x = np.cos(lat) * np.cos(lon)
        y = np.cos(lat) * np.sin(lon)
        z = np.sin(lat)
        return np.array([x, y, z], dtype=np.float32)

    for i in range(num_cells):
        height_val = heights_per_cell[i]

        is_pentagon = i in pent_ids
        if is_pentagon:
            base_color = color_pentagon
        else:
            base_color = color_ocean if height_val < sphere_params.get('sea_level', 0.4) else color_land

        poly_verts_3d = np.array([lonlat_to_xyz(lon, lat) for lon, lat in polys_lonlat[i]])
        displaced_verts = poly_verts_3d * (1.0 + disp_scale * (height_val - 0.5))

        base_index = len(final_vertices)
        final_vertices.extend(displaced_verts)
        final_heights.extend([height_val] * len(displaced_verts))
        final_colors.extend([base_color] * len(displaced_verts))

        for j in range(1, len(displaced_verts) - 1):
            fill_indices.append([base_index, base_index + j, base_index + j + 1])

        num_poly_verts = len(displaced_verts)
        for j in range(num_poly_verts):
            line_indices.append([base_index + j, base_index + ((j + 1) % num_poly_verts)])

    return (np.array(final_vertices, dtype=np.float32),
            np.array(fill_indices, dtype=np.uint32),
            np.array(line_indices, dtype=np.uint32),
            np.array(final_heights, dtype=np.float32),
            np.array(final_colors, dtype=np.float32))

def update_planet_widget(planet_widget, world_settings: dict):
    """
    Главная функция-оркестратор. Собирает данные и обновляет 3D-виджет планеты.
    """
    if planet_widget is None:
        logger.warning("Виджет планеты недоступен.")
        return

    logger.info("Обновление 3D-вида планеты (from logic module)...")

    try:
        subdivision_level = world_settings.get('subdivision_level', 8)
        disp_scale = world_settings.get('disp_scale', 0.05)
        sphere_params = world_settings.get('sphere_params', {})
        # --- ИЗМЕНЕНИЕ: Добавляем 'sea_level' в sphere_params для передачи в _generate_faceted_geometry ---
        sphere_params['sea_level'] = world_settings.get('sea_level', 0.4)

        planet_data = build_hexplanet(f=subdivision_level)
        if not planet_data:
            raise RuntimeError("Failed to generate planet data.")

        # --- ИЗМЕНЕНИЕ: Теперь context создается здесь и передается дальше ---
        context = {'project': {'seed': sphere_params.get('seed', 0)}}
        V, F_fill, I_lines, V_heights, V_colors = _generate_faceted_geometry(planet_data, sphere_params, disp_scale,
                                                                             context)

        # Передаем данные в виджет
        planet_widget.set_geometry(V, F_fill, I_lines, V_heights, V_colors)

        logger.info("3D-вид планеты успешно обновлен (faceted).")

    except Exception as e:
        logger.exception(f"Ошибка при обновлении 3D-вида планеты: {e}")
        raise