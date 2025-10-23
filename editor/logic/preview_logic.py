# editor/logic/preview_logic.py
# ВЕРСИЯ 7.0: Генерация маски формы вынесена в отдельную ноду RegionShapeMaskNode.
# _generate_world_input теперь возвращает только базовый 3D-шум и маску из единиц.
from __future__ import annotations
import logging
import numpy as np
import json
from pathlib import Path
from numba import njit, prange # Оставляем для других возможных ядер Numba

from NodeGraphQt import BaseNode
from editor.graph.graph_runner import run_graph
from editor.nodes.height.io.world_input_node import WorldInputNode
from editor.nodes.base_node import GeneratorNode # Исправлен импорт
from generator_logic.terrain.global_sphere_noise import get_noise_for_region_preview
from typing import TYPE_CHECKING, Set, Tuple, Optional, Dict, Any, List

if TYPE_CHECKING:
    from editor.core.main_window import MainWindow

logger = logging.getLogger(__name__)
EPS = 1e-9 # Константа для избежания деления на ноль


# --- Функция _get_target_node_and_mode БЕЗ ИЗМЕНЕНИЙ ---
def _get_target_node_and_mode(main_window: MainWindow) -> tuple[None, bool] | tuple[BaseNode, bool]:
    target_node = (main_window.graph.selected_nodes()[0]
                   if main_window.graph and main_window.graph.selected_nodes()
                   else main_window._last_selected_node)
    if not target_node:
        return None, False
    is_global_mode = isinstance(target_node, WorldInputNode) or _has_world_input_ancestor(target_node)
    return target_node, is_global_mode

# --- Функция _prepare_context БЕЗ ИЗМЕНЕНИЙ ---
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
    # --- Важно: Центр координат в (0,0) для shape_masks ---
    context['x_coords'], context['z_coords'] = np.meshgrid(x_meters, z_meters)
    context['_original_resolution'] = region_resolution
    context['_original_vertex_distance'] = vertex_distance
    return context, calc_resolution

# --- Функция _generate_world_input ИЗМЕНЕНА ---
def _generate_world_input(main_window: "MainWindow", context: Dict[str, Any], sphere_params: dict, return_coords_only: bool = False) -> Tuple[np.ndarray, np.ndarray, Optional[List[float]]] | np.ndarray:
    """
    Генерирует:
    1. (output_height): Детальный 3D-шум для региона [0..1].
    2. (output_mask): Базовую маску из единиц.
    3. (north_vector_2d): Локальный 2D вектор направления на Северный полюс.
    ИЛИ
    Если return_coords_only=True, возвращает только массив 3D координат.
    """
    logger.info("Generating world input (3D noise and North vector)...")
    try:
        radius_text = main_window.planet_radius_label.text().replace(" км", "").replace(",", "").replace(" ", "")
        radius_m = float(radius_text) * 1000.0
        if radius_m < 1.0: raise ValueError("Radius is too small")
    except Exception:
        logger.warning("Could not parse radius from UI, falling back to default.")
        radius_m = 6371000.0

    x_m, z_m = context['x_coords'], context['z_coords']
    center_vec = np.array(main_window.current_world_offset, dtype=np.float32)
    if np.linalg.norm(center_vec) < EPS: center_vec = np.array([1.0, 0.0, 0.0]) # Fallback
    center_vec /= np.linalg.norm(center_vec) # Нормализуем на всякий случай

    # Определяем "вверх" для расчета базиса (Z-up)
    global_north_vec = np.array([0.0, 0.0, 1.0], dtype=np.float32)

    # Вычисляем локальные оси U и V (X и Z на плоскости превью)
    if np.abs(np.dot(center_vec, global_north_vec)) > 0.99:
         # Если мы на полюсе, выбираем другое направление для "вверх"
         alternative_up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
         tangent_u = np.cross(alternative_up, center_vec)
    else:
         tangent_u = np.cross(global_north_vec, center_vec) # U = North x Center

    if np.linalg.norm(tangent_u) < EPS:
         alternative_up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
         tangent_u = np.cross(alternative_up, center_vec)

    tangent_u /= np.linalg.norm(tangent_u)
    tangent_v = np.cross(center_vec, tangent_u) # V = Center x U
    tangent_v /= np.linalg.norm(tangent_v)

    # Генерация координат для шума
    points_in_plane = (center_vec[np.newaxis, np.newaxis, :]
                       + tangent_u[np.newaxis, np.newaxis, :] * (x_m / radius_m)[..., np.newaxis]
                       + tangent_v[np.newaxis, np.newaxis, :] * (z_m / radius_m)[..., np.newaxis])
    coords_for_noise = points_in_plane / np.linalg.norm(points_in_plane, axis=-1, keepdims=True)
    coords_for_noise = coords_for_noise.astype(np.float32)

    # Если нужен только массив координат
    if return_coords_only:
        return coords_for_noise

    # === ЧАСТЬ 1: ГЕНЕРАЦИЯ ДЕТАЛЬНОЙ ВЫСОТЫ (3D-ШУМ) ===
    base_noise = get_noise_for_region_preview(
        sphere_params=sphere_params,
        coords_xyz=coords_for_noise
    )
    # Нормализация амплитуды
    try:
        max_height_m = main_window.max_height_input.value()
        base_elevation_text = main_window.base_elevation_label.text().replace(" м", "").replace(",", "")
        base_elevation_m = float(base_elevation_text)
        if max_height_m > 1e-6 and base_elevation_m > 1e-6:
            amplitude_norm = base_elevation_m / max_height_m
        else: amplitude_norm = 0.33
    except Exception: amplitude_norm = 0.33

    output_height = (base_noise * amplitude_norm).astype(np.float32)
    logger.info("3D noise generation finished.")

    # === ЧАСТЬ 2: ГЕНЕРАЦИЯ БАЗОВОЙ МАСКИ ===
    output_mask = np.ones_like(output_height, dtype=np.float32)

    # === ЧАСТЬ 3: ВЫЧИСЛЕНИЕ ЛОКАЛЬНОГО ВЕКТОРА СЕВЕРА ===
    logger.info("Calculating local North vector...")
    north_tangent = global_north_vec - np.dot(global_north_vec, center_vec) * center_vec
    north_norm = np.linalg.norm(north_tangent)
    north_vector_2d = None # Инициализируем как None
    if north_norm > EPS:
        north_tangent /= north_norm
        # Проецируем нормализованный вектор севера на локальные оси U и V
        north_u = np.dot(north_tangent, tangent_u)
        north_v = np.dot(north_tangent, tangent_v)
        # --- ИЗМЕНЕНИЕ: Возвращаем список [float, float] ---
        north_vector_2d = [float(north_u), float(north_v)]
        # ------------------------------------
        logger.info(f"Local North vector calculated: [{north_u:.3f}, {north_v:.3f}] (U corresponds to screen X, V to screen Z/UP)")
    else:
        # Это происходит, если центр региона (center_vec) совпадает с полюсом (global_north_vec)
        logger.warning("Cannot determine North vector at the pole.")

    # Возвращаем height, mask и north_vector_2d (который может быть None)
    return output_height, output_mask, north_vector_2d


# --- Функция _has_world_input_ancestor БЕЗ ИЗМЕНЕНИЙ ---
def _has_world_input_ancestor(node: GeneratorNode, visited: Set[str] = None) -> bool:
    if visited is None: visited = set()
    if node.id in visited: return False
    visited.add(node.id)
    if isinstance(node, WorldInputNode): return True
    for port in node.inputs().values():
        for connected_port in port.connected_ports():
            upstream_node = connected_port.node()
            if not upstream_node: continue
            # Используем isinstance с проверкой на GeneratorNode для рекурсии
            if isinstance(upstream_node, GeneratorNode):
                 # Проверяем сам апстрим нод
                 if isinstance(upstream_node, WorldInputNode):
                     return True
                 # Рекурсивный вызов
                 if _has_world_input_ancestor(upstream_node, visited):
                     return True
    return False

def generate_node_graph_output(main_window: MainWindow, for_export: bool = False) -> Optional[Dict[str, Any]]:
    target_node, is_global_mode = _get_target_node_and_mode(main_window)
    if not target_node:
        logger.warning("Target node for generation not found.")
        return None

    context, calc_resolution = _prepare_context(main_window, for_export)
    original_resolution = context.get('_original_resolution', calc_resolution)

    # Инициализируем north_vector_2d значением None по умолчанию
    north_vector_2d = None

    if is_global_mode:
        continent_size_km = main_window.ws_continent_scale_km.value()
        frequency = 20000.0 / max(continent_size_km, 1.0)
        sphere_params = {
            'octaves': int(main_window.ws_octaves.value()),
            'gain': main_window.ws_gain.value(),
            'seed': main_window.ws_seed.value(),
            'frequency': frequency,
            'power': main_window.ws_power.value(),
        }
        # Получаем все три значения из _generate_world_input
        base_height, base_mask, north_vector_2d = _generate_world_input(main_window, context, sphere_params)
        logger.debug(f"North vector from _generate_world_input: {north_vector_2d}") # Добавим лог для проверки
    else:
        shape = context['x_coords'].shape
        base_height = np.zeros(shape, dtype=np.float32)
        base_mask = np.ones(shape, dtype=np.float32)

    context["world_input_height"] = base_height
    context["world_input_mask"] = base_mask

    # Обновляем статистику WorldInputNode, если это возможно
    if isinstance(target_node, WorldInputNode):
         # Код обновления статистики WorldInputNode (если он нужен)
         # Например: target_node.update_stats(...)
         pass # Пока просто заглушка

    # Запускаем граф
    final_map_01 = run_graph(target_node, context)
    if final_map_01 is None:
        logger.error("Graph execution returned None.")
        shape = context['x_coords'].shape
        final_map_01 = np.zeros(shape, dtype=np.float32)

    # Компенсация разрешения
    original_vertex_distance = context.get('_original_vertex_distance', 1.0)
    display_map_01 = final_map_01
    if calc_resolution != original_resolution and not for_export:
        compensation_factor = original_resolution / calc_resolution
        display_vertex_distance = original_vertex_distance * compensation_factor
        logger.info(
            f"Using low-res preview ({calc_resolution}x{calc_resolution}). Compensating vertex distance: {original_vertex_distance:.2f}м -> {display_vertex_distance:.2f}м")
    else:
        display_vertex_distance = original_vertex_distance

    # Получение вероятностей биомов (без изменений)
    biome_probabilities = {}
    if main_window.project_manager and main_window.project_manager.current_project_path and main_window.climate_enabled.isChecked():
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

    # !!! ВОТ ИСПРАВЛЕНИЕ !!!
    # Возвращаем РЕАЛЬНО вычисленный north_vector_2d, а не None
    return {
        "final_map_01": display_map_01,
        "max_height": context.get('max_height_m', 1.0),
        "vertex_distance": display_vertex_distance,
        "north_vector_2d": north_vector_2d, # <--- ИСПРАВЛЕНО
        "biome_probabilities": biome_probabilities
    }