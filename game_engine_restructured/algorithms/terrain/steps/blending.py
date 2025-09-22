# Файл: game_engine_restructured/algorithms/terrain/steps/blending.py
from __future__ import annotations

import random
from typing import Any, Dict
import numpy as np

from game_engine_restructured.numerics.masking import create_mask
# Импортируем наши инструменты

from . import stamping  # Импортируем наш модуль со штампами
from .noise import _generate_noise_field
from .walkers import behaviors


def apply_walker_stampede(params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    ОРКЕСТРАТОР: Запускает "блуждающего агента".
    1. Находит стартовую точку.
    2. Вызывает "мозг" (behaviors) для генерации маршрута.
    3. Запускает "исполнителя", который идет по маршруту и ставит штампы.
    """
    print("    [Walker] -> Запуск блуждающего агента...")
    # --- 1. Подготовка ---
    height_grid = context["main_heightmap"]
    x_coords, z_coords = context["x_coords"], context["z_coords"]
    cell_size = context["cell_size"]
    seed = context["seed"]

    placement_params = params.get("placement", {})
    stamp_params = params.get("stamp", {})
    walker_params = params.get("walker", {})
    blend_mode = params.get("blend_mode", "add")

    # --- 2. Нахождение стартовой точки ---
    start_x, start_z = 0, 0
    placement_mode = placement_params.get("mode", "highest_point")
    # Используем border_margin для поиска старта, чтобы агент не родился сразу у края
    margin = walker_params.get("border_margin_tiles", 0) * cell_size

    if placement_mode == "highest_point":
        x_safe = (x_coords > np.min(x_coords) + margin) & (x_coords < np.max(x_coords) - margin)
        z_safe = (z_coords > np.min(z_coords) + margin) & (z_coords < np.max(z_coords) - margin)
        safe_zone_mask = x_safe & z_safe
        masked_heights = np.where(safe_zone_mask, height_grid, -np.inf)
        if np.any(np.isfinite(masked_heights)):
            idx = np.unravel_index(np.argmax(masked_heights), height_grid.shape)
            start_x, start_z = x_coords[idx], z_coords[idx]
            print(f"    [Walker] -> Агент рожден в точке (highest_point): ({start_x:.1f}, {start_z:.1f})")

    elif placement_mode == "corner":
        corner = placement_params.get("corner", "north_west")
        offset = walker_params.get("perimeter_offset_tiles", 0) * cell_size
        min_x_vis, max_x_vis = np.min(x_coords) + offset, np.max(x_coords) - offset
        min_z_vis, max_z_vis = np.min(z_coords) + offset, np.max(z_coords) - offset

        if corner == "north_west":
            start_x, start_z = min_x_vis, max_z_vis
        elif corner == "north_east":
            start_x, start_z = max_x_vis, max_z_vis
        # ... и так далее для других углов
        print(f"    [Walker] -> Агент рожден в углу ({corner}): ({start_x:.1f}, {start_z:.1f})")

    # --- 3. Генерация маршрута с помощью "мозга" ---
    path_mode = walker_params.get("path_mode", "random_walk")
    route = []

    step_dist = stamp_params.get("scale_tiles", 1000.0) * cell_size * walker_params.get("step_distance_ratio", 0.5)

    # Определяем границы для "штурмана"
    offset = walker_params.get("perimeter_offset_tiles", 0) * cell_size
    bounds = {
        'min_x': np.min(x_coords) + offset, 'max_x': np.max(x_coords) - offset,
        'min_z': np.min(z_coords) + offset, 'max_z': np.max(z_coords) - offset
    }
    # Для случайного блуждания используем более строгие границы
    random_walk_bounds = {
        'min_x': np.min(x_coords) + margin, 'max_x': np.max(x_coords) - margin,
        'min_z': np.min(z_coords) + margin, 'max_z': np.max(z_coords) - margin
    }

    if path_mode == "random_walk":
        print(f"    [Walker] -> Поведение: Случайное блуждание ({walker_params.get('num_steps', 4)} шагов).")
        route = behaviors.generate_random_walk_path(
            start_x, start_z, step_dist, walker_params.get('num_steps', 4), random_walk_bounds, seed
        )
    elif path_mode == "perimeter":
        print("    [Walker] -> Поведение: Движение по периметру.")
        route = behaviors.generate_perimeter_path(start_x, start_z, step_dist, bounds)

    # --- 4. ИСПОЛНЕНИЕ: Простой цикл идет по готовому маршруту ---
    print(f"    [Walker] -> Исполнение маршрута из {len(route)} шагов.")
    for i, (point_x, point_z) in enumerate(route):
        # Детерминированный случайный поворот для каждого шага
        step_seed = seed + i * 13 + int(point_x) * 47 + int(point_z) * 101
        random.seed(step_seed)
        angle = random.choice([0, 45, 90, 135, 180, 225, 270, 315])

        decal = stamping.generate_decal(
            x_coords, z_coords, cell_size, stamp_params,
            center_x=point_x, center_z=point_z, angle_deg=angle
        )

        # Смешиваем результат
        if blend_mode == "add":
            height_grid += decal
        elif blend_mode == "subtract":
            height_grid -= decal
        elif blend_mode == "multiply":
            height_grid *= (1.0 + decal)
        else:
            height_grid += decal

    # --- 5. Завершение ---
    context["main_heightmap"] = height_grid
    print("    [Walker] -> Агент завершил свой путь.")
    return context




def apply_masked_stamp(params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Нода, которая применяет текстурный штамп (тайловый или декаль) с использованием маски.
    """
    height_grid = context["main_heightmap"]
    x_coords, z_coords = context["x_coords"], context["z_coords"]
    cell_size = context["cell_size"]

    mask_params = params.get("mask", {})
    stamp_params = params.get("stamp", {})
    placement_params = params.get("placement", {})

    # --- ШАГ 1: Создаем маску ---
    h_min, h_max = np.min(height_grid), np.max(height_grid)
    normalized_height = (height_grid - h_min) / (h_max - h_min) if (h_max - h_min) > 1e-6 else np.zeros_like(
        height_grid)

    mask = create_mask(
        base_noise=normalized_height,
        threshold=mask_params.get("threshold", 0.5),
        invert=mask_params.get("invert", False),
        fade_range=mask_params.get("fade_range", 0.1)
    )

    # --- ШАГ 2: Генерируем смещение от штампа ---
    if stamp_params.get("tiling", True):
        # Старый режим: тайлинг по всей карте
        stamp_displacement = stamping.generate_displacement(x_coords, z_coords, cell_size, stamp_params)
    else:
        # Новый режим: одиночная "декаль"
        placement_mode = placement_params.get("mode", "center")
        center_x, center_z = 0, 0

        if placement_mode == "highest_point":
            # Ищем точку с максимальной высотой внутри маски
            masked_heights = np.where(mask > 0.1, height_grid, -np.inf)
            if np.any(np.isfinite(masked_heights)):
                idx = np.unravel_index(np.argmax(masked_heights), height_grid.shape)
                center_x, center_z = x_coords[idx], z_coords[idx]
                print(f"    [Blending] -> Найдена высшая точка для штампа: ({center_x:.1f}, {center_z:.1f})")

        angle = 0
        if placement_params.get("random_rotation", False):
            # Детерминированный случайный поворот на основе координат и seed'а
            # Используем простые числа для лучшего "перемешивания"
            angle_seed = int(center_x * 13 + center_z * 47 + context["seed"] * 101)
            np.random.seed(angle_seed)
            angle = np.random.choice([0, 45, 90, 135, 180, 225, 270, 315])

        stamp_displacement = stamping.generate_decal(
            x_coords, z_coords, cell_size, stamp_params,
            center_x=center_x, center_z=center_z, angle_deg=angle
        )

    # --- ШАГ 3: Смешиваем и применяем результат ---
    final_displacement = stamp_displacement * mask
    blend_mode = params.get("blend_mode", "add")

    if blend_mode == "add":
        height_grid += final_displacement
    elif blend_mode == "subtract":
        height_grid -= final_displacement
    elif blend_mode == "multiply":
        # Умножаем существующую высоту на (1 + смещение)
        # amp_m должен быть небольшим, например 0.2 для 20%
        height_grid *= (1.0 + final_displacement)
    else:
        height_grid += final_displacement

    context["main_heightmap"] = height_grid
    return context


# Добавьте эту функцию в конец файла blending.py
def apply_masked_noise(params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Нода, которая применяет слой процедурного шума к рельефу с использованием маски.
    """
    print("    [Blending] -> Применение процедурного шума по маске...")
    # --- ШАГ 1: Извлекаем данные и параметры ---
    height_grid = context["main_heightmap"]
    mask_params = params.get("mask")
    noise_params = params.get("noise")

    if not mask_params or not noise_params:
        print("!!! [Blending] CRITICAL ERROR: В ноде 'masked_noise' отсутствуют параметры 'mask' или 'noise'.")
        return context

    # --- ШАГ 2: Создаем маску (логика как в apply_masked_stamp) ---
    h_min, h_max = np.min(height_grid), np.max(height_grid)
    if (h_max - h_min) > 1e-6:
        normalized_height = (height_grid - h_min) / (h_max - h_min)
    else:
        normalized_height = np.zeros_like(height_grid)

    mask = create_mask(
        base_noise=normalized_height,
        threshold=mask_params.get("threshold", 0.5),
        invert=mask_params.get("invert", False),
        fade_range=mask_params.get("fade_range", 0.1)
    )

    # --- ШАГ 3: Генерируем шум, используя наш инструмент из noise.py ---
    # Передаем только параметры для шума и общий контекст
    noise_displacement = _generate_noise_field(noise_params, context)

    # --- ШАГ 4: Смешиваем и применяем результат ---
    blend_mode = params.get("blend_mode", "add")  # 'add', 'subtract', etc.
    final_displacement = noise_displacement * mask

    if blend_mode == "add":
        height_grid += final_displacement
    elif blend_mode == "subtract":
        height_grid -= final_displacement
    elif blend_mode == "multiply":
        height_grid *= (1.0 + final_displacement)
    else:
        print(f"!!! [Blending] WARNING: Неизвестный blend_mode '{blend_mode}'. Применяется 'add'.")
        height_grid += final_displacement

    context["main_heightmap"] = height_grid
    return context


def blend_layers(layer_a: np.ndarray, layer_b: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Линейно смешивает два слоя (A и B) используя маску.
    Формула: A * (1 - mask) + B * mask
    """
    # Убедимся, что маска находится в диапазоне [0, 1] для корректной интерполяции
    clipped_mask = np.clip(mask, 0.0, 1.0)
    return layer_a * (1.0 - clipped_mask) + layer_b * clipped_mask