# ЗАМЕНА ВСЕГО ФАЙЛА: editor/logic/planet_view_logic.py
import json
import logging
import math
import numpy as np
from PySide6 import QtWidgets
from pathlib import Path
from dataclasses import dataclass

# Импорты вашего проекта
from editor.render.planet_palettes import map_planet_height_palette, map_planet_bimodal_palette
from generator_logic.climate import biome_matcher, global_climate
from generator_logic.topology.icosa_grid import build_hexplanet
from generator_logic.terrain.global_sphere_noise import get_noise_for_sphere_view
from editor.ui.layouts.world_settings_panel import PLANET_ROUGHNESS_PRESETS

logger = logging.getLogger(__name__)


# --- ШАГ 1: Сборщик параметров в виде структуры данных ---
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
            'land_warming_effect_c': 2.5
        },
        sea_level_01=main_window.climate_sea_level.value() / 100.0
    )


# --- Вспомогательные функции для геометрии (без изменений) ---
def _normalize_vector(v):
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(norm, 1e-9)


def _slerp(u, v, t):
    u = _normalize_vector(u);
    v = _normalize_vector(v)
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


# --- ШАГ 2: Генератор базовой геометрии ---
def _generate_base_geometry(planet_data: dict, subdivision_level: int) -> tuple[
    np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
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


# --- ШАГ 3, 4, 5: Генерация высот, климата, цветов и сборка ---
def orchestrate_planet_update(main_window) -> dict | None:
    """
    Главная функция-оркестратор. Собирает параметры и последовательно вызывает
    функции для генерации геометрии, высот, климата и данных для рендера.
    """
    logger.info("Обновление вида планеты (рефакторинг)...")

    try:
        # 1. Сбор параметров
        params = _gather_planet_parameters(main_window)

        # 2. Создание топологии и базовой геометрии для РЕНДЕРА
        planet_data = build_hexplanet(f=params.subdivision_level_grid)
        V_base, F_fill, V_lines, I_lines = _generate_base_geometry(planet_data, params.subdivision_level_geom)

        # 3. Генерация карты высот (для рендера)
        heights_01_render = get_noise_for_sphere_view(params.sphere_params, V_base)
        heights_01_render = heights_01_render.flatten()
        V_displaced = V_base * (1.0 + params.disp_scale * (heights_01_render - 0.5))[:, np.newaxis]

        # 4. Симуляция климата и получение цветов
        if params.is_climate_enabled:
            logger.info("  -> Режим климата включен. Запуск симуляции на ЛОГИЧЕСКОЙ сетке...")
            biomes_path = Path("game_engine_restructured/data/biomes.json")
            with open(biomes_path, "r", encoding="utf-8") as f:
                biomes_definition = json.load(f)

            # --- Шаг 4.1: Вычисляем параметры на логической сетке (ячейках) ---
            centers_xyz = planet_data['centers_xyz']
            heights_01_on_grid = get_noise_for_sphere_view(params.sphere_params, centers_xyz)
            heights_01_on_grid = heights_01_on_grid.flatten()  # <--- ДОБАВИТЬ ЭТУ СТРОКУ
            is_land_mask_on_grid = heights_01_on_grid >= params.sea_level_01

            sea_level_m_abs = (params.radius_m - params.max_displacement_m) + (
                        params.sea_level_01 * (2 * params.max_displacement_m))

            V_displaced_on_grid = centers_xyz * (1.0 + params.disp_scale * (heights_01_on_grid - 0.5))[:, np.newaxis]
            vertex_heights_abs = np.linalg.norm(V_displaced * params.radius_m, axis=1)
            heights_m_above_sea = vertex_heights_abs - sea_level_m_abs
            heights_m_above_sea_on_grid = heights_abs_on_grid - sea_level_m_abs

            # --- Шаг 4.2: Запускаем симуляцию с данными, соответствующими `neighbors` ---
            climate_data_on_grid = global_climate.orchestrate_global_climate_simulation(
                xyz_coords=centers_xyz,
                heights_m=heights_m_above_sea_on_grid,
                is_land_mask=is_land_mask_on_grid,
                neighbors=planet_data['neighbors'],
                params=params.climate_params
            )

            # --- Шаг 4.3: Переносим данные о климате с ячеек на вершины рендер-модели ---
            from generator_logic.topology.icosa_grid import nearest_cell_by_xyz
            # Для каждой вершины находим ID ближайшей ячейки
            vertex_to_cell_map = np.array([nearest_cell_by_xyz(v, centers_xyz) for v in V_base], dtype=np.int32)

            # Собираем биомы для каждой ВЕРШИНЫ на основе данных из ближайшей ячейки
            dominant_biomes_for_render = []
            is_land_mask_render = heights_01_render >= params.sea_level_01  # Маска суши для рендер-модели

            for i in range(len(V_base)):
                if not is_land_mask_render[i]:
                    dominant_biomes_for_render.append("water")  # Это просто заглушка для палитры
                    continue

                cell_idx = vertex_to_cell_map[i]
                temp = climate_data_on_grid["temperature"][cell_idx]
                hum = climate_data_on_grid["humidity"][cell_idx]

                probs = biome_matcher.calculate_biome_probabilities(temp, hum, biomes_definition)
                dominant_biomes_for_render.append(max(probs, key=probs.get) if probs else "default")

            colors = map_planet_bimodal_palette(heights_01_render, params.sea_level_01, dominant_biomes_for_render)
        else:
            logger.info("  -> Режим климата выключен. Раскраска по высоте.")
            colors = map_planet_height_palette(heights_01_render)

        # 6. Сборка данных для рендера
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

        # 7. Кэширование
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