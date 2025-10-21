# editor/logic/preview_logic.py
from __future__ import annotations
import logging
import numpy as np
import json
from pathlib import Path

# --- ДОБАВЛЯЕМ НОВЫЕ ИМПОРТЫ ---
from scipy.spatial import KDTree
from numba import njit, prange
# Убедись, что этот импорт правильный относительно структуры твоего проекта
from generator_logic.topology.icosa_grid import build_hexplanet
# --- КОНЕЦ НОВЫХ ИМПОРТОВ ---

from NodeGraphQt import BaseNode

from editor.graph.graph_runner import run_graph
from editor.nodes.height.io.world_input_node import WorldInputNode

# --- ИСПРАВЛЕННЫЙ ИМПОРТ (Строка 18) ---
# Теперь импортируем обе функции, так как get_noise_for_sphere_view используется ниже
from generator_logic.terrain.global_sphere_noise import get_noise_for_region_preview, get_noise_for_sphere_view
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---


from typing import TYPE_CHECKING, Set, Tuple, Optional, Dict, Any

if TYPE_CHECKING:
    from editor.core.main_window import MainWindow
    from editor.nodes.base_node import GeneratorNode

logger = logging.getLogger(__name__)

# --- КОНСТАНТА ДЛЯ ИЗБЕЖАНИЯ ДЕЛЕНИЯ НА НОЛЬ ---
EPS = 1e-9

# --- НОВАЯ ФУНКЦИЯ (оптимизированная с Numba) ---
@njit(cache=True, fastmath=True, parallel=True)
def _blend_hex_data_kernel(
    output_height: np.ndarray,
    output_mask: np.ndarray,
    coords_for_noise: np.ndarray, # Форма (H, W, 3)
    kdtree_data: np.ndarray,      # Данные KDTree (внутренний формат)
    kdtree_indices: np.ndarray,   # Индексы точек в KDTree
    hex_base_heights: np.ndarray  # Массив BaseHeight для каждого гекса
):
    """
    Numba-ядро для быстрого вычисления смешивания.
    """
    H, W, _ = coords_for_noise.shape
    num_centers = len(hex_base_heights)

    # KDTree.query не поддерживается в Numba напрямую,
    # поэтому мы сделаем простой поиск 2 ближайших вручную.
    # Для >10k гексов это будет медленнее KDTree, но Numba ускорит цикл.
    # Если производительность станет проблемой, можно будет поискать
    # Numba-совместимую реализацию KDTree или передавать предрассчитанные соседей.

    for r in prange(H):
        for c in range(W):
            point = coords_for_noise[r, c]

            # --- Ручной поиск 2 ближайших ---
            min_dist_sq_1 = np.inf
            min_dist_sq_2 = np.inf
            idx_1 = -1
            idx_2 = -1

            for i in range(num_centers):
                center = kdtree_data[kdtree_indices[i]] # Получаем координаты центра по индексу
                dx = point[0] - center[0]
                dy = point[1] - center[1]
                dz = point[2] - center[2]
                dist_sq = dx*dx + dy*dy + dz*dz

                if dist_sq < min_dist_sq_1:
                    min_dist_sq_2 = min_dist_sq_1
                    idx_2 = idx_1
                    min_dist_sq_1 = dist_sq
                    idx_1 = i
                elif dist_sq < min_dist_sq_2:
                    min_dist_sq_2 = dist_sq
                    idx_2 = i
            # --- Конец поиска ---

            if idx_1 == -1 or idx_2 == -1: # На случай ошибок
                output_height[r, c] = 0.0
                output_mask[r, c] = 1.0
                continue

            d1 = np.sqrt(min_dist_sq_1)
            d2 = np.sqrt(min_dist_sq_2)
            total_dist = d1 + d2

            if total_dist < EPS: # Если точка совпадает с центром
                 weight_A = 1.0
            else:
                 weight_A = d2 / total_dist

            height_A = hex_base_heights[idx_1]
            height_B = hex_base_heights[idx_2]

            blended_height = height_A * weight_A + height_B * (1.0 - weight_A)

            output_height[r, c] = blended_height
            output_mask[r, c] = weight_A

# --- КОНЕЦ НОВОЙ ФУНКЦИИ ---


# ... (функции _get_target_node_and_mode и _prepare_context остаются БЕЗ ИЗМЕНЕНИЙ) ...
def _get_target_node_and_mode(main_window: MainWindow) -> tuple[None, bool] | tuple[BaseNode, bool]:
    target_node = (main_window.graph.selected_nodes()[0]
                   if main_window.graph and main_window.graph.selected_nodes()
                   else main_window._last_selected_node)
    if not target_node:
        return None, False
    # --- ИСПРАВЛЕНИЕ: Проверяем предков только если это НЕ сам WorldInputNode ---
    is_global_mode = isinstance(target_node, WorldInputNode) or _has_world_input_ancestor(target_node)
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
    return target_node, is_global_mode

def _prepare_context(main_window: MainWindow, for_export: bool) -> Tuple[Dict[str, Any], int]:
    """
    Готовит контекст для генерации.
    Если for_export=True, всегда используется полное "Разрешение региона".
    Иначе, используется "Разрешение вычислений" для быстрого превью.
    """
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
    # --- ИСПРАВЛЕНИЕ: Размер мира теперь зависит от РАСЧЕТНОГО разрешения ---
    world_side_m = calc_resolution * vertex_distance # Было region_resolution
    context['WORLD_SIZE_METERS'] = world_side_m
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    # Генерируем координаты в метрах для РАСЧЕТНОГО разрешения
    x_meters = np.linspace(-world_side_m / 2.0, world_side_m / 2.0, calc_resolution, dtype=np.float32)
    z_meters = np.linspace(-world_side_m / 2.0, world_side_m / 2.0, calc_resolution, dtype=np.float32)
    context['x_coords'], context['z_coords'] = np.meshgrid(x_meters, z_meters)

    # --- ДОБАВЛЯЕМ: Сохраняем оригинальные параметры для масштабирования ---
    context['_original_resolution'] = region_resolution
    context['_original_vertex_distance'] = vertex_distance
    # --- КОНЕЦ ДОБАВЛЕНИЯ ---

    return context, calc_resolution


# --- ИЗМЕНЯЕМ ЭТУ ФУНКЦИЮ (ИСПРАВЛЕНЫ ОТСТУПЫ) ---
def _generate_world_input(main_window: "MainWindow", context: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
    """
    Генерирует базовый ландшафт и маску путем смешивания данных гексагональной сетки.
    Возвращает кортеж: (blended_height, weight_mask)
    """
    logger.info("Generating world input via hex blending...")

    # 1. Получаем 3D координаты для текущей квадратной сетки
    # (логика получения координат остается прежней)
    try:
        radius_text = main_window.planet_radius_label.text().replace(" км", "").replace(",", "").replace(" ", "")
        radius_m = float(radius_text) * 1000.0
        if radius_m < 1.0: raise ValueError("Radius is too small")
    except Exception:
        logger.warning("Could not parse radius from UI, falling back to default.")
        radius_m = 6371000.0

    x_m, z_m = context['x_coords'], context['z_coords']
    center_vec = np.array(main_window.current_world_offset, dtype=np.float32)
    if np.linalg.norm(center_vec) < EPS: center_vec = np.array([1.0, 0.0, 0.0]) # Защита от нулевого вектора
    center_vec /= np.linalg.norm(center_vec)
    up_vec = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    if np.abs(np.dot(center_vec, up_vec)) > 0.99:
        up_vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)

    tangent_u = np.cross(up_vec, center_vec) # Исправлен порядок для правой системы координат
    tangent_u /= np.linalg.norm(tangent_u)
    tangent_v = np.cross(center_vec, tangent_u)
    tangent_v /= np.linalg.norm(tangent_v) # Нормализуем второй тангенс

    # Проецируем плоские координаты на касательную плоскость и затем на сферу
    points_in_plane = (center_vec[np.newaxis, np.newaxis, :]
                       + tangent_u[np.newaxis, np.newaxis, :] * (x_m / radius_m)[..., np.newaxis]
                       + tangent_v[np.newaxis, np.newaxis, :] * (z_m / radius_m)[..., np.newaxis])
    coords_for_noise = points_in_plane / np.linalg.norm(points_in_plane, axis=-1, keepdims=True)
    coords_for_noise = coords_for_noise.astype(np.float32)

    # 2. Получаем данные глобальной гексагональной сетки
    planet_data = getattr(main_window.planet_widget, '_planet_data', None)
    if not planet_data or 'centers_xyz' not in planet_data:
        logger.error("Planet data (hex centers) not found. Returning flat terrain.")
        shape = context['x_coords'].shape
        return np.zeros(shape, dtype=np.float32), np.ones(shape, dtype=np.float32)

    hex_centers_xyz = planet_data['centers_xyz'].astype(np.float64) # Используем float64 для KDTree

    # 3. Создаем KDTree для быстрого поиска соседей
    try:
        kdtree = KDTree(hex_centers_xyz)
    except Exception as e:
        logger.error(f"Failed to build KDTree: {e}. Returning flat terrain.")
        shape = context['x_coords'].shape
        return np.zeros(shape, dtype=np.float32), np.ones(shape, dtype=np.float32)

    # --- НАЧАЛО БЛОКА С ИСПРАВЛЕННЫМ ОТСТУПОМ ---
    # (Этот код был внутри 'except', теперь он снаружи)

    # 4. Получаем или генерируем данные для гексов (WorldDataGrid)
    # --- НАЧАЛО ЗАМЕНЫ ЗАГЛУШКИ ---
    logger.info(f"Calculating BaseHeight for {len(hex_centers_xyz)} hex centers using global noise...")

    # --- ДОБАВЛЯЕМ ИНИЦИАЛИЗАЦИЮ ---
    num_hexes = len(hex_centers_xyz)
    hex_base_heights = np.zeros(num_hexes, dtype=np.float32)  # Инициализируем нулями
    logger.warning("Initializing hex_base_heights with zeros before calculation.")
    # --- КОНЕЦ ИНИЦИАЛИЗАЦИИ ---

    try:
        # Собираем параметры глобального шума из UI (как в planet_view_logic)
        sphere_params = {
            'octaves': int(main_window.ws_octaves.value()),
            'gain': main_window.ws_gain.value(),
            'seed': main_window.ws_seed.value(),
            # Частоту и power берем так же, как рассчитывали для planet_view_logic
            'frequency': 20000.0 / max(main_window.ws_continent_scale_km.value(), 1.0),
            'power': main_window.ws_power.value(),
        }
        # Вызываем функцию шума, передавая КООРДИНАТЫ ЦЕНТРОВ ГЕКСОВ
        noise_result = get_noise_for_sphere_view(
            sphere_params,
            hex_centers_xyz  # Передаем координаты центров
        )
        # Убедимся, что результат не None перед flatten
        if noise_result is None:
            raise ValueError("get_noise_for_sphere_view returned None")

        hex_base_heights_raw = noise_result.flatten()  # Убедимся, что результат плоский (N,)

        # Убедимся, что диапазон [0..1] и ПЕРЕЗАПИСЫВАЕМ инициализированный массив
        hex_base_heights = np.clip(hex_base_heights_raw, 0.0, 1.0).astype(np.float32)
        logger.info(
            f"Successfully calculated BaseHeight for hexes: min={hex_base_heights.min():.3f}, max={hex_base_heights.max():.3f}")

    except Exception as e:
        logger.error(f"Failed to calculate hex_base_heights using global noise: {e}", exc_info=True)
        # hex_base_heights уже инициализирован нулями, поэтому здесь ничего не делаем,
        # кроме логирования.
        logger.warning("Falling back to previously initialized zero BaseHeight for hexes.")


    # 5. Выполняем смешивание с помощью Numba-ядра
    H, W, _ = coords_for_noise.shape
    output_height = np.empty((H, W), dtype=np.float32)
    output_mask = np.empty((H, W), dtype=np.float32)

    logger.info("Starting Numba kernel for hex blending...")
    _blend_hex_data_kernel(  # <<< Ошибка возникала при попытке передать hex_base_heights сюда
        output_height,
        output_mask,
        coords_for_noise,
        kdtree.data,
        np.arange(len(kdtree.data), dtype=np.intp),
        hex_base_heights  # <--- ОШИБКА БЫЛА ЗДЕСЬ (строка 276 в твоем traceback)
    )
    logger.info("Numba kernel finished.")

    # --- ДОБАВЛЯЕМ ЛОГИРОВАНИЕ ПЕРЕД ВОЗВРАТОМ ---
    logger.debug(
        f"Returning from _generate_world_input. output_height shape: {output_height.shape}, output_mask shape: {output_mask.shape}")
    if output_height is None or output_mask is None:
        logger.error("!!! Critical error: output_height or output_mask is None before returning!")
        # Возвращаем заглушки, чтобы избежать TypeError
        shape = context['x_coords'].shape
        return np.zeros(shape, dtype=np.float32), np.ones(shape, dtype=np.float32)
    # --- КОНЕЦ ЛОГИРОВАНИЯ ---

    # 6. Возвращаем оба результата
    return output_height, output_mask

    # --- ДОБАВЛЯЕМ ЗАПАСНОЙ RETURN (на всякий случай) ---
    # Этот код теперь недостижим, так как return выше, но я его оставлю
    # на случай будущих правок, хотя его можно удалить.
    logger.error("!!! _generate_world_input reached unexpected end, returning fallback arrays!")
    shape = context['x_coords'].shape
    return np.zeros(shape, dtype=np.float32), np.ones(shape, dtype=np.float32)
    # --- КОНЕЦ ЗАПАСНОГО RETURN ---

    # --- КОНЕЦ БЛОКА С ИСПРАВЛЕННЫМ ОТСТУПОМ ---



def _has_world_input_ancestor(node: GeneratorNode, visited: Set[str] = None) -> bool:
    if visited is None: visited = set()
    if node.id in visited: return False
    visited.add(node.id)
    # --- ИСПРАВЛЕНИЕ: isinstance(node, WorldInputNode) ---
    if isinstance(node, WorldInputNode): return True
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
    for port in node.inputs().values():
        for connected_port in port.connected_ports():
            # --- ИСПРАВЛЕНИЕ: Проверяем тип перед рекурсивным вызовом ---
            upstream_node = connected_port.node()
            if isinstance(upstream_node, GeneratorNode):
                if _has_world_input_ancestor(upstream_node, visited):
                    return True
            # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
    return False


# --- ИЗМЕНЯЕМ ЭТУ ФУНКЦИЮ ---
def generate_node_graph_output(main_window: MainWindow, for_export: bool = False) -> Optional[Dict[str, Any]]:
    target_node, is_global_mode = _get_target_node_and_mode(main_window)
    if not target_node:
        logger.warning("Target node for generation not found.")
        return None

    context, calc_resolution = _prepare_context(main_window, for_export)

    # --- ИСПРАВЛЕНИЕ: Используем оригинальное разрешение из контекста ---
    original_resolution = context.get('_original_resolution', calc_resolution)
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    if is_global_mode:
        # Вызываем новую функцию, которая вернет два массива
        base_height, base_mask = _generate_world_input(main_window, context)
    else:
        # Если граф не зависит от WorldInput, создаем плоскую базу и маску=1
        logger.info("Generating flat input because graph does not depend on WorldInputNode.")
        shape = context['x_coords'].shape
        base_height = np.zeros(shape, dtype=np.float32)
        base_mask = np.ones(shape, dtype=np.float32)

    # Сохраняем оба результата в контекст для WorldInputNode
    context["world_input_height"] = base_height
    context["world_input_mask"] = base_mask
    # Старый ключ для обратной совместимости (если где-то еще используется)
    context["world_input_noise"] = base_height

    # Обновляем статистику для WorldInputNode, если он есть в графе
    if np.any(base_height) and main_window.graph:
        max_h = context.get('max_height_m', 1.0)
        # Рассчитываем статистику для базовой высоты
        stats = {
            'min_norm': np.min(base_height), 'max_norm': np.max(base_height), 'mean_norm': np.mean(base_height),
            'min_m': np.min(base_height) * max_h, 'max_m': np.max(base_height) * max_h,
            'mean_m': np.mean(base_height) * max_h
        }
        for node in main_window.graph.all_nodes():
            if isinstance(node, WorldInputNode):
                node.output_stats = stats
                break # Достаточно обновить первую найденную ноду

    # Запускаем вычисление графа, начиная с целевой ноды
    final_map_01 = run_graph(target_node, context)
    if final_map_01 is None:
         logger.error("Graph execution returned None.")
         # Возвращаем заглушку, чтобы избежать падения UI
         shape = context['x_coords'].shape
         final_map_01 = np.zeros(shape, dtype=np.float32)


    # --- ЛОГИКА МАСШТАБИРОВАНИЯ И VERTEX DISTANCE ОСТАЕТСЯ ПРЕЖНЕЙ ---
    original_vertex_distance = context.get('_original_vertex_distance', 1.0)

    # Если мы считали в пониженном разрешении, нужно смасштабировать результат
    # и компенсировать vertex_distance для корректного отображения в превью
    if calc_resolution != original_resolution and not for_export:
        try:
            import cv2 # Используем OpenCV для ресайза
            logger.info(f"Resizing output from {calc_resolution}x{calc_resolution} to {original_resolution}x{original_resolution}")
            final_map_01_resized = cv2.resize(
                final_map_01,
                (original_resolution, original_resolution),
                interpolation=cv2.INTER_LINEAR # Линейная интерполяция - хороший компромисс
            )
            display_map_01 = final_map_01_resized
            # Vertex distance не меняем, т.к. карта теперь в нужном размере
            display_vertex_distance = original_vertex_distance

        except ImportError:
            logger.warning("OpenCV not found. Cannot resize preview. Showing low-resolution result.")
            # Показываем результат как есть, но корректируем vertex_distance
            display_map_01 = final_map_01
            compensation_factor = original_resolution / calc_resolution
            display_vertex_distance = original_vertex_distance * compensation_factor
        except Exception as e:
            logger.error(f"Error during resizing: {e}. Showing low-resolution result.")
            display_map_01 = final_map_01
            compensation_factor = original_resolution / calc_resolution
            display_vertex_distance = original_vertex_distance * compensation_factor
    else:
        # Если разрешение совпадает или это экспорт, используем как есть
        display_map_01 = final_map_01
        display_vertex_distance = original_vertex_distance


    biome_probabilities = {}
    # ... (логика загрузки кэша климата остается без изменений) ...
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
                else: # --- ДОБАВЛЕНО: Обработка отсутствия данных для региона ---
                    logger.warning(f"Climate cache found, but no data for region ID {region_id_str}.")
                    biome_probabilities = {"error": "cache_miss"}
            else: # --- ДОБАВЛЕНО: Обработка отсутствия файла кэша ---
                 logger.warning("Climate cache file not found.")
                 biome_probabilities = {"error": "cache_miss"}

        except Exception as e:
            logger.error(f"Ошибка при чтении кэша климата для превью: {e}")
            biome_probabilities = {"error": str(e)} # Сообщаем об ошибке


    # Возвращаем данные для UI
    return {
        "final_map_01": display_map_01, # Карта для отображения (может быть смасштабирована)
        "max_height": context.get('max_height_m', 1000.0),
        "vertex_distance": display_vertex_distance, # Расстояние для отображения
        "north_vector_2d": None, # Пока не реализовано
        "biome_probabilities": biome_probabilities
    }
# --- КОНЕЦ ИЗМЕНЕНИЙ ФУНКЦИИ ---