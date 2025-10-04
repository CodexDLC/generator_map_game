# editor/logic/planet_view_logic.py
import logging
import math
import numpy as np
from PySide6 import QtGui

from generator_logic.topology.icosa_grid import build_hexplanet

logger = logging.getLogger(__name__)

HEIGHT_STOPS = np.array([0.0, 0.39, 0.4, 0.5, 0.75, 1.0], dtype=np.float32)
COLOR_MAP = np.array([
    [0.1, 0.2, 0.6],
    [0.2, 0.4, 0.8],
    [0.85, 0.75, 0.5],
    [0.4, 0.6, 0.3],
    [0.3, 0.4, 0.2],
    [1.0, 1.0, 1.0],
], dtype=np.float32)


def get_colors_from_heights(heights: np.ndarray, stops: np.ndarray) -> np.ndarray:
    red = np.interp(heights, stops, COLOR_MAP[:, 0])
    green = np.interp(heights, stops, COLOR_MAP[:, 1])
    blue = np.interp(heights, stops, COLOR_MAP[:, 2])
    return np.stack([red, green, blue], axis=-1).astype(np.float32)


def _generate_faceted_geometry(planet_data: dict, sphere_params: dict, disp_scale: float, context: dict) -> tuple[
    np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    from generator_logic.terrain.global_sphere_noise import global_sphere_noise_wrapper

    polys_lonlat = planet_data['cell_polys_lonlat_rad']

    def lonlat_to_xyz(lon, lat):
        x = np.cos(lat) * np.cos(lon)
        y = np.cos(lat) * np.sin(lon)
        z = np.sin(lat)
        return np.array([x, y, z], dtype=np.float32)

    fill_indices, line_indices, vertex_counter = [], [], 0
    all_poly_verts_3d = []
    for i, poly_lonlat in enumerate(polys_lonlat):
        num_poly_verts = len(poly_lonlat)
        if num_poly_verts < 3: continue
        poly_verts_3d = np.array([lonlat_to_xyz(lon, lat) for lon, lat in poly_lonlat])
        all_poly_verts_3d.extend(poly_verts_3d)
        base_index = vertex_counter
        for j in range(1, num_poly_verts - 1):
            fill_indices.append([base_index, base_index + j, base_index + j + 1])
        for j in range(num_poly_verts):
            line_indices.append([base_index + j, base_index + ((j + 1) % num_poly_verts)])
        vertex_counter += num_poly_verts
    all_poly_verts_3d = np.array(all_poly_verts_3d, dtype=np.float32)

    # --- НАЧАЛО ИСПРАВЛЕНИЯ: исправлена ошибка с неопределенной переменной _seed ---
    warp_strength = sphere_params.get('warp_strength', 0.0)
    if warp_strength > 0.0:
        base_seed = sphere_params.get('seed', 0)
        warp_context = {'project': {'seed': base_seed ^ 12345}}
        warp_params = {'frequency': 0.5, 'octaves': 2, 'gain': 0.5}

        offset_x = global_sphere_noise_wrapper(warp_context, warp_params, coords_xyz=all_poly_verts_3d)
        # Для каждого канала смещения используем свой уникальный сид
        warp_params['seed'] = base_seed + 1
        offset_y = global_sphere_noise_wrapper(warp_context, warp_params, coords_xyz=all_poly_verts_3d)
        warp_params['seed'] = base_seed + 2
        offset_z = global_sphere_noise_wrapper(warp_context, warp_params, coords_xyz=all_poly_verts_3d)

        offsets = np.stack([offset_x, offset_y, offset_z], axis=-1) * warp_strength
        warped_coords = all_poly_verts_3d + offsets
        warped_coords /= np.linalg.norm(warped_coords, axis=1, keepdims=True)
    else:
        warped_coords = all_poly_verts_3d
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    heights_per_vertex = global_sphere_noise_wrapper(context, sphere_params, coords_xyz=warped_coords)
    if heights_per_vertex.ndim > 1:
        heights_per_vertex = heights_per_vertex.ravel()

    power = sphere_params.get('power', 1.0)
    if power != 1.0:
        heights_per_vertex = np.power(heights_per_vertex, power)

    sea_level_pct = sphere_params.get('sea_level_pct', 0.4)
    current_stops = HEIGHT_STOPS.copy()
    current_stops[1] = max(0.0, sea_level_pct - 0.01)
    current_stops[2] = sea_level_pct

    colors_per_vertex = get_colors_from_heights(heights_per_vertex, current_stops)

    displaced_vertices = all_poly_verts_3d * (1.0 + disp_scale * (heights_per_vertex - 0.5))[:, np.newaxis]

    return (displaced_vertices.astype(np.float32),
            np.array(fill_indices, dtype=np.uint32),
            np.array(line_indices, dtype=np.uint32),
            heights_per_vertex.astype(np.float32),
            colors_per_vertex.astype(np.float32))


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

        planet_data = build_hexplanet(f=subdivision_level)
        if not planet_data:
            raise RuntimeError("Failed to generate planet data.")

        # --- НАЧАЛО ИЗМЕНЕНИЙ: Сохраняем данные о планете в виджет ---
        if hasattr(planet_widget, 'set_planet_data'):
            planet_widget.set_planet_data(planet_data)
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---

        context = {'project': {'seed': sphere_params.get('seed', 0)}}
        V, F_fill, I_lines, V_heights, V_colors = _generate_faceted_geometry(planet_data, sphere_params, disp_scale,
                                                                             context)
        planet_widget.set_geometry(V, F_fill, I_lines, V_heights, V_colors)

        logger.info("3D-вид планеты успешно обновлен (faceted).")

    except Exception as e:
        logger.exception(f"Ошибка при обновлении 3D-вида планеты: {e}")
        raise