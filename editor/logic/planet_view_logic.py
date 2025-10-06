# editor/logic/planet_view_logic.py
import logging
import math
import numpy as np
from PySide6 import QtWidgets
import traceback

from editor.core.render_settings import RenderSettings
from editor.render_palettes import map_palette_cpu
from generator_logic.topology.icosa_grid import build_hexplanet
from generator_logic.terrain.global_sphere_noise import get_noise_for_sphere_view

logger = logging.getLogger(__name__)


def _normalize_vector(v):
    """Нормализует вектор или массив векторов."""
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(norm, 1e-9)


def _slerp(u: np.ndarray, v: np.ndarray, t: float) -> np.ndarray:
    """
    Сферическая интерполяция между двумя единичными векторами u и v.
    Возвращает точку на дуге большого круга. t=0.5 — ровно середина ребра на сфере.
    """
    # гарантируем единичность входов
    u = u / max(np.linalg.norm(u), 1e-12)
    v = v / max(np.linalg.norm(v), 1e-12)
    dot = float(np.clip(np.dot(u, v), -1.0, 1.0))
    # угол между векторами
    theta = math.acos(dot)
    if theta < 1e-6:
        # почти совпадают — возвращаем u (или v), это ок
        return u.copy()
    sin_theta = math.sin(theta)
    a = math.sin((1.0 - t) * theta) / sin_theta
    b = math.sin(t * theta) / sin_theta
    w = a * u + b * v
    return w / max(np.linalg.norm(w), 1e-12)


def _subdivide_triangle(v1, v2, v3, level):
    """
    Рекурсивно подразделяет сферический треугольник на 4 меньших,
    строго удерживая вершины на единичной сфере за счёт slerp.
    """
    # исходные вершины на сфере (единичный радиус)
    v1 = v1 / max(np.linalg.norm(v1), 1e-12)
    v2 = v2 / max(np.linalg.norm(v2), 1e-12)
    v3 = v3 / max(np.linalg.norm(v3), 1e-12)

    if level <= 0:
        return [(v1, v2, v3)]

    # геодезические середины рёбер
    m12 = _slerp(v1, v2, 0.5)
    m23 = _slerp(v2, v3, 0.5)
    m31 = _slerp(v3, v1, 0.5)

    tris = []
    tris.extend(_subdivide_triangle(v1, m12, m31, level - 1))
    tris.extend(_subdivide_triangle(m12, v2, m23, level - 1))
    tris.extend(_subdivide_triangle(m31, m23, v3, level - 1))
    tris.extend(_subdivide_triangle(m12, m23, m31, level - 1))
    return tris


def _generate_hex_sphere_geometry(
        planet_data: dict,
        sphere_params: dict,
        disp_scale: float,
        render_settings: RenderSettings,
        subdivision_level: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Генерирует высокодетализированную геометрию сферы, подразделяя каждый гексагон.
    """
    polys_lonlat = planet_data['cell_polys_lonlat_rad']
    centers_xyz = planet_data['centers_xyz']

    def lonlat_to_xyz(lon, lat, radius=1.0):
        # считаем в float64 для точности, приводим в конце
        lon = float(lon);
        lat = float(lat)
        x = math.cos(lat) * math.cos(lon)
        y = math.cos(lat) * math.sin(lon)
        z = math.sin(lat)
        v = np.array([x, y, z], dtype=np.float64)
        v /= max(np.linalg.norm(v), 1e-12)
        return (v * radius).astype(np.float32)

    all_triangles: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []

    # --- ШАГ 1: Для каждого гексагона создаем детализированную сетку ---
    for i, poly in enumerate(polys_lonlat):
        if len(poly) < 3:
            continue
        poly_verts_3d = np.array([lonlat_to_xyz(lon, lat) for lon, lat in poly], dtype=np.float32)
        poly_verts_3d = _normalize_vector(poly_verts_3d)
        center_3d = centers_xyz[i].astype(np.float32)
        center_3d = center_3d / max(np.linalg.norm(center_3d), 1e-9)
        for j in range(len(poly_verts_3d)):
            v1 = poly_verts_3d[j]
            v2 = poly_verts_3d[(j + 1) % len(poly_verts_3d)]
            sub_tris = _subdivide_triangle(center_3d, v1, v2, subdivision_level)
            all_triangles.extend(sub_tris)

    # --- ШАГ 2: Уникализируем вершины и формируем индексы треугольников ---
    vertex_map: dict[tuple, int] = {}
    unique_vertices: list[np.ndarray] = []
    final_triangles_indices: list[list[int]] = []
    for tri in all_triangles:
        tri_idx: list[int] = []
        for v in tri:
            key = tuple(np.round(v, 6))
            if key not in vertex_map:
                vertex_map[key] = len(unique_vertices)
                unique_vertices.append(np.asarray(v, dtype=np.float32))
            tri_idx.append(vertex_map[key])
        final_triangles_indices.append(tri_idx)

    V_sphere_base = np.array(unique_vertices, dtype=np.float32)
    F_fill = np.array(final_triangles_indices, dtype=np.uint32)
    V_sphere_base = _normalize_vector(V_sphere_base).astype(np.float32)
    try:
        r_base = np.linalg.norm(V_sphere_base, axis=1)
        logger.info(f"R(base) min/max = {r_base.min():.6f}/{r_base.max():.6f} (ожидаем ~1.000000)")
    except Exception:
        pass

    # --- ШАГ 3: Линии только по исходным гексам (без сабдивов) ---
    I_lines: list[list[int]] = []
    line_vertex_map: dict[tuple, int] = {}
    line_unique_vertices: list[np.ndarray] = []
    for poly in polys_lonlat:
        poly_indices: list[int] = []
        for lon, lat in poly:
            key = (round(lon, 6), round(lat, 6))
            if key not in line_vertex_map:
                line_vertex_map[key] = len(line_unique_vertices)
                line_unique_vertices.append(lonlat_to_xyz(lon, lat))
            poly_indices.append(line_vertex_map[key])
        for k in range(len(poly_indices)):
            I_lines.append([poly_indices[k], poly_indices[(k + 1) % len(poly_indices)]])
    line_vertices_array = np.array(line_unique_vertices, dtype=np.float32)

    # --- ШАГ 5: Смещаем вершины и собираем пакеты для рендера ---
    # 5.1 РЕЛЬЕФ (fill)
    heights = get_noise_for_sphere_view(sphere_params, V_sphere_base).flatten()
    power = sphere_params.get('power', 1.0)
    if power != 1.0:
        heights = np.power(heights, power)

    sea_level = sphere_params.get('sea_level_pct', 0.4)
    heights_with_sea = np.where(heights < sea_level, sea_level, heights)

    colors = map_palette_cpu(heights_with_sea, render_settings.palette_name, sea_level_pct=sea_level)
    # смещение рельефа
    displaced_vertices = V_sphere_base * (1.0 + disp_scale * (heights_with_sea - 0.5))[:, np.newaxis]
    # радиусы рельефа
    r_fill = np.linalg.norm(displaced_vertices, axis=1)
    r_fill_min = float(r_fill.min())
    r_fill_max = float(r_fill.max())

    # 5.2 ЛИНИИ (line) — ставим поверх ФАКТИЧЕСКОГО r_fill_max
    # нормализуем на всякий случай
    line_vertices_unit = _normalize_vector(line_vertices_array)
    # зазор делаем от фактического масштаба сцены (1% от макс. радиуса, но не меньше 0.002)
    line_margin = max(0.002, 0.01 * r_fill_max)
    line_radius = r_fill_max + line_margin
    line_vertices_displaced = line_vertices_unit * line_radius

    # логи для контроля
    try:
        r_line = np.linalg.norm(line_vertices_displaced, axis=1)
        logger.info(
            f"Max height: {float(heights_with_sea.max()):.4f}; "
            f"R(fill) min/max = {r_fill_min:.3f}/{r_fill_max:.3f}; "
            f"R(line) min/max = {float(r_line.min()):.3f}/{float(r_line.max()):.3f} "
            f"(lines outside: {line_radius > r_fill_max})"
        )
    except Exception:
        pass

    # 5.3 Сборка буферов
    offset = len(displaced_vertices)
    all_vertices = np.vstack([displaced_vertices, line_vertices_displaced]).astype(np.float32)

    line_colors = np.zeros_like(line_vertices_array, dtype=np.float32)  # цвета для линий не важны
    all_colors = np.vstack([colors.astype(np.float32), line_colors])

    all_line_indices = (np.array(I_lines, dtype=np.uint32) + offset).flatten()

    return all_vertices, F_fill, all_line_indices, all_colors


def orchestrate_planet_update(main_window):
    """
    Обновляет предпросмотр планеты.
    По умолчанию включает AUTO-режим: целевой пик-ту-пик рельефа = 0.3% радиуса (землеподобно).
    Учёт уровня моря: реальный размах над морем = disp_scale * (1 - sea_level).
    """
    if main_window.update_planet_btn:
        main_window.update_planet_btn.setEnabled(False)
    QtWidgets.QApplication.processEvents()

    try:
        # --- Радиус планеты ---
        radius_text = main_window.planet_radius_label.text().replace(" км", "").replace(",", "").replace(" ", "")
        radius_km = float(radius_text) if radius_text and radius_text != 'Ошибка' else 1.0
        radius_m = radius_km * 1000.0
        if radius_m < 1.0:
            raise ValueError("Радиус планеты слишком мал или не рассчитан.")

        # --- Уровень моря (0..1). Если вдруг пришли проценты, приводим к доле. ---
        sea_val = float(main_window.ws_sea_level.value())
        sea_level = sea_val * 0.01 if sea_val > 1.0 else sea_val
        sea_level = max(0.0, min(0.99, sea_level))  # страховка: не даём 1.0

        # --- AUTO пресет «Земля»: Δr_target = 0.3% радиуса ---
        delta_r_target = 0.003  # 0.3% от радиуса, пик-ту-пик
        # disp_scale таков, чтобы над морем мы получили ровно delta_r_target
        disp_scale = delta_r_target / max(1e-6, (1.0 - sea_level))
        eq_base_elevation_m = delta_r_target * radius_m  # эквивалентный пик-ту-пик в метрах

        # --- Параметры шума для предпросмотра (как было) ---
        scale_value = main_window.ws_relative_scale.value()
        frequency = 1.0 + (scale_value * 9.0)

        # Детализация предпросмотра из комбо «Средняя (3)» и т.п.
        detail_text = main_window.planet_preview_detail_input.currentText()
        subdivision_level = int(detail_text.split("(")[1].replace(")", ""))

        # Детализация гекса-сетки (чтобы не ломать твою логику)
        subdivision_level_grid = int(main_window.subdivision_level_input.currentText().split(" ")[0])

        logger.info(
            "Relief mode: AUTO(Earth 0.3%%). radius_km=%.3f (%.1f m), sea=%.3f -> "
            "Δr_target=%.6f (~%.3f%%), disp_scale=%.6f, eq_base_elevation≈%.1f m"
            % (radius_km, radius_m, sea_level, delta_r_target, delta_r_target*100.0,
               disp_scale, eq_base_elevation_m)
        )

        world_settings = {
            'subdivision_level': subdivision_level_grid,
            'disp_scale': disp_scale,
            'sphere_params': {
                'octaves': int(main_window.ws_octaves.value()),
                'gain': main_window.ws_gain.value(),
                'seed': main_window.ws_seed.value(),
                'frequency': frequency,
                'power': main_window.ws_power.value(),
                'sea_level_pct': sea_level,
            }
        }

        update_planet_widget(main_window.planet_widget, world_settings, main_window.render_settings, subdivision_level)

    except Exception as e:
        QtWidgets.QMessageBox.critical(
            main_window,
            "Ошибка",
            f"Не удалось обновить 3D-планету: {e}\n{traceback.format_exc()}"
        )
    finally:
        if main_window.update_planet_btn:
            main_window.update_planet_btn.setEnabled(True)



def update_planet_widget(planet_widget, world_settings: dict, render_settings: RenderSettings, subdivision_level: int):
    if planet_widget is None: return
    logger.info(f"Обновление 3D-вида планеты (уровень детализации: {subdivision_level})...")
    try:
        subdivision_level_grid = world_settings.get('subdivision_level', 8)
        disp_scale = world_settings.get('disp_scale', 0.05)
        sphere_params = world_settings.get('sphere_params', {})
        planet_data = build_hexplanet(f=subdivision_level_grid)
        if not planet_data: raise RuntimeError("Failed to generate planet data.")
        planet_widget.set_planet_data(planet_data)
        if hasattr(planet_widget, 'set_render_settings'):
            planet_widget.set_render_settings(render_settings)
        V, F_fill, I_lines, C = _generate_hex_sphere_geometry(
            planet_data, sphere_params, disp_scale, render_settings, subdivision_level
        )
        planet_widget.set_geometry(V, F_fill, I_lines, C)
        logger.info(f"3D-вид планеты успешно обновлен ({len(V)} вершин, {len(F_fill)} полигонов).")
    except Exception as e:
        logger.exception(f"Ошибка при обновлении 3D-вида планеты: {e}")
        raise