# editor/logic/preview_logic.py
from __future__ import annotations
import logging
import traceback
import math
import numpy as np
from PySide6 import QtWidgets
from scipy.spatial.transform import Rotation as R
import cv2  # Импортируем OpenCV для изменения размера

from editor.graph.graph_runner import run_graph
from editor.utils.diag import diag_array
from generator_logic.terrain.global_sphere_noise import get_noise_for_region_preview
from editor.nodes.height.io.world_input_node import WorldInputNode

from typing import TYPE_CHECKING, Set, Tuple, Optional, Dict, Any

if TYPE_CHECKING:
    from editor.core.main_window import MainWindow
    from editor.nodes.base_node import GeneratorNode

logger = logging.getLogger(__name__)


def _get_target_node_and_mode(main_window: MainWindow) -> Tuple[Optional[GeneratorNode], bool]:
    """
    Находит целевую ноду для рендеринга и определяет, используется ли глобальный режим.
    """
    target_node = (main_window.graph.selected_nodes()[0]
                   if main_window.graph and main_window.graph.selected_nodes()
                   else main_window._last_selected_node)
    if not target_node:
        logger.warning("Нет выбранной ноды для превью. Рендер отменен.")
        return None, False

    is_global_mode = _has_world_input_ancestor(target_node)
    logger.info(f"Рендеринг превью для ноды: '{target_node.name()}'")
    if is_global_mode:
        logger.info(">>> РЕЖИМ: Глобальный (найден WorldInputNode). Используются сферические координаты.")
    else:
        logger.info(">>> РЕЖИМ: Локальный (WorldInputNode не найден). Используется плоская сетка.")

    return target_node, is_global_mode


def _prepare_context(main_window: MainWindow) -> Tuple[Dict[str, Any], int]:
    """
    Собирает базовый контекст и разрешение из UI.
    ВЕРСИЯ ИСПРАВЛЕНИЯ: Теперь всегда используется 'region_resolution' для вычислений.
    """
    context = main_window.project_manager.collect_ui_context(for_preview=True)

    try:
        # ИСПРАВЛЕНИЕ: Используем разрешение региона для всех вычислений
        resolution_str = main_window.region_resolution_input.currentText()
        resolution = int(resolution_str.split('x')[0])
    except (AttributeError, ValueError, IndexError):
        logger.warning("Не удалось прочитать разрешение региона из UI. Используется значение по умолчанию: 4096.")
        resolution = 4096

    vertex_distance = main_window.vertex_distance_input.value()
    world_side_m = resolution * vertex_distance

    context['WORLD_SIZE_METERS'] = world_side_m
    logger.debug(
        f"Собраны параметры для ВЫЧИСЛЕНИЙ: Resolution={resolution}px, VertexDistance={vertex_distance} м/пикс, WorldSide={world_side_m} м.")

    x_meters = np.linspace(-world_side_m / 2.0, world_side_m / 2.0, resolution, dtype=np.float32)
    z_meters = np.linspace(-world_side_m / 2.0, world_side_m / 2.0, resolution, dtype=np.float32)
    context['x_coords'], context['z_coords'] = np.meshgrid(x_meters, z_meters)

    return context, resolution


def _generate_world_input(main_window: MainWindow, resolution: int, sphere_params: dict) -> np.ndarray:
    """
    Генерирует `world_input_noise` для глобального режима.
    Возвращает 3D-сферический шум, спроецированный на плоскую карту.
    """
    target_center_vec = np.array(main_window.current_world_offset, dtype=np.float32)
    target_center_vec /= np.linalg.norm(target_center_vec)
    logger.debug(f"Целевой вектор региона (ID: {main_window.current_region_id}): {target_center_vec}")

    x_norm = np.linspace(-1.0, 1.0, resolution, dtype=np.float32)
    y_norm = np.linspace(-1.0, 1.0, resolution, dtype=np.float32)
    xv_norm, yv_norm = np.meshgrid(x_norm, y_norm)

    d_sq = xv_norm**2 + yv_norm**2
    zv_norm = np.sqrt(np.maximum(0.0, 1.0 - d_sq))

    up_vec = np.array([0.0, 0.0, 1.0])
    axis = np.cross(up_vec, target_center_vec)
    angle = np.arccos(np.dot(up_vec, target_center_vec))

    if np.linalg.norm(axis) > 1e-6:
        rotation = R.from_rotvec(axis / np.linalg.norm(axis) * angle)
    else:
        rotation = R.identity() if np.dot(up_vec, target_center_vec) > 0 else R.from_rotvec([1, 0, 0] * np.pi)

    points_to_rotate = np.stack([xv_norm, yv_norm, zv_norm], axis=-1)
    coords_for_noise = rotation.apply(points_to_rotate.reshape(-1, 3)).reshape(points_to_rotate.shape)
    base_noise = get_noise_for_region_preview(sphere_params=sphere_params, coords_xyz=coords_for_noise)

    logger.debug(f"Сгенерирован глобальный базовый шум. Shape: {base_noise.shape}, "
                 f"min: {base_noise.min():.4f}, max: {base_noise.max():.4f}, mean: {base_noise.mean():.4f}")

    return base_noise.astype(np.float32)


def _run_graph_and_update_ui(main_window: MainWindow, target_node: GeneratorNode, context: dict):
    """
    Запускает вычисление графа, уменьшает результат до разрешения превью и обновляет 3D-вид.
    """
    preview_max_height = context.get('max_height_m', 1000.0)
    vertex_distance = main_window.vertex_distance_input.value()

    if np.any(context["world_input_noise"]) and main_window.graph:
        base_noise = context["world_input_noise"]
        min_n, max_n, mean_n = np.min(base_noise), np.max(base_noise), np.mean(base_noise)
        stats = {
            'min_norm': min_n, 'max_norm': max_n, 'mean_norm': mean_n,
            'min_m': min_n * preview_max_height,
            'max_m': max_n * preview_max_height,
            'mean_m': mean_n * preview_max_height,
        }
        for node in main_window.graph.all_nodes():
            if isinstance(node, WorldInputNode):
                node.output_stats = stats
                break

    diag_array(context.get("world_input_noise"), name="world_input_noise (before run_graph)")
    final_map_01 = run_graph(target_node, context)
    logger.debug(f"Граф успешно выполнен. Финальная карта: Shape: {final_map_01.shape}, "
                 f"min: {final_map_01.min():.4f}, max: {final_map_01.max():.4f}, mean: {final_map_01.mean():.4f}")

    # --- ИСПРАВЛЕНИЕ: Логика даунскейлинга ---
    try:
        preview_res_str = main_window.preview_resolution_input.currentText()
        preview_resolution = int(preview_res_str.split('x')[0])
    except (AttributeError, ValueError, IndexError):
        logger.warning("Не удалось прочитать разрешение превью. Используется 1024.")
        preview_resolution = 1024

    display_map_01 = final_map_01
    if final_map_01.shape[0] > preview_resolution:
        logger.debug(f"Уменьшение карты с {final_map_01.shape[0]}px до {preview_resolution}px для превью.")
        display_map_01 = cv2.resize(final_map_01, (preview_resolution, preview_resolution), interpolation=cv2.INTER_LINEAR)

    final_map_meters = display_map_01 * preview_max_height
    if main_window.preview_widget:
        main_window.preview_widget.update_mesh(final_map_meters, vertex_distance)
        logger.debug(f"Меш в 3D превью обновлен. Vertex distance: {vertex_distance} м., "
                     f"Разрешение рендера: {display_map_01.shape[0]}x{display_map_01.shape[1]}px.")

    if main_window.node_inspector:
        main_window.node_inspector.refresh_from_selection()


def _has_world_input_ancestor(node: GeneratorNode, visited: Set[str] = None) -> bool:
    """
    Рекурсивно проверяет, есть ли в предках ноды WorldInputNode.
    """
    if visited is None:
        visited = set()
    if node.id in visited:
        return False
    visited.add(node.id)

    if isinstance(node, WorldInputNode):
        return True

    for port in node.inputs().values():
        for connected_port in port.connected_ports():
            ancestor_node = connected_port.node()
            if isinstance(ancestor_node, GeneratorNode):
                if _has_world_input_ancestor(ancestor_node, visited):
                    return True
    return False


def generate_preview(main_window: MainWindow):
    """
    Главная функция-оркестратор для генерации превью.
    """
    if main_window.right_outliner:
        main_window.right_outliner.set_busy(True)

    try:
        target_node, is_global_mode = _get_target_node_and_mode(main_window)
        if not target_node:
            return

        # ИСПРАВЛЕНИЕ: `resolution` здесь - это полное разрешение для вычислений
        context, resolution = _prepare_context(main_window)

        if is_global_mode:
            sphere_params = context.get('project', {}).get('global_noise', {})
            base_noise = _generate_world_input(main_window, resolution, sphere_params)
        else:
            base_noise = np.zeros_like(context['x_coords'], dtype=np.float32)
            logger.debug("Для локального режима создан пустой (нулевой) world_input_noise.")

        context["world_input_noise"] = base_noise
        _run_graph_and_update_ui(main_window, target_node, context)

    except Exception as e:
        logger.exception(f"Ошибка во время генерации превью: {e}")
        QtWidgets.QMessageBox.critical(main_window, "Ошибка генерации",
                                       f"Произошла ошибка: {e}\n\n{traceback.format_exc()}")
    finally:
        if main_window.right_outliner:
            main_window.right_outliner.set_busy(False)