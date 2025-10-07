# editor/logic/preview_logic.py
from __future__ import annotations
import logging
import traceback
import math  # <-- Убедитесь, что этот импорт есть
import numpy as np
from PySide6 import QtWidgets

from editor.graph.graph_runner import run_graph
from generator_logic.terrain.global_sphere_noise import get_noise_for_region_preview
from editor.nodes.height.io.world_input_node import WorldInputNode

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from editor.core.main_window import MainWindow

logger = logging.getLogger(__name__)


def generate_preview(main_window: MainWindow):
    """
    ФИНАЛЬНАЯ ВЕРСИЯ: Генерирует превью, корректно поворачивая
    плоскую сетку для соответствия выбранному региону на сфере.
    """
    if main_window.right_outliner:
        main_window.right_outliner.set_busy(True)

    try:
        target_node = (main_window.graph.selected_nodes()[0]
                       if main_window.graph and main_window.graph.selected_nodes()
                       else main_window._last_selected_node)
        if not target_node:
            logger.warning("Нет выбранной ноды для превью. Рендер отменен.")
            return

        logger.info(f"Рендеринг превью для ноды: '{target_node.name()}'")

        # --- НАЧАЛО БЛОКА ИЗМЕНЕНИЙ ---

        # Шаг 1: Собираем контекст из UI
        context = main_window.project_manager.collect_ui_context(for_preview=True)
        sphere_params = context.get('project', {}).get('global_noise', {})
        resolution = int(main_window.preview_resolution_input.currentText().split('x')[0])

        # Шаг 2: Создаем плоскую сетку с центром в (0, 0), как вы и предложили.
        half = 1.0
        x_flat = np.linspace(-half, half, resolution, dtype=np.float32)
        z_flat = np.linspace(-half, half, resolution, dtype=np.float32)
        x_coords, z_coords = np.meshgrid(x_flat, z_flat)

        d_sq = x_coords ** 2 + z_coords ** 2
        y_coords = np.sqrt(np.maximum(0.0, 1.0 - d_sq))
        y_coords[d_sq > 1.0] = 0

        # Шаг 3: Вычисляем матрицу вращения
        target_center_vec = np.array(main_window.current_world_offset, dtype=np.float32)
        target_center_vec /= np.linalg.norm(target_center_vec)

        up_vec = np.array([0.0, 0.0, 1.0])

        from scipy.spatial.transform import Rotation as R
        axis = np.cross(up_vec, target_center_vec)
        angle = np.arccos(np.dot(up_vec, target_center_vec))

        if np.linalg.norm(axis) > 1e-6:
            rotation = R.from_rotvec(axis / np.linalg.norm(axis) * angle)
        else:
            rotation = R.identity() if np.dot(up_vec, target_center_vec) > 0 else R.from_rotvec([1, 0, 0] * np.pi)

        # Шаг 4: Применяем вращение к каждой точке нашего "купола"
        points_to_rotate = np.stack([x_coords, z_coords, y_coords], axis=-1)
        coords_for_noise = rotation.apply(points_to_rotate.reshape(-1, 3)).reshape(points_to_rotate.shape)

        # Шаг 5: Передаем правильные данные в граф
        context['x_coords'] = x_coords
        context['z_coords'] = z_coords

        base_noise = get_noise_for_region_preview(
            sphere_params=sphere_params,
            coords_xyz=coords_for_noise
        )
        context["world_input_noise"] = base_noise.astype(np.float32)

        # --- КОНЕЦ БЛОКА ИЗМЕНЕНИЙ ---

        # ... (остальная часть функции остается без изменений) ...
        preview_max_height = context.get('max_height_m', 1000.0)
        if np.any(base_noise) and main_window.graph:
            min_n, max_n, mean_n = np.min(base_noise), np.max(base_noise), np.mean(base_noise)
            stats = {'min_norm': min_n, 'max_norm': max_n, 'mean_norm': mean_n, 'min_m': min_n * preview_max_height,
                     'max_m': max_n * preview_max_height, 'mean_m': mean_n * preview_max_height, }
            for node in main_window.graph.all_nodes():
                if isinstance(node, WorldInputNode):
                    node.output_stats = stats
                    break
        final_map_01 = run_graph(target_node, context)
        final_map_meters = final_map_01 * preview_max_height
        if main_window.preview_widget:
            vertex_distance = main_window.vertex_distance_input.value()
            main_window.preview_widget.update_mesh(final_map_meters, vertex_distance)
        if main_window.node_inspector:
            main_window.node_inspector.refresh_from_selection()

    except Exception as e:
        logger.exception(f"Ошибка во время генерации превью: {e}")
        QtWidgets.QMessageBox.critical(main_window, "Ошибка генерации",
                                       f"Произошла ошибка: {e}\n\n{traceback.format_exc()}")
    finally:
        if main_window.right_outliner:
            main_window.right_outliner.set_busy(False)