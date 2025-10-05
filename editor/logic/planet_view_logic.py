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


def _subdivide_triangle(v1, v2, v3, level):
    """Рекурсивно подразделяет треугольник на 4 меньших на ЕДИНИЧНОЙ сфере."""
    # НОРМАЛИЗУЕМ исходные вершины — ключ к одинаковому радиусу!
    v1 = v1 / np.linalg.norm(v1)
    v2 = v2 / np.linalg.norm(v2)
    v3 = v3 / np.linalg.norm(v3)

    if level <= 0:
        return [(v1, v2, v3)]

    # Находим средние точки рёбер и проецируем их на сферу
    m12 = (v1 + v2) / 2.0;  m12 /= np.linalg.norm(m12)
    m23 = (v2 + v3) / 2.0;  m23 /= np.linalg.norm(m23)
    m31 = (v3 + v1) / 2.0;  m31 /= np.linalg.norm(m31)

    # Рекурсивно подразделяем 4 новых треугольника
    triangles = []
    triangles.extend(_subdivide_triangle(v1,  m12, m31, level - 1))
    triangles.extend(_subdivide_triangle(m12, v2,  m23, level - 1))
    triangles.extend(_subdivide_triangle(m31, m23, v3,  level - 1))
    triangles.extend(_subdivide_triangle(m12, m23, m31, level - 1))
    return triangles


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
    polys_lonlat = planet_data['cell_polys_lonlat_rad']   # список полигонов: [(lon,lat), ...] в радианах
    centers_xyz  = planet_data['centers_xyz']             # np.ndarray [N,3] центров ячеек (может быть не на радиусе 1)

    def lonlat_to_xyz(lon, lat, radius=1.0):
        x = np.cos(lat) * np.cos(lon)
        y = np.cos(lat) * np.sin(lon)
        z = np.sin(lat)
        return np.array([x, y, z], dtype=np.float32) * radius

    all_triangles: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []

    # --- ШАГ 1: Для каждого гексагона создаем детализированную сетку ---
    for i, poly in enumerate(polys_lonlat):
        if len(poly) < 3:
            continue

        # Вершины полигона на единичной сфере
        poly_verts_3d = np.array([lonlat_to_xyz(lon, lat) for lon, lat in poly], dtype=np.float32)
        poly_verts_3d = _normalize_vector(poly_verts_3d)

        # ЦЕНТР ЯЧЕЙКИ: БЕРЁМ ИЗ centers_xyz И НОРМАЛИЗУЕМ (этого не хватало)
        center_3d = centers_xyz[i].astype(np.float32)
        center_3d = center_3d / max(np.linalg.norm(center_3d), 1e-9)

        # 6 стартовых треугольников (центр -> рёбра)
        for j in range(len(poly_verts_3d)):
            v1 = poly_verts_3d[j]
            v2 = poly_verts_3d[(j + 1) % len(poly_verts_3d)]

            # Рекурсивное подразделение на ЕДИНИЧНОЙ сфере
            sub_tris = _subdivide_triangle(center_3d, v1, v2, subdivision_level)
            all_triangles.extend(sub_tris)

    # --- ШАГ 2: Уникализируем вершины и формируем индексы треугольников ---
    vertex_map: dict[tuple, int] = {}
    unique_vertices: list[np.ndarray] = []
    final_triangles_indices: list[list[int]] = []

    for tri in all_triangles:
        tri_idx: list[int] = []
        for v in tri:
            key = tuple(np.round(v, 6))  # сглаживаем флоат-шума
            if key not in vertex_map:
                vertex_map[key] = len(unique_vertices)
                unique_vertices.append(np.asarray(v, dtype=np.float32))
            tri_idx.append(vertex_map[key])
        final_triangles_indices.append(tri_idx)

    V_sphere_base = np.array(unique_vertices, dtype=np.float32)          # [M,3]
    F_fill        = np.array(final_triangles_indices, dtype=np.uint32)   # [K,3]

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
                line_unique_vertices.append(lonlat_to_xyz(lon, lat))  # уже на радиусе 1
            poly_indices.append(line_vertex_map[key])

        for k in range(len(poly_indices)):
            I_lines.append([poly_indices[k], poly_indices[(k + 1) % len(poly_indices)]])

    line_vertices_array = np.array(line_unique_vertices, dtype=np.float32)  # [L,3], радиус 1

    # --- ШАГ 4: Вычисляем высоты и цвета для высокодетализированных вершин ---
    heights = get_noise_for_sphere_view(sphere_params, V_sphere_base).flatten()
    power = sphere_params.get('power', 1.0)
    if power != 1.0:
        heights = np.power(heights, power)

    # ФИКС: Clip в [0,1] — шум не "взрывает" радиус за пределы
    heights = np.clip(heights, 0.0, 1.0)

    sea_level = sphere_params.get('sea_level_pct', 0.4)
    heights_with_sea = np.where(heights < sea_level, sea_level, heights)

    colors = map_palette_cpu(heights_with_sea, render_settings.palette_name, sea_level_pct=sea_level)

    # --- ШАГ 5: Смещаем вершины и собираем пакеты для рендера ---
    # Заполняемая геометрия (рельеф)
    displaced_vertices = V_sphere_base * (1.0 + disp_scale * (heights_with_sea - 0.5))[:, np.newaxis]

    # ФИКС: Динамический радиус линий — снаружи max рельефа
    max_height = np.max(heights_with_sea)
    margin = max(0.002, 0.05 * disp_scale)
    line_radius = 1.0 + disp_scale * (max_height - 0.5) + margin
    line_vertices_displaced = line_vertices_array * line_radius

    # Логи радиусов — проверь в консоли, чтоб убедиться (r_line > r_fill.max)
    try:
        r_fill = np.linalg.norm(displaced_vertices, axis=1)
        r_line = np.linalg.norm(line_vertices_displaced, axis=1)
        logger.info(
            f"Max height: {max_height:.4f}; "
            f"R(fill) min/max = {r_fill.min():.3f}/{r_fill.max():.3f}; "
            f"R(line) min/max = {r_line.min():.3f}/{r_line.max():.3f} "
            f"(lines outside: {r_line.min() > r_fill.max()})"
        )
    except Exception:
        pass

    # Конкатенируем (остальное без изменений)
    offset = len(displaced_vertices)
    all_vertices = np.vstack([displaced_vertices, line_vertices_displaced]).astype(np.float32)

    # Цвет для линий — нули, просто чтобы буфер совпадал по длине
    line_colors = np.zeros_like(line_vertices_array, dtype=np.float32)
    all_colors = np.vstack([colors.astype(np.float32), line_colors])

    # Индексы линий со смещением
    all_line_indices = (np.array(I_lines, dtype=np.uint32) + offset).flatten()

    return all_vertices, F_fill, all_line_indices, all_colors

def orchestrate_planet_update(main_window):
    if main_window.update_planet_btn: main_window.update_planet_btn.setEnabled(False)
    QtWidgets.QApplication.processEvents()
    try:
        radius_text = main_window.planet_radius_label.text().replace(" км", "").replace(",", "").replace(" ", "")
        radius_km = float(radius_text) if radius_text and radius_text != 'Ошибка' else 1.0
        radius_m = radius_km * 1000.0
        if radius_m < 1.0: raise ValueError("Радиус планеты слишком мал или не рассчитан.")

        elevation_text = main_window.base_elevation_label.text().replace(" м", "").replace(",", "").replace(" ", "")
        base_elevation_m = float(elevation_text) if elevation_text and elevation_text != 'Ошибка' else 1000.0
        disp_scale = base_elevation_m / radius_m

        scale_value = main_window.ws_relative_scale.value()
        frequency = 1.0 + (scale_value * 9.0)

        # --- НАЧАЛО ИЗМЕНЕНИЙ ---
        # Считываем уровень детализации из нового UI-элемента
        detail_text = main_window.planet_preview_detail_input.currentText()
        subdivision_level = int(detail_text.split("(")[1].replace(")", ""))
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---

        world_settings = {
            'subdivision_level': int(main_window.subdivision_level_input.currentText().split(" ")[0]),
            'disp_scale': disp_scale,
            'sphere_params': {
                'octaves': int(main_window.ws_octaves.value()),
                'gain': main_window.ws_gain.value(),
                'seed': main_window.ws_seed.value(),
                'frequency': frequency,
                'power': main_window.ws_power.value(),
                'sea_level_pct': main_window.ws_sea_level.value(),
            }
        }

        # --- НАЧАЛО ИЗМЕНЕНИЙ ---
        update_planet_widget(main_window.planet_widget, world_settings, main_window.render_settings, subdivision_level)
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    except Exception as e:
        QtWidgets.QMessageBox.critical(main_window, "Ошибка",
                                       f"Не удалось обновить 3D-планету: {e}\n{traceback.format_exc()}")
    finally:
        if main_window.update_planet_btn: main_window.update_planet_btn.setEnabled(True)


# --- НАЧАЛО ИЗМЕНЕНИЙ ---
def update_planet_widget(planet_widget, world_settings: dict, render_settings: RenderSettings, subdivision_level: int):
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---
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

        # --- НАЧАЛО ИЗМЕНЕНИЙ ---
        V, F_fill, I_lines, C = _generate_hex_sphere_geometry(
            planet_data, sphere_params, disp_scale, render_settings, subdivision_level
        )
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---

        planet_widget.set_geometry(V, F_fill, I_lines, C)
        logger.info(f"3D-вид планеты успешно обновлен ({len(V)} вершин, {len(F_fill)} полигонов).")

    except Exception as e:
        logger.exception(f"Ошибка при обновлении 3D-вида планеты: {e}")
        raise