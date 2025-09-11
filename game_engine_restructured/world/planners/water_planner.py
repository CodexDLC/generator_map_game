# Файл: game_engine_restructured/world/planners/water_planner.py
from __future__ import annotations
from typing import TYPE_CHECKING
import numpy as np
import random
import heapq

from ...core import constants as const

if TYPE_CHECKING:
    from ...core.preset.model import Preset


def apply_sea_level(
        stitched_heights: np.ndarray,
        stitched_surface: np.ndarray,
        stitched_nav: np.ndarray,
        preset: Preset
):
    """
    Затапливает все участки ниже глобального уровня моря.
    """
    sea_level = preset.elevation.get("sea_level_m", 15.0)
    if sea_level is None: return

    print(f"  -> Applying sea level at {sea_level}m...")
    water_mask = stitched_heights <= sea_level
    rock_mask = stitched_surface == const.KIND_BASE_ROCK
    final_water_mask = water_mask & ~rock_mask

    stitched_surface[final_water_mask] = const.KIND_BASE_WATERBED
    stitched_nav[final_water_mask] = const.NAV_WATER


def generate_highland_lakes(
        stitched_heights: np.ndarray,
        stitched_surface: np.ndarray,
        stitched_nav: np.ndarray,
        stitched_humidity: np.ndarray | None,
        preset: Preset,
        seed: int
):
    """
    Находит и заполняет естественные впадины в рельефе выше уровня моря.
    """
    # ... (код этой функции остается без изменений)
    water_cfg = preset.water
    if not water_cfg or not water_cfg.get("enabled"):
        return

    print("  -> Searching for highland lakes...")
    rng = random.Random(seed)
    sea_level = preset.elevation.get("sea_level_m", 15.0)
    H, W = stitched_heights.shape

    visited = np.zeros_like(stitched_heights, dtype=bool)

    pq = []
    for x in range(W):
        for z in [0, H - 1]:
            if stitched_heights[z, x] > sea_level:
                heapq.heappush(pq, (stitched_heights[z, x], z, x))
                visited[z, x] = True
    for z in range(1, H - 1):
        for x in [0, W - 1]:
            if stitched_heights[z, x] > sea_level:
                heapq.heappush(pq, (stitched_heights[z, x], z, x))
                visited[z, x] = True

    while pq:
        h, z, x = heapq.heappop(pq)

        for dz, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nz, nx = z + dz, x + dx
            if not (0 <= nz < H and 0 <= nx < W) or visited[nz, nx]:
                continue

            visited[nz, nx] = True
            neighbor_h = stitched_heights[nz, nx]
            fill_h = max(h, neighbor_h)
            heapq.heappush(pq, (fill_h, nz, nx))

    from scipy.ndimage import label
    labeled_lakes, num_labels = label(~visited)

    for i in range(1, num_labels + 1):
        lake_mask = labeled_lakes == i

        if stitched_humidity is not None:
            avg_humidity = np.mean(stitched_humidity[lake_mask])
            base_chance = water_cfg.get("lake_chance_base", 0.1)
            hum_multiplier = water_cfg.get("lake_chance_humidity_multiplier", 3.0)
            final_chance = base_chance + (base_chance * avg_humidity * hum_multiplier)
            if rng.random() > final_chance:
                continue

        stitched_surface[lake_mask] = const.KIND_BASE_WATERBED
        stitched_nav[lake_mask] = const.NAV_WATER
        print(f"    -> Created a highland lake of size {np.sum(lake_mask)}")


# --- НАЧАЛО НОВОГО КОДА ---

def generate_rivers(
        stitched_heights: np.ndarray,
        stitched_surface: np.ndarray,
        stitched_nav: np.ndarray,
        preset: Preset,
        seed: int
):
    """
    Генерирует реки методом гидравлической эрозии ("капельный" метод).
    """
    water_cfg = preset.water
    if not water_cfg or not water_cfg.get("enabled"):
        return

    river_chance = water_cfg.get("river_chance_per_chunk", 0.5)
    rng = random.Random(seed)
    if rng.random() > river_chance:
        return

    print("  -> Generating rivers...")
    H, W = stitched_heights.shape
    flow_map = np.zeros_like(stitched_heights, dtype=np.float32)

    # 1. "Бросаем капли" со случайных высоких точек
    num_droplets = water_cfg.get("river_num_droplets", 4000)

    # --- НАЧАЛО ИЗМЕНЕНИЙ ---
    sea_level = preset.elevation.get("sea_level_m", 15.0)
    min_height_for_spring = sea_level + 70  # Реки могут начаться только на 20м выше уровня моря

    successful_droplets = 0
    attempts = 0
    while successful_droplets < num_droplets and attempts < num_droplets * 5:
        x, z = rng.randint(5, W - 6), rng.randint(5, H - 6)
        attempts += 1

        # Проверяем, что точка достаточно высокая
        if stitched_heights[z, x] < min_height_for_spring:
            continue  # Эта точка слишком низкая, ищем другую

        successful_droplets += 1
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---

        # "Капля" течет вниз, пока не достигнет моря или края карты
        for _ in range(2 * (W + H)):  # Ограничение длины пути
            flow_map[z, x] += 1

            # Ищем самого низкого соседа
            best_neighbor = None
            min_height = stitched_heights[z, x]

            for dz, dx in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
                nz, nx = z + dz, x + dx
                if 0 <= nz < H and 0 <= nx < W:
                    h = stitched_heights[nz, nx]
                    if h < min_height:
                        min_height = h
                        best_neighbor = (nz, nx)

            if best_neighbor:
                z, x = best_neighbor
                if stitched_nav[z, x] == const.NAV_WATER:  # Река впала в озеро/океан
                    break
            else:
                break  # Капля застряла во впадине

    # 2. Формируем маску рек
    flow_threshold = water_cfg.get("river_threshold", 0.01) * num_droplets
    river_mask = flow_map > flow_threshold

    if not np.any(river_mask):
        print("    -> No significant rivers formed.")
        return
    # --- НАЧАЛО ИЗМЕНЕНИЙ: Расширение русла реки ---
    from scipy.ndimage import binary_dilation

    # Реки будут от 1 до 3 пикселей в ширину
    # Чем больше поток, тем шире река
    wide_river_mask = flow_map > (flow_threshold * 5)
    widest_river_mask = flow_map > (flow_threshold * 10)

    # Расширяем (дилатация) маску, чтобы сделать реку толще
    river_mask = binary_dilation(river_mask, iterations=1)
    river_mask |= binary_dilation(wide_river_mask, iterations=2)
    river_mask |= binary_dilation(widest_river_mask, iterations=3)
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    # 3. Применяем простое терраформирование и "раскраску"
    excavate_depth = water_cfg.get("river_excavate_depth_m", -1.0)

    stitched_heights[river_mask] += excavate_depth
    stitched_surface[river_mask] = const.KIND_BASE_WATERBED
    stitched_nav[river_mask] = const.NAV_WATER

    print(f"    -> Carved river network with {np.sum(river_mask)} tiles.")

# --- КОНЕЦ НОВОГО КОДА ---