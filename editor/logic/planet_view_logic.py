# editor/logic/planet_view_logic.py
import json
import logging
import math
import numpy as np
from PySide6 import QtWidgets
from pathlib import Path

from editor.render.planet_palettes import map_planet_height_palette, map_planet_bimodal_palette
from generator_logic.climate import biome_matcher, global_models
from generator_logic.topology.icosa_grid import build_hexplanet
from generator_logic.terrain.global_sphere_noise import get_noise_for_sphere_view
from editor.ui.layouts.world_settings_panel import PLANET_ROUGHNESS_PRESETS

logger = logging.getLogger(__name__)


def _normalize_vector(v):
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(norm, 1e-9)


def _slerp(u, v, t):
    u = u / max(np.linalg.norm(u), 1e-12)
    v = v / max(np.linalg.norm(v), 1e-12)
    dot = float(np.clip(np.dot(u, v), -1.0, 1.0))
    theta = math.acos(dot)
    if theta < 1e-6: return u.copy()
    sin_theta = math.sin(theta)
    a = math.sin((1.0 - t) * theta) / sin_theta
    b = math.sin(t * theta) / sin_theta
    w = a * u + b * v
    return w / max(np.linalg.norm(w), 1e-12)


def _subdivide_triangle(v1, v2, v3, level):
    if level <= 0: return [(v1, v2, v3)]
    m12, m23, m31 = _slerp(v1, v2, 0.5), _slerp(v2, v3, 0.5), _slerp(v3, v1, 0.5)
    tris = []
    tris.extend(_subdivide_triangle(v1, m12, m31, level - 1))
    tris.extend(_subdivide_triangle(m12, v2, m23, level - 1))
    tris.extend(_subdivide_triangle(m31, m23, v3, level - 1))
    tris.extend(_subdivide_triangle(m12, m23, m31, level - 1))
    return tris


def _generate_hex_sphere_geometry(planet_data, heights_01: np.ndarray, disp_scale, subdivision_level) -> tuple:
    """
    Возвращает 5 значений: displaced_vertices, F_fill, line_vertices_displaced, I_lines, V_sphere_base.
    """
    polys_lonlat = planet_data['cell_polys_lonlat_rad']
    centers_xyz = planet_data['centers_xyz']

    def lonlat_to_xyz(lon, lat, radius=1.0):
        lon, lat = float(lon), float(lat)
        x = math.cos(lat) * math.cos(lon)
        y = math.cos(lat) * math.sin(lon)
        z = math.sin(lat)
        v = np.array([x, y, z], dtype=np.float64)
        return (_normalize_vector(v) * radius).astype(np.float32)

    all_triangles = []
    for i, poly in enumerate(polys_lonlat):
        if len(poly) < 3: continue
        poly_verts_3d = _normalize_vector(np.array([lonlat_to_xyz(lon, lat) for lon, lat in poly], dtype=np.float32))
        center_3d = _normalize_vector(centers_xyz[i].astype(np.float32))
        for j in range(len(poly_verts_3d)):
            v1, v2 = poly_verts_3d[j], poly_verts_3d[(j + 1) % len(poly_verts_3d)]
            all_triangles.extend(_subdivide_triangle(center_3d, v1, v2, subdivision_level))

    vertex_map, unique_vertices, final_triangles_indices = {}, [], []
    for tri in all_triangles:
        tri_idx = []
        for v in tri:
            key = tuple(np.round(v, 6))
            if key not in vertex_map:
                vertex_map[key] = len(unique_vertices)
                unique_vertices.append(np.asarray(v, dtype=np.float32))
            tri_idx.append(vertex_map[key])
        final_triangles_indices.append(tri_idx)

    V_sphere_base = _normalize_vector(np.array(unique_vertices, dtype=np.float32))
    F_fill = np.array(final_triangles_indices, dtype=np.uint32)

    # Убедимся, что heights_01 имеет правильную форму для смещения
    flat_heights = heights_01.flatten()
    if len(flat_heights) != len(V_sphere_base):
        # Если размеры не совпадают (например, при первом вызове с np.zeros(1)), создаем массив нужного размера
        flat_heights = np.zeros(len(V_sphere_base), dtype=np.float32)

    displaced_vertices = V_sphere_base * (1.0 + disp_scale * (flat_heights - 0.5))[:, np.newaxis]

    I_lines, line_vertex_map, line_unique_vertices = [], {}, []
    for poly in polys_lonlat:
        poly_indices = []
        for lon, lat in poly:
            key = (round(lon, 6), round(lat, 6))
            if key not in line_vertex_map:
                line_vertex_map[key] = len(line_unique_vertices)
                line_unique_vertices.append(lonlat_to_xyz(lon, lat))
            poly_indices.append(line_vertex_map[key])
        for k in range(len(poly_indices)): I_lines.append([poly_indices[k], poly_indices[(k + 1) % len(poly_indices)]])

    r_fill_max = float(np.linalg.norm(displaced_vertices, axis=1).max())
    line_vertices_displaced = _normalize_vector(np.array(line_unique_vertices, dtype=np.float32)) * (
            r_fill_max + max(0.002, 0.01 * r_fill_max))

    return displaced_vertices, F_fill, line_vertices_displaced, I_lines, V_sphere_base


def orchestrate_planet_update(main_window) -> dict:
    """
    Главная функция обновления 3D-вида планеты.
    """
    logger.info("Обновление вида планеты...")

    try:
        radius_text = main_window.planet_radius_label.text().replace(" км", "").replace(",", "").replace(" ", "")
        radius_km = float(radius_text)
    except (ValueError, TypeError):
        logger.error("Не удалось прочитать радиус планеты из UI, используется значение по умолчанию 6371 км.")
        radius_km = 6371.0

    radius_m = radius_km * 1000.0
    if radius_m < 1.0: raise ValueError("Радиус планеты слишком мал")

    preset_name = main_window.planet_type_preset_input.currentText()
    roughness_pct, _ = PLANET_ROUGHNESS_PRESETS.get(preset_name, (0.003, 2.5))
    disp_scale = roughness_pct * 1.5
    max_displacement_m = radius_m * disp_scale * 0.5

    continent_size_km = main_window.ws_continent_scale_km.value()
    frequency = 20000.0 / max(continent_size_km, 1.0)
    logger.info(
        f"Рассчитана частота шума для вида планеты: {frequency:.2f} (на основе размера континента: {continent_size_km:,.0f} км)")

    sphere_params = {
        'octaves': int(main_window.ws_octaves.value()),
        'gain': main_window.ws_gain.value(),
        'seed': main_window.ws_seed.value(),
        'frequency': frequency,
        'power': main_window.ws_power.value(),
    }

    detail_text = main_window.planet_preview_detail_input.currentText()
    subdivision_level_geom = int(detail_text.split("(")[1].replace(")", ""))
    subdivision_level_grid = int(main_window.subdivision_level_input.currentText().split(" ")[0])

    planet_data = build_hexplanet(f=subdivision_level_grid)
    if not planet_data: raise RuntimeError("Failed to generate planet data.")

    # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
    # 1. Сначала делаем один вызов, чтобы получить базовую геометрию (V_fill_base)
    #    Правильно распаковываем 5 значений, но используем только последнее.
    _, _, _, _, V_fill_base = _generate_hex_sphere_geometry(
        planet_data, np.zeros(1), 0.0, subdivision_level_geom
    )

    # 2. Генерируем шум ОДИН РАЗ на основе этой геометрии
    heights_01 = get_noise_for_sphere_view(sphere_params, V_fill_base)

    # 3. Теперь генерируем финальную геометрию, ПЕРЕДАВАЯ в нее готовый шум
    #    И снова правильно распаковываем 5 значений.
    V_fill, F_fill, V_lines, I_lines, _ = _generate_hex_sphere_geometry(
        planet_data, heights_01, disp_scale, subdivision_level_geom
    )
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    flat_heights_01 = heights_01.flatten()

    if main_window.climate_enabled.isChecked():
        logger.info("  -> Режим климата включен. Расчет биомов...")
        try:
            biomes_path = Path("game_engine_restructured/data/biomes.json")
            with open(biomes_path, "r", encoding="utf-8") as f:
                biomes_definition = json.load(f)

            sea_level_01 = main_window.climate_sea_level.value() / 100.0
            is_land_mask = flat_heights_01 >= sea_level_01

            dominant_biomes_on_land = []
            if np.any(is_land_mask):
                V_norm_land = (V_fill_base / np.linalg.norm(V_fill_base, axis=1, keepdims=True))[is_land_mask]

                avg_temp_c = main_window.climate_avg_temp.value()
                axis_tilt = main_window.climate_axis_tilt.value()
                equator_pole_diff = axis_tilt * 1.5
                equator_temp_c = avg_temp_c + equator_pole_diff / 3.0

                base_temp_land = global_models.calculate_base_temperature(V_norm_land, equator_temp_c,
                                                                          equator_pole_diff)

                # Используем V_fill со смещением для более точной высоты
                heights_m_land = np.linalg.norm(V_fill[is_land_mask], axis=1) - radius_m + max_displacement_m
                final_temp_land = base_temp_land + heights_m_land * -0.0065

                sea_level_m = radius_m - max_displacement_m + sea_level_01 * (2 * max_displacement_m)
                humidity_land = np.clip(1.0 - (heights_m_land - sea_level_m) / (max_displacement_m * 2), 0.1, 0.9)

                for i in range(len(final_temp_land)):
                    probs = biome_matcher.calculate_biome_probabilities(final_temp_land[i], humidity_land[i],
                                                                        biomes_definition)
                    dominant_biome = max(probs, key=probs.get) if probs else "default"
                    dominant_biomes_on_land.append(dominant_biome)

            fill_colors = map_planet_bimodal_palette(flat_heights_01, sea_level_01, dominant_biomes_on_land)

        except Exception as e:
            logger.error(f"Ошибка при расчете климата для планеты: {e}", exc_info=True)
            fill_colors = map_planet_height_palette(heights_01)
    else:
        logger.info("  -> Режим климата выключен. Раскраска по высоте.")
        fill_colors = map_planet_height_palette(heights_01)

    offset = len(V_fill)
    all_vertices = np.vstack([V_fill, V_lines]).astype(np.float32)
    line_colors = np.zeros((len(V_lines), 3), dtype=np.float32)
    all_colors = np.vstack([fill_colors.reshape(-1, 3), line_colors])
    all_line_indices = (np.array(I_lines, dtype=np.uint32) + offset)

    if main_window.project_manager.current_project_path:
        cache_dir = Path(main_window.project_manager.current_project_path) / "cache"
        cache_dir.mkdir(exist_ok=True)
        cache_file = cache_dir / "planet_geometry.npz"
        np.savez_compressed(cache_file, vertices=all_vertices, fill_indices=F_fill,
                            line_indices=all_line_indices.flatten(), colors=all_colors, planet_data=planet_data)
        logger.info(f"Геометрия планеты сохранена в кэш: {cache_file}")

    return {
        "vertices": all_vertices, "fill_indices": F_fill, "line_indices": all_line_indices.flatten(),
        "colors": all_colors, "planet_data": planet_data
    }