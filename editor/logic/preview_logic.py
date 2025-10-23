# editor/logic/preview_logic.py
from __future__ import annotations
import logging
import numpy as np
import json
from pathlib import Path

# --- ИЗМЕНЕННЫЕ ИМПОРТЫ ---
from numba import njit, prange
# --- КОНЕЦ ИМПОРТОВ ---

from NodeGraphQt import BaseNode

from editor.graph.graph_runner import run_graph
from editor.nodes.height.io.world_input_node import WorldInputNode

# --- ИСПРАВЛЕНИЕ ОШИБКИ 'NameError' ---
from editor.nodes.base_node import GeneratorNode
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---

from generator_logic.terrain.global_sphere_noise import get_noise_for_region_preview

from typing import TYPE_CHECKING, Set, Tuple, Optional, Dict, Any

if TYPE_CHECKING:
    from editor.core.main_window import MainWindow
    # GeneratorNode уже импортирован выше

logger = logging.getLogger(__name__)

# --- КОНСТАНТА ДЛЯ ИЗБЕЖАНИЯ ДЕЛЕНИЯ НА НОЛЬ ---
EPS = 1e-9


# --- ИЗМЕНЕННАЯ ФУНКЦИЯ (ТЕСТ С КРУГОМ) ---
# @njit(cache=True, fastmath=True, parallel=True) # <- Numba выключен
def _generate_hex_mask_kernel(
        output_mask: np.ndarray,
        x_coords: np.ndarray,  # 2D массив X-координат (в метрах)
        z_coords: np.ndarray,  # 2D массив Z-координат (в метрах)
        hex_radius_m: float,  # Радиус гекса (от центра до угла)
        fade_start_norm: float,  # 0.98
        fade_end_norm: float  # 1.0
):
    """
    Генерирует 2D маску (ТЕСТ: КРУГ).
    """
    H, W = x_coords.shape
    fade_dist = fade_end_norm - fade_start_norm
    if fade_dist < 1e-6:
        fade_dist = 1e-6

        # --- ДОБАВЛЯЕМ ЗАЩИТУ ---
    if hex_radius_m < 1e-6:
        hex_radius_m = 1e-6  # Защита от деления на ноль
    # --- КОНЕЦ ---

    for r in range(H):  # <- Numba выключен
        for c in range(W):
            x = x_coords[r, c]
            z = z_coords[r, c]

            # --- Формула круга ---
            dist_sq = x * x + z * z
            norm_dist = np.sqrt(dist_sq) / hex_radius_m
            # --- КОНЕЦ ---

            # 2. Применяем плавное затухание
            if norm_dist < fade_start_norm:
                output_mask[r, c] = 1.0
            elif norm_dist > fade_end_norm:
                output_mask[r, c] = 0.0
            else:
                # Линейная интерполяция
                t = (norm_dist - fade_start_norm) / fade_dist
                output_mask[r, c] = 1.0 - t



# --- ЭТА ФУНКЦИЯ БЕЗ ИЗМЕНЕНИЙ ---
def _get_target_node_and_mode(main_window: MainWindow) -> tuple[None, bool] | tuple[BaseNode, bool]:
    target_node = (main_window.graph.selected_nodes()[0]
                   if main_window.graph and main_window.graph.selected_nodes()
                   else main_window._last_selected_node)
    if not target_node:
        return None, False
    is_global_mode = isinstance(target_node, WorldInputNode) or _has_world_input_ancestor(target_node)
    return target_node, is_global_mode


# --- ЭТА ФУНКЦИЯ БЕЗ ИЗМЕНЕНИЙ ---
def _prepare_context(main_window: MainWindow, for_export: bool) -> Tuple[Dict[str, Any], int]:
    context = main_window.project_manager.collect_ui_context(for_preview=False)
    try:
        region_res_str = main_window.region_resolution_input.currentText()
        region_resolution = int(region_res_str.split('x')[0])
    except (AttributeError, ValueError, IndexError):
        region_resolution = 1024
    if for_export:
        calc_resolution = region_resolution
        logger.info(f"Подготовка контекста для ЭКСПОРТА. Разрешение: {calc_resolution}x{calc_resolution}")
    else:
        try:
            calc_res_str = main_window.preview_calc_resolution_input.currentText()
            if "Полное" in calc_res_str:
                calc_resolution = region_resolution
            else:
                calc_resolution = int(calc_res_str.split('x')[0])
        except (AttributeError, ValueError, IndexError):
            calc_resolution = 1024
        logger.info(f"Подготовка контекста для ПРЕВЬЮ. Разрешение: {calc_resolution}x{calc_resolution}")
    vertex_distance = main_window.vertex_distance_input.value()
    world_side_m = calc_resolution * vertex_distance
    context['WORLD_SIZE_METERS'] = world_side_m
    x_meters = np.linspace(-world_side_m / 2.0, world_side_m / 2.0, calc_resolution, dtype=np.float32)
    z_meters = np.linspace(-world_side_m / 2.0, world_side_m / 2.0, calc_resolution, dtype=np.float32)
    context['x_coords'], context['z_coords'] = np.meshgrid(x_meters, z_meters)
    context['_original_resolution'] = region_resolution
    context['_original_vertex_distance'] = vertex_distance
    return context, calc_resolution


# --- ЭТА ФУНКЦИЯ БЕЗ ИЗМЕНЕНИЙ (кроме fade_start_norm) ---
def _generate_world_input(main_window: "MainWindow", context: Dict[str, Any], sphere_params: dict) -> Tuple[
    np.ndarray, np.ndarray]:
    """
    Генерирует:
    1. (output_height): Детальный 3D-шум для региона
    2. (output_mask): Геометрическую маску гексагона
    """

    # === ЧАСТЬ 1: ГЕНЕРАЦИЯ ДЕТАЛЬНОЙ ВЫСОТЫ (3D-ШУМ) ===
    logger.info("Generating world input (3D noise for height)...")

    # 1. Получаем 3D координаты
    try:
        radius_text = main_window.planet_radius_label.text().replace(" км", "").replace(",", "").replace(" ", "")
        radius_m = float(radius_text) * 1000.0
        if radius_m < 1.0: raise ValueError("Radius is too small")
    except Exception:
        logger.warning("Could not parse radius from UI, falling back to default.")
        radius_m = 6371000.0

    x_m, z_m = context['x_coords'], context['z_coords']
    center_vec = np.array(main_window.current_world_offset, dtype=np.float32)
    if np.linalg.norm(center_vec) < EPS: center_vec = np.array([1.0, 0.0, 0.0])
    center_vec /= np.linalg.norm(center_vec)
    up_vec = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    if np.abs(np.dot(center_vec, up_vec)) > 0.99:
        up_vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)

    tangent_u = np.cross(up_vec, center_vec)
    tangent_u /= np.linalg.norm(tangent_u)
    tangent_v = np.cross(center_vec, tangent_u)
    tangent_v /= np.linalg.norm(tangent_v)

    points_in_plane = (center_vec[np.newaxis, np.newaxis, :]
                       + tangent_u[np.newaxis, np.newaxis, :] * (x_m / radius_m)[..., np.newaxis]
                       + tangent_v[np.newaxis, np.newaxis, :] * (z_m / radius_m)[..., np.newaxis])
    coords_for_noise = points_in_plane / np.linalg.norm(points_in_plane, axis=-1, keepdims=True)
    coords_for_noise = coords_for_noise.astype(np.float32)

    # 2. Вызываем 3D-шум
    base_noise = get_noise_for_region_preview(
        sphere_params=sphere_params,
        coords_xyz=coords_for_noise
    )

    # 3. Нормализация высоты
    try:
        max_height_m = main_window.max_height_input.value()
        base_elevation_text = main_window.base_elevation_label.text().replace(" м", "").replace(",", "")
        base_elevation_m = float(base_elevation_text)
        if max_height_m > 1e-6 and base_elevation_m > 1e-6:
            amplitude_norm = base_elevation_m / max_height_m
        else:
            amplitude_norm = 0.33
            logger.warning(
                f"Could not calculate amplitude norm (base_elevation={base_elevation_m}, max_height={max_height_m}), falling back to {amplitude_norm}")
    except Exception as e:
        amplitude_norm = 0.33
        logger.warning(f"Could not calculate amplitude norm: {e}, falling back to {amplitude_norm}")

    output_height = (base_noise * amplitude_norm).astype(np.float32)
    logger.info("3D noise generation finished.")

    # === ЧАСТЬ 2: ГЕНЕРАЦИЯ ГЕОМЕТРИЧЕСКОЙ МАСКИ (ТЕСТ: КРУГ) ===
    logger.info("Generating geometric hex mask (TEST: CIRCLE)...")
    H, W = context['x_coords'].shape

    world_side_m = context.get('WORLD_SIZE_METERS', 4096.0)
    hex_radius_m = world_side_m / 2.0

    fade_start_norm = 0.98
    fade_end_norm = 1.0

    # --- ИЗМЕНЕНИЕ (ТЕСТ): Снова используем np.ones ---
    # Мы тестируем, падает ли ядро.
    output_mask = np.ones((H, W), dtype=np.float32)  # Было np.empty
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    _generate_hex_mask_kernel(
        output_mask,
        context['x_coords'],
        context['z_coords'],
        hex_radius_m,
        fade_start_norm,
        fade_end_norm
    )
    logger.info("Geometric mask finished.")

    # 6. Возвращаем (Детальный шум, Гекс-маска)
    return output_height, output_mask


# --- ЭТА ФУНКЦИЯ БЕЗ ИЗМЕНЕНИЙ ---
def _has_world_input_ancestor(node: GeneratorNode, visited: Set[str] = None) -> bool:
    """
    Рекурсивно проверяет, есть ли WorldInputNode среди "предков"
    (входящих нод) для указанной ноды.
    """
    if visited is None:
        visited = set()

    if node.id in visited:
        return False
    visited.add(node.id)

    # Проверяем саму текущую ноду (это сработает для рекурсивных вызовов)
    if isinstance(node, WorldInputNode):
        return True

    # Проверяем всех ее "родителей"
    for port in node.inputs().values():
        for connected_port in port.connected_ports():
            upstream_node = connected_port.node()

            if not upstream_node:
                continue

            # --- НАДЕЖНАЯ ПРОВЕРКА ---
            # Сначала напрямую проверяем, не WorldInputNode ли это.
            # Эта проверка надежна, т.к. WorldInputNode импортируется
            # прямо в этом файле.
            if isinstance(upstream_node, WorldInputNode):
                return True

            # Проверка 'isinstance(..., GeneratorNode)' может быть
            # ненадежной из-за циклических импортов.
            # Но мы все равно должны ее сделать для рекурсии.
            if isinstance(upstream_node, GeneratorNode):
                if _has_world_input_ancestor(upstream_node, visited):
                    return True
            # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    return False

# --- ЭТА ФУНКЦИЯ БЕЗ ИЗМЕНЕНИЙ ---
def generate_node_graph_output(main_window: MainWindow, for_export: bool = False) -> Optional[Dict[str, Any]]:
    target_node, is_global_mode = _get_target_node_and_mode(main_window)
    if not target_node:
        logger.warning("Target node for generation not found.")
        return None

    context, calc_resolution = _prepare_context(main_window, for_export)
    original_resolution = context.get('_original_resolution', calc_resolution)

    if is_global_mode:
        # Собираем параметры для 3D-шума
        continent_size_km = main_window.ws_continent_scale_km.value()
        frequency = 20000.0 / max(continent_size_km, 1.0)
        sphere_params = {
            'octaves': int(main_window.ws_octaves.value()),
            'gain': main_window.ws_gain.value(),
            'seed': main_window.ws_seed.value(),
            'frequency': frequency,
            'power': main_window.ws_power.value(),
        }
        # Передаем параметры в _generate_world_input
        base_height, base_mask = _generate_world_input(main_window, context, sphere_params)
    else:
        logger.info("Generating flat input because graph does not depend on WorldInputNode.")
        shape = context['x_coords'].shape
        base_height = np.zeros(shape, dtype=np.float32)
        base_mask = np.ones(shape, dtype=np.float32)

        # Сохраняем оба результата в контекст
    context["world_input_height"] = base_height
    context["world_input_mask"] = base_mask
    context["world_input_noise"] = base_height

    # Обновляем статистику ноды
    if np.any(base_height) and main_window.graph:
        max_h = context.get('max_height_m', 1.0)
        stats = {
            'min_norm': np.min(base_height), 'max_norm': np.max(base_height), 'mean_norm': np.mean(base_height),
            'min_m': np.min(base_height) * max_h, 'max_m': np.max(base_height) * max_h,
            'mean_m': np.mean(base_height) * max_h
        }
        for node in main_window.graph.all_nodes():
            if isinstance(node, WorldInputNode):
                node.output_stats = stats
                break

                # Запускаем вычисление графа
    final_map_01 = run_graph(target_node, context)
    if final_map_01 is None:
        logger.error("Graph execution returned None.")
        shape = context['x_coords'].shape
        final_map_01 = np.zeros(shape, dtype=np.float32)

    # --- ЛОГИКА КОМПЕНСАЦИИ (ОСТАЕТСЯ БЕЗ ИЗМЕНЕНИЙ) ---
    original_vertex_distance = context.get('_original_vertex_distance', 1.0)
    display_map_01 = final_map_01
    if calc_resolution != original_resolution and not for_export:
        compensation_factor = original_resolution / calc_resolution
        display_vertex_distance = original_vertex_distance * compensation_factor
        logger.info(
            f"Using low-res preview ({calc_resolution}x{calc_resolution}). Compensating vertex distance: {original_vertex_distance:.2f}м -> {display_vertex_distance:.2f}м")
    else:
        display_vertex_distance = original_vertex_distance

    # ... (логика biome_probabilities остается без изменений) ...
    biome_probabilities = {}
    if main_window.climate_enabled.isChecked():
        try:
            cache_path = Path(main_window.project_manager.current_project_path) / "cache" / "global_climate_data.json"
            if cache_path.exists():
                with open(cache_path, "r", encoding="utf-8") as f:
                    climate_data = json.load(f)
                region_id_str = str(main_window.current_region_id)
                region_climate = climate_data.get("region_data", {}).get(region_id_str)
                if region_climate:
                    biome_probabilities = region_climate.get("biome_probabilities", {})
                else:
                    logger.warning(f"Climate cache found, but no data for region ID {region_id_str}.")
                    biome_probabilities = {"error": "cache_miss"}
            else:
                logger.warning("Climate cache file not found.")
                biome_probabilities = {"error": "cache_miss"}
        except Exception as e:
            logger.error(f"Ошибка при чтении кэша климата для превью: {e}")
            biome_probabilities = {"error": str(e)}

    # Возвращаем данные для UI
    return {
        "final_map_01": display_map_01,
        "max_height": context.get('max_height_m', 1.0),
        "vertex_distance": display_vertex_distance,
        "north_vector_2d": None,
        "biome_probabilities": biome_probabilities
    }