# editor/logic/preview_logic.py
from __future__ import annotations
import logging
import traceback
import math
import numpy as np
from PySide6 import QtWidgets

from editor.graph.graph_runner import run_graph
from game_engine_restructured.world.planetary_grid import PlanetaryGrid
from generator_logic.terrain.global_sphere_noise import global_sphere_noise_wrapper


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from editor.core.main_window import MainWindow

logger = logging.getLogger(__name__)


def generate_preview(main_window: MainWindow):
    """
    Основная функция-оркестратор для генерации 3D-превью (ВЕРСИЯ 9.0).
    """
    if main_window.right_outliner: main_window.right_outliner.set_busy(True)
    try:
        target_node = main_window.graph.selected_nodes()[
            0] if main_window.graph and main_window.graph.selected_nodes() else main_window._last_selected_node
        if not target_node:
            logger.warning("Нет выбранной ноды для превью. Рендер отменен.")
            return

        logger.info(f"Рендеринг превью для ноды: '{target_node.name()}'")

        # 1. Получаем параметры из UI
        preview_res = int(main_window.preview_resolution_input.currentText().split('x')[0])
        region_res = int(main_window.region_resolution_input.currentText().split('x')[0])
        max_height_m = main_window.max_height_input.value()
        subdiv_text = main_window.subdivision_level_input.currentText()
        num_regions_str = "".join(filter(str.isdigit, subdiv_text))
        num_regions = int(num_regions_str) if num_regions_str else 1

        # 2. Вычисляем площадь гексагона и характерный размер планеты
        square_area = region_res * region_res
        hexagon_area = (3 * math.sqrt(3) / 8) * square_area
        total_pixel_area = hexagon_area * num_regions
        planet_characteristic_size = math.sqrt(total_pixel_area)

        # 3. Вычисляем частоту шума
        scale_value = main_window.ws_relative_scale.value()
        num_waves = 1.0 + (scale_value * 99.0)
        frequency = num_waves / planet_characteristic_size
        logger.debug(
            f"Частота шума: {frequency:.6f} (волн: {num_waves:.1f} / размер: {planet_characteristic_size:.0f} px)")

        # 4. Собираем параметры для глобального шума
        sphere_params = {
            'octaves': int(main_window.ws_octaves.value()),
            'gain': main_window.ws_gain.value(),
            'seed': main_window.ws_seed.value(),
            'frequency': frequency,
            'power': main_window.ws_power.value(),
            'warp_strength': main_window.ws_warp_strength.value(),
        }

        # 5. Генерируем основу ландшафта в ПОЛНОМ разрешении
        planet_grid = PlanetaryGrid(radius_m=1.0)
        coords_3d_full_res = planet_grid.get_coords_for_region(main_window.current_region_id, region_res)

        logger.info(
            f"Генерация базового ландшафта для региона {main_window.current_region_id} ({region_res}x{region_res})...")
        base_noise_full_res = global_sphere_noise_wrapper(
            context={'project': {'seed': sphere_params.get('seed', 0)}},
            sphere_params=sphere_params,
            coords_xyz=coords_3d_full_res
        )

        # 6. Уменьшаем до разрешения превью
        if preview_res < region_res:
            step = region_res // preview_res
            base_noise_preview = base_noise_full_res[::step, ::step]
        else:
            base_noise_preview = base_noise_full_res

        # --- НАЧАЛО ИСПРАВЛЕНИЯ: Возвращаем правильное создание сеток ---
        # 7. Создаем контекст для графа нод с ПОЛНОЦЕННЫМИ 2D-сетками
        x_range = np.arange(preview_res, dtype=np.float32)
        z_range = np.arange(preview_res, dtype=np.float32)
        x_coords, z_coords = np.meshgrid(x_range, z_range)
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        context = {
            "x_coords": x_coords,
            "z_coords": z_coords,
            "WORLD_SIZE_METERS": region_res * main_window.vertex_distance_input.value(),
            "max_height_m": max_height_m,
            "project": main_window.project_manager.current_project_data,
            "world_input_noise": base_noise_preview.astype(np.float32)
        }

        # 8. Запускаем граф
        final_map_01 = run_graph(target_node, context)

        sea_level = main_window.ws_sea_level.value()
        final_map_01 = np.where(final_map_01 < sea_level, sea_level, final_map_01)

        # 9. Масштабируем для отрисовки
        final_map_meters = final_map_01 * max_height_m

        if main_window.preview_widget:
            height_scale_factor = preview_res / region_res
            scaled_exaggeration = main_window.render_settings.height_exaggeration * height_scale_factor
            if abs(main_window.render_settings.height_exaggeration) > 1e-6:
                scaled_map_for_render = final_map_meters * scaled_exaggeration / main_window.render_settings.height_exaggeration
            else:
                scaled_map_for_render = final_map_meters
            main_window.preview_widget.update_mesh(scaled_map_for_render, 1.0)

    except Exception as e:
        logger.exception(f"Ошибка во время генерации: {e}")
        QtWidgets.QMessageBox.critical(main_window, "Ошибка генерации",
                                       f"Произошла ошибка: {e}\n\n{traceback.format_exc()}")
    finally:
        if main_window.right_outliner: main_window.right_outliner.set_busy(False)