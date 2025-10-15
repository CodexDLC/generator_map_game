# editor/logic/planet_view_logic.py
import json
import logging
import math
import numpy as np
from PySide6 import QtWidgets
from pathlib import Path

from editor.render.planet_palettes import map_planet_height_palette, map_planet_climate_palette
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


def _generate_hex_sphere_geometry(planet_data, sphere_params, disp_scale, subdivision_level) -> tuple:
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
    heights_01 = get_noise_for_sphere_view(sphere_params, V_sphere_base).flatten()
    displaced_vertices = V_sphere_base * (1.0 + disp_scale * (heights_01 - 0.5))[:, np.newaxis]

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

    return displaced_vertices, F_fill, line_vertices_displaced, I_lines


def orchestrate_planet_update(main_window) -> dict:
    """
    Главная функция обновления 3D-вида планеты.
    ВЕРСИЯ 2.1: Исправлена ошибка несоответствия размеров массивов вершин и цветов.
    """
    logger.info("Обновление вида планеты...")

    # --- ШАГ 1: Сбор параметров из UI ---
    radius_text = main_window.planet_radius_label.text().replace(" км", "").replace(",", "").replace(" ", "")
    radius_m = float(radius_text) * 1000.0 if radius_text and radius_text != 'Ошибка' else 1.0
    if radius_m < 1.0: raise ValueError("Радиус планеты слишком мал")

    preset_name = main_window.planet_type_preset_input.currentText()
    roughness_pct, _ = PLANET_ROUGHNESS_PRESETS.get(preset_name, (0.003, 2.5))
    disp_scale = roughness_pct * 1.5
    max_displacement_m = radius_m * disp_scale * 0.5

    scale_value = main_window.ws_relative_scale.value()
    min_freq, max_freq = 0.5, 10.0
    normalized_scale = (scale_value - 0.01) / 0.99
    frequency = max_freq - normalized_scale * (max_freq - min_freq)

    sphere_params = {
        'octaves': int(main_window.ws_octaves.value()), 'gain': main_window.ws_gain.value(),
        'seed': main_window.ws_seed.value(), 'frequency': frequency, 'power': main_window.ws_power.value(),
    }

    # --- ШАГ 2: Генерация геометрии ---
    detail_text = main_window.planet_preview_detail_input.currentText()
    subdivision_level_geom = int(detail_text.split("(")[1].replace(")", ""))
    subdivision_level_grid = int(main_window.subdivision_level_input.currentText().split(" ")[0])

    planet_data = build_hexplanet(f=subdivision_level_grid)
    if not planet_data: raise RuntimeError("Failed to generate planet data.")

    # Теперь _generate_hex_sphere_geometry возвращает и вершины линий
    V_fill, F_fill, V_lines, I_lines = _generate_hex_sphere_geometry(
        planet_data, sphere_params, disp_scale, subdivision_level_geom
    )

    # --- ШАГ 3: Расчет климата и выбор цвета ---
    if main_window.climate_enabled.isChecked():
        logger.info("  -> Режим климата включен. Расчет биомов...")
        try:
            biomes_path = Path("game_engine_restructured/data/biomes.json")
            with open(biomes_path, "r", encoding="utf-8") as f:
                biomes_definition = json.load(f)

            V_norm = V_fill / np.linalg.norm(V_fill, axis=1, keepdims=True)
            avg_temp_c = main_window.climate_avg_temp.value()
            axis_tilt = main_window.climate_axis_tilt.value()
            equator_pole_diff = axis_tilt * 1.5
            base_temp = global_models.calculate_base_temperature(V_norm, avg_temp_c, equator_pole_diff)

            heights_m = np.linalg.norm(V_fill, axis=1) - radius_m + max_displacement_m
            final_temp = base_temp + heights_m * -0.0065

            sea_level_m = radius_m - max_displacement_m + (main_window.climate_sea_level.value() / 100.0) * (
                        2 * max_displacement_m)
            humidity = np.clip(1.0 - (heights_m - sea_level_m) / (max_displacement_m * 2), 0.1, 0.9)

            dominant_biomes = [max(probs, key=probs.get) if (
                probs := biome_matcher.calculate_biome_probabilities(final_temp[i], humidity[i],
                                                                     biomes_definition)) else "default" for i in
                               range(len(V_fill))]

            fill_colors = map_planet_climate_palette(dominant_biomes)

        except Exception as e:
            logger.error(f"Ошибка при расчете климата для планеты: {e}", exc_info=True)
            heights_01 = get_noise_for_sphere_view(sphere_params, V_fill).flatten()
            fill_colors = map_planet_height_palette(heights_01)
    else:
        logger.info("  -> Режим климата выключен. Раскраска по высоте.")
        heights_01 = get_noise_for_sphere_view(sphere_params, V_fill).flatten()
        fill_colors = map_planet_height_palette(heights_01)

    # --- ШАГ 4: Сборка итоговых массивов ---
    offset = len(V_fill)
    all_vertices = np.vstack([V_fill, V_lines]).astype(np.float32)
    # Создаем черный цвет для вершин линий
    line_colors = np.zeros_like(V_lines, dtype=np.float32)
    all_colors = np.vstack([fill_colors.reshape(-1, 3), line_colors])
    all_line_indices = (np.array(I_lines, dtype=np.uint32) + offset).flatten()

    # --- ШАГ 5: Сохранение и возврат результата ---
    if main_window.project_manager.current_project_path:
        cache_dir = Path(main_window.project_manager.current_project_path) / "cache"
        cache_dir.mkdir(exist_ok=True)
        cache_file = cache_dir / "planet_geometry.npz"
        np.savez_compressed(cache_file, vertices=all_vertices, fill_indices=F_fill, line_indices=all_line_indices,
                            colors=all_colors, planet_data=planet_data)
        logger.info(f"Геометрия планеты сохранена в кэш: {cache_file}")

    return {
        "vertices": all_vertices, "fill_indices": F_fill, "line_indices": all_line_indices,
        "colors": all_colors, "planet_data": planet_data
    }