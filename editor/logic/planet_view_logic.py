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


def _generate_hex_sphere_geometry(
        planet_data: dict, sphere_params: dict, disp_scale: float, render_settings: RenderSettings
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Генерирует единую геометрию сферы, состоящую из гексов.
    """
    polys_lonlat = planet_data['cell_polys_lonlat_rad']

    def lonlat_to_xyz(lon, lat, radius=1.0):
        x = np.cos(lat) * np.cos(lon)
        y = np.cos(lat) * np.sin(lon)
        z = np.sin(lat)
        return np.array([x, y, z], dtype=np.float32) * radius

    # --- ШАГ 1: Собираем все уникальные вершины из всех полигонов ---
    vertex_map = {}
    unique_vertices_lonlat = []

    for poly in polys_lonlat:
        for lon, lat in poly:
            # Округляем, чтобы избавиться от микро-различий в float
            key = (round(lon, 6), round(lat, 6))
            if key not in vertex_map:
                vertex_map[key] = len(unique_vertices_lonlat)
                unique_vertices_lonlat.append((lon, lat))

    # Конвертируем lon/lat в 3D-координаты
    V_sphere_base = np.array([lonlat_to_xyz(lon, lat) for lon, lat in unique_vertices_lonlat], dtype=np.float32)

    # --- ШАГ 2: Создаем полигоны и линии, используя индексы уникальных вершин ---
    F_fill = []
    I_lines = []
    for poly in polys_lonlat:
        if len(poly) < 3: continue

        # Собираем индексы вершин для текущего полигона
        poly_indices = [vertex_map[(round(lon, 6), round(lat, 6))] for lon, lat in poly]

        # Триангулируем полигон "веером" от первой вершины
        p0_idx = poly_indices[0]
        for i in range(1, len(poly_indices) - 1):
            F_fill.append([p0_idx, poly_indices[i], poly_indices[i + 1]])

        # Создаем линии для контура
        for i in range(len(poly_indices)):
            I_lines.append([poly_indices[i], poly_indices[(i + 1) % len(poly_indices)]])

    # --- ШАГ 3: Вычисляем высоты и цвета для УНИКАЛЬНЫХ вершин ---
    heights = get_noise_for_sphere_view(sphere_params, V_sphere_base).flatten()
    power = sphere_params.get('power', 1.0)
    if power != 1.0:
        heights = np.power(heights, power)

    sea_level = sphere_params.get('sea_level_pct', 0.4)
    heights_with_sea = np.where(heights < sea_level, sea_level, heights)

    colors = map_palette_cpu(heights_with_sea, render_settings.palette_name, sea_level_pct=sea_level)

    # --- ШАГ 4: Смещаем вершины и объединяем данные ---
    displaced_vertices = V_sphere_base * (1.0 + disp_scale * (heights_with_sea - 0.5))[:, np.newaxis]

    # Теперь у нас единый набор вершин для всего
    final_vertices = displaced_vertices.astype(np.float32)
    final_colors = colors.astype(np.float32)

    # Объединяем вершины от шара и линий (они теперь одни и те же)
    # Это нужно, чтобы виджет получил один большой массив
    all_vertices = final_vertices
    all_colors = final_colors

    # Линии используют те же самые индексы вершин, что и полигоны
    all_line_indices = np.array(I_lines, dtype=np.uint32).flatten()

    return (
        all_vertices,
        np.array(F_fill, dtype=np.uint32),
        all_line_indices,
        all_colors
    )


def update_planet_widget(planet_widget, world_settings: dict, render_settings: RenderSettings):
    if planet_widget is None: return
    logger.info("Обновление 3D-вида планеты (геометрия из гексов)...")
    try:
        subdivision_level = world_settings.get('subdivision_level', 8)
        disp_scale = world_settings.get('disp_scale', 0.05)
        sphere_params = world_settings.get('sphere_params', {})

        planet_data = build_hexplanet(f=subdivision_level)
        if not planet_data: raise RuntimeError("Failed to generate planet data.")

        planet_widget.set_planet_data(planet_data)
        if hasattr(planet_widget, 'set_render_settings'):
            planet_widget.set_render_settings(render_settings)

        V, F_fill, I_lines, C = _generate_hex_sphere_geometry(
            planet_data, sphere_params, disp_scale, render_settings
        )
        planet_widget.set_geometry(V, F_fill, I_lines, C)
        logger.info(f"3D-вид планеты успешно обновлен ({len(V)} вершин).")
    except Exception as e:
        logger.exception(f"Ошибка при обновлении 3D-вида планеты: {e}")
        raise


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
        update_planet_widget(main_window.planet_widget, world_settings, main_window.render_settings)
    except Exception as e:
        QtWidgets.QMessageBox.critical(main_window, "Ошибка",
                                       f"Не удалось обновить 3D-планету: {e}\n{traceback.format_exc()}")
    finally:
        if main_window.update_planet_btn: main_window.update_planet_btn.setEnabled(True)