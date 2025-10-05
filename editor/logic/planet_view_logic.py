# editor/logic/planet_view_logic.py
import logging
import math
import numpy as np
from PySide6 import QtGui, QtWidgets
import traceback

from editor.core.render_settings import RenderSettings
from editor.render_palettes import map_palette_cpu
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


def _generate_faceted_geometry(planet_data: dict, sphere_params: dict, disp_scale: float, context: dict, render_settings: 'RenderSettings') -> tuple[
    np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    from generator_logic.terrain.global_sphere_noise import get_noise_for_sphere_view

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

    heights_per_vertex = get_noise_for_sphere_view(
        sphere_params,
        coords_xyz=all_poly_verts_3d
    )
    if heights_per_vertex.ndim > 1:
        heights_per_vertex = heights_per_vertex.ravel()

    power = sphere_params.get('power', 1.0)
    if power != 1.0:
        heights_per_vertex = np.power(heights_per_vertex, power)

    sea_level_pct = sphere_params.get('sea_level_pct', 0.4)
    palette_name = render_settings.palette_name
    colors_per_vertex = map_palette_cpu(heights_per_vertex, palette_name, sea_level_pct=sea_level_pct)

    displaced_vertices = all_poly_verts_3d * (1.0 + disp_scale * (heights_per_vertex - 0.5))[:, np.newaxis]

    return (displaced_vertices.astype(np.float32),
            np.array(fill_indices, dtype=np.uint32),
            np.array(line_indices, dtype=np.uint32),
            heights_per_vertex.astype(np.float32),
            colors_per_vertex.astype(np.float32))


def update_planet_widget(planet_widget, world_settings: dict, render_settings: RenderSettings):
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

        if hasattr(planet_widget, 'set_planet_data'):
            planet_widget.set_planet_data(planet_data)

        context = {'project': {'seed': sphere_params.get('seed', 0)}}

        # --- ИСПРАВЛЕНИЕ: Добавляем недостающий аргумент 'render_settings' в вызов ---
        V, F_fill, I_lines, V_heights, V_colors = _generate_faceted_geometry(
            planet_data,
            sphere_params,
            disp_scale,
            context,
            render_settings
        )

        planet_widget.set_geometry(V, F_fill, I_lines, V_heights, V_colors)

        logger.info("3D-вид планеты успешно обновлен (faceted).")

    except Exception as e:
        logger.exception(f"Ошибка при обновлении 3D-вида планеты: {e}")
        raise


def orchestrate_planet_update(main_window):
    """Собирает данные из UI и запускает обновление 3D-вида планеты."""
    if main_window.update_planet_btn: main_window.update_planet_btn.setEnabled(False)
    QtWidgets.QApplication.processEvents()

    try:
        radius_text = main_window.planet_radius_label.text().replace(" км", "").replace(",", "").replace(" ", "")
        radius_km = float(radius_text) if radius_text and radius_text != 'Ошибка' else 1.0
        radius_m = radius_km * 1000.0
        if radius_m < 1.0:
            raise ValueError("Радиус планеты слишком мал или не рассчитан.")

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
                'sea_level_pct': main_window.ws_sea_level.value(),
                'power': main_window.ws_power.value(),
                'warp_strength': main_window.ws_warp_strength.value(),
            }
        }

        update_planet_widget(main_window.planet_widget, world_settings)

    except Exception as e:
        QtWidgets.QMessageBox.critical(main_window, "Ошибка",
                                       f"Не удалось обновить 3D-планету: {e}\n{traceback.format_exc()}")
    finally:
        if main_window.update_planet_btn: main_window.update_planet_btn.setEnabled(True)