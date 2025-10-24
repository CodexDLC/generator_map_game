# ЗАМЕНА ВСЕГО ФАЙЛА: editor/logic/planet_view_logic.py
import json
import logging
import math
import numpy as np
from pathlib import Path
from dataclasses import dataclass

from editor.render.palettes import map_planet_bimodal_palette
from generator_logic.climate import biome_matcher
from generator_logic.topology.icosa_grid import build_hexplanet, nearest_cell_by_xyz
from generator_logic.terrain.global_sphere_noise import get_noise_for_sphere_view
from editor.ui.layouts.world_settings_panel import PLANET_ROUGHNESS_PRESETS

logger = logging.getLogger(__name__)


@dataclass
class PlanetUpdateParams:
    """Структура для хранения всех параметров, собранных из UI."""
    radius_m: float
    max_displacement_m: float
    disp_scale: float
    sphere_params: dict
    subdivision_level_geom: int
    subdivision_level_grid: int
    is_climate_enabled: bool
    climate_params: dict
    sea_level_01: float


def _gather_planet_parameters(main_window) -> PlanetUpdateParams:
    """Собирает все необходимые параметры из UI в один объект."""
    try:
        radius_text = main_window.planet_radius_label.text().replace(" км", "").replace(",", "").replace(" ", "")
        radius_km = float(radius_text)
    except (ValueError, TypeError):
        radius_km = 6371.0
    radius_m = radius_km * 1000.0
    if radius_m < 1.0: raise ValueError("Радиус планеты слишком мал")

    preset_name = main_window.planet_type_preset_input.currentText()
    roughness_pct, _ = PLANET_ROUGHNESS_PRESETS.get(preset_name, (0.003, 2.5))
    disp_scale = roughness_pct * 1.5
    max_displacement_m = radius_m * disp_scale * 0.5

    continent_size_km = main_window.ws_continent_scale_km.value()
    frequency = 20000.0 / max(continent_size_km, 1.0)

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

    return PlanetUpdateParams(
        radius_m=radius_m,
        max_displacement_m=max_displacement_m,
        disp_scale=disp_scale,
        sphere_params=sphere_params,
        subdivision_level_geom=subdivision_level_geom,
        subdivision_level_grid=subdivision_level_grid,
        is_climate_enabled=main_window.climate_enabled.isChecked(),
        climate_params={
            'avg_temp_c': main_window.climate_avg_temp.value(),
            'axis_tilt_deg': main_window.climate_axis_tilt.value(),
        },
        sea_level_01=main_window.climate_sea_level.value() / 100.0
    )


def _normalize_vector(v):
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(norm, 1e-9)


def _slerp(u, v, t):
    u, v = _normalize_vector(u), _normalize_vector(v)
    dot = float(np.clip(np.dot(u, v), -1.0, 1.0))
    theta = math.acos(dot)
    if theta < 1e-6: return u.copy()
    sin_theta = math.sin(theta)
    a = math.sin((1.0 - t) * theta) / sin_theta
    b = math.sin(t * theta) / sin_theta
    return _normalize_vector(a * u + b * v)


def _subdivide_triangle(v1, v2, v3, level):
    if level <= 0: return [(v1, v2, v3)]
    m12, m23, m31 = _slerp(v1, v2, 0.5), _slerp(v2, v3, 0.5), _slerp(v3, v1, 0.5)
    tris = []
    tris.extend(_subdivide_triangle(v1, m12, m31, level - 1))
    tris.extend(_subdivide_triangle(m12, v2, m23, level - 1))
    tris.extend(_subdivide_triangle(m31, m23, v3, level - 1))
    tris.extend(_subdivide_triangle(m12, m23, m31, level - 1))
    return tris


def _generate_base_geometry(planet_data: dict, subdivision_level: int):
    polys_lonlat = planet_data['cell_polys_lonlat_rad']
    centers_xyz = planet_data['centers_xyz']

    def lonlat_to_xyz(lon, lat):
        x = math.cos(lat) * math.cos(lon)
        y = math.cos(lat) * math.sin(lon)
        z = math.sin(lat)
        return np.array([x, y, z], dtype=np.float32)

    all_triangles = []
    for i, poly in enumerate(polys_lonlat):
        if len(poly) < 3: continue
        poly_verts_3d = _normalize_vector(np.array([lonlat_to_xyz(lon, lat) for lon, lat in poly]))
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
                unique_vertices.append(v)
            tri_idx.append(vertex_map[key])
        final_triangles_indices.append(tri_idx)

    V_sphere_base = _normalize_vector(np.array(unique_vertices, dtype=np.float32))
    F_fill = np.array(final_triangles_indices, dtype=np.uint32)
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

    V_lines = _normalize_vector(np.array(line_unique_vertices, dtype=np.float32))
    return V_sphere_base, F_fill, V_lines, np.array(I_lines, dtype=np.uint32)


def orchestrate_planet_update(main_window) -> dict | None:
    logger.info("Запуск полной симуляции планеты...")
    try:
        params = _gather_planet_parameters(main_window)

        # Генерируем ДВЕ сетки:
        # 1. Логическая сетка (грубая) - для гексагональной сетки и ID регионов
        planet_data = build_hexplanet(f=params.subdivision_level_grid)
        # 2. Визуальная/симуляционная сетка (детальная) - для рендеринга и точного климата
        V_base, F_fill, V_lines, I_lines = _generate_base_geometry(planet_data, params.subdivision_level_geom)
        logger.info(f"-> Геометрия сгенерирована: {len(V_base)} вершин для симуляции/рендера.")

        # Генерация рельефа на детальной сетке
        heights_01 = get_noise_for_sphere_view(params.sphere_params, V_base).flatten()
        V_displaced = V_base * (1.0 + params.disp_scale * (heights_01 - 0.5))[:, np.newaxis]

        if params.is_climate_enabled:
            logger.info("-> Расчет детального климата на сетке рендеринга...")
            biomes_path = Path("game_engine_restructured/data/biomes.json")
            with open(biomes_path, "r", encoding="utf-8") as f:
                biomes_definition = json.load(f)

            # --- Шаг 1: Расчет климата на каждой вершине детальной сетки ---
            is_land_mask = heights_01 >= params.sea_level_01
            heights_abs = np.linalg.norm(V_displaced * params.radius_m, axis=1)
            sea_level_m_abs = (params.radius_m - params.max_displacement_m) + (
                        params.sea_level_01 * (2 * params.max_displacement_m))
            heights_m_above_sea = heights_abs - sea_level_m_abs

            # ИЗМЕНЕНИЕ ЗДЕСЬ: Возвращаем расчет широты на ось Z (индекс 2)
            latitude_factor = np.abs(V_base[:, 2])
            base_temp = params.climate_params.get("avg_temp_c", 15.0)
            equator_pole_diff = params.climate_params.get("axis_tilt_deg", 23.5) * 1.5
            latitudinal_temp = (base_temp + equator_pole_diff / 3.0) - latitude_factor * equator_pole_diff
            temperature_map = latitudinal_temp + heights_m_above_sea * -0.0065

            humidity_map = np.full_like(temperature_map, 0.4, dtype=np.float32)
            humidity_map[~is_land_mask] = 1.0

            # --- Шаг 2: Определение биомов и цветов для каждой вершины ---
            dominant_biomes_for_render = []
            for i in range(len(V_base)):
                if not is_land_mask[i]:
                    dominant_biomes_for_render.append("water")
                    continue
                temp, hum = temperature_map[i], humidity_map[i]
                probs = biome_matcher.calculate_biome_probabilities(temp, hum, biomes_definition)
                dominant_biomes_for_render.append(max(probs, key=probs.get) if probs else "default")

            colors = map_planet_bimodal_palette(heights_01, params.sea_level_01, dominant_biomes_for_render)

            # --- Шаг 3: Агрегация детальных данных в кэш для грубой логической сетки ---
            logger.info("-> Агрегация детальных данных о климате в кэш регионов...")
            vertex_to_cell_map = np.array([nearest_cell_by_xyz(v, planet_data['centers_xyz']) for v in V_base],
                                          dtype=np.int32)

            global_climate_cache = {"version": 2, "world_seed": params.sphere_params['seed'], "region_data": {}}
            num_regions = len(planet_data['centers_xyz'])
            for i in range(num_regions):
                region_vertex_indices = np.where(vertex_to_cell_map == i)[0]
                if region_vertex_indices.size == 0: continue

                avg_temp = np.mean(temperature_map[region_vertex_indices])
                avg_hum = np.mean(humidity_map[region_vertex_indices])
                probs = biome_matcher.calculate_biome_probabilities(avg_temp, avg_hum, biomes_definition)
                sanitized_probs = {k: float(v) for k, v in probs.items()}

                global_climate_cache["region_data"][str(i)] = {
                    "average_temperature_c": float(avg_temp),
                    "average_humidity": float(avg_hum),
                    "dominant_biome": max(sanitized_probs, key=sanitized_probs.get) if sanitized_probs else "default",
                    "biome_probabilities": sanitized_probs
                }

            if main_window.project_manager.current_project_path:
                cache_dir = Path(main_window.project_manager.current_project_path) / "cache"
                cache_dir.mkdir(exist_ok=True)
                cache_file = cache_dir / "global_climate_data.json"
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(global_climate_cache, f, indent=2)
                logger.info(f"Глобальный кэш климата сохранен: {cache_file}")
        else:
            logger.info("-> Режим климата выключен. Раскраска по высоте.")
            colors = map_height_to_grayscale(heights_01)

        # Сборка данных для рендера
        r_fill_max = float(np.linalg.norm(V_displaced, axis=1).max())
        V_lines_displaced = V_lines * (r_fill_max + max(0.002, 0.01 * r_fill_max))
        offset = len(V_displaced)
        all_vertices = np.vstack([V_displaced, V_lines_displaced]).astype(np.float32)
        line_colors = np.zeros((len(V_lines_displaced), 3), dtype=np.float32)
        all_colors = np.vstack([colors.reshape(-1, 3), line_colors])
        all_line_indices = (I_lines + offset)

        render_data = {
            "vertices": all_vertices, "fill_indices": F_fill,
            "line_indices": all_line_indices.flatten(),
            "colors": all_colors, "planet_data": planet_data
        }

        if main_window.project_manager.current_project_path:
            cache_dir = Path(main_window.project_manager.current_project_path) / "cache"
            cache_dir.mkdir(exist_ok=True)
            cache_file = cache_dir / "planet_geometry.npz"
            np.savez_compressed(cache_file, **render_data)
            logger.info(f"Геометрия планеты сохранена в кэш: {cache_file}")

        return render_data
    except Exception as e:
        logger.error(f"Ошибка при обновлении вида планеты: {e}", exc_info=True)
        return None