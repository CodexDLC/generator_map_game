# game_engine_restructured/algorithms/water/water_planner.py
from __future__ import annotations
from typing import TYPE_CHECKING
import numpy as np
import random
import math
from opensimplex import OpenSimplex

from ...core import constants as const

if TYPE_CHECKING:
    from ...core.preset.model import Preset
    from ...core.types import GenResult


# (Код функции _generate_lake_mask остается без изменений)
def _generate_lake_mask(size: int, cx: int, cz: int, radius: int, seed: int) -> np.ndarray:
    mask = np.zeros((size, size), dtype=bool)
    noise_gen = OpenSimplex(seed)
    offset_x = random.randint(-radius // 2, radius // 2)
    offset_y = random.randint(-radius // 2, radius // 2)
    center_x, center_z = size // 2 + offset_x, size // 2 + offset_y
    for z in range(size):
        for x in range(size):
            dx, dz = x - center_x, z - center_z
            dist = math.sqrt(dx * dx + dz * dz)
            noise_val = noise_gen.noise2(x * 0.05, z * 0.05)
            dist_warped = dist + noise_val * (radius * 0.3)
            if dist_warped < radius:
                mask[z, x] = True
    return mask


def generate_lakes(result: GenResult, preset: Preset):
    # (Код этой функции остается без изменений)
    water_cfg = preset.water
    if not water_cfg or not water_cfg.get("enabled"): return
    rng = random.Random(result.stage_seeds.get("water", result.seed))
    humidity_grid = np.array(result.layers.get("humidity", []))
    if humidity_grid.size == 0:
        noise_gen = OpenSimplex(result.stage_seeds["humidity"])
        wx, wz = result.cx * result.size, result.cz * result.size
        avg_humidity = (noise_gen.noise2(wx * 0.0001, wz * 0.0001) + 1.0) / 2.0
    else:
        avg_humidity = np.mean(humidity_grid)
    base_chance = water_cfg.get("lake_chance_base", 0.02)
    chance_multiplier = water_cfg.get("lake_chance_humidity_multiplier", 3.0)
    final_chance = base_chance + (avg_humidity - 0.5) * chance_multiplier
    if rng.random() > final_chance:
        print(f"  -> No lakes for chunk ({result.cx}, {result.cz}). Chance: {final_chance:.2f}")
        return
    print(f"  -> Generating lake for chunk ({result.cx}, {result.cz}). Chance: {final_chance:.2f}")
    min_radius, max_radius = water_cfg.get("lake_min_radius", 15), water_cfg.get("lake_max_radius", 50)
    radius = rng.randint(min_radius, max_radius)
    lake_mask = _generate_lake_mask(result.size, result.cx, result.cz, radius, rng.randint(0, 0xFFFFFFFF))
    if not np.any(lake_mask): return
    height_grid = np.array(result.layers["height_q"]["grid"], dtype=np.float32)
    shore_heights = height_grid[lake_mask]
    if shore_heights.size == 0: return
    avg_shore_height = np.mean(shore_heights)
    flatten_depth = water_cfg.get("lake_flatten_depth_m", -5.0)
    target_height = avg_shore_height + flatten_depth
    height_grid[lake_mask] = target_height
    result.layers["height_q"]["grid"] = height_grid.tolist()
    surface_grid, nav_grid = result.layers["surface"], result.layers["navigation"]
    for z, x in np.argwhere(lake_mask):
        surface_grid[z][x] = const.KIND_BASE_SAND
        nav_grid[z][x] = const.NAV_WATER
        for dz in range(-2, 3):
            for dx in range(-2, 3):
                if dz == 0 and dx == 0: continue
                nx, nz = x + dx, z + dz
                if 0 <= nx < result.size and 0 <= nz < result.size and not lake_mask[nz, nx]:
                    if nav_grid[nz][nx] != const.NAV_WATER:
                        surface_grid[nz][nx] = const.KIND_BASE_SAND


# --- НОВАЯ ФУНКЦИЯ ДЛЯ РЕК ---
def generate_rivers(result: GenResult, preset: Preset):
    """
    Генерирует реки методом гидравлической эрозии с витлянием.
    """
    water_cfg = preset.water
    if not water_cfg or not water_cfg.get("enabled"):
        return

    rng = random.Random(result.stage_seeds.get("water", result.seed) ^ 0xDEADBEEF)
    if rng.random() > water_cfg.get("river_chance_per_chunk", 0.5):
        print(f"  -> No rivers for chunk ({result.cx}, {result.cz}).")
        return

    print(f"  -> Generating rivers for chunk ({result.cx}, {result.cz})...")

    size = result.size
    height_grid = np.array(result.layers["height_q"]["grid"], dtype=np.float32)
    flow_map = np.zeros_like(height_grid)

    # --- Настройка Curl Noise ---
    curl_scale = water_cfg.get("river_curl_noise_scale", 200.0)
    curl_strength = water_cfg.get("river_curl_noise_strength", 0.3)
    curl_freq = 1.0 / curl_scale if curl_scale > 0 else 0
    noise_gen_x = OpenSimplex(rng.randint(0, 0xFFFFFFFF))
    noise_gen_z = OpenSimplex(rng.randint(0, 0xFFFFFFFF))

    # --- Симуляция "капель дождя" ---
    num_droplets = water_cfg.get("river_num_droplets", 4000)
    for _ in range(num_droplets):
        px, pz = rng.randint(0, size - 1), rng.randint(0, size - 1)

        for _ in range(size * 2):  # Максимальная длина пути
            # --- Вектор гравитации (куда течь вниз) ---
            best_dx, best_dz = 0, 0
            min_h = height_grid[pz, px]
            for dz in range(-1, 2):
                for dx in range(-1, 2):
                    if dx == 0 and dz == 0: continue
                    nx, nz = px + dx, pz + dz
                    if 0 <= nx < size and 0 <= nz < size:
                        if height_grid[nz, nx] < min_h:
                            min_h = height_grid[nz, nx]
                            best_dx, best_dz = dx, dz

            # --- Вектор вихря (боковое смещение) ---
            wx, wz = (result.cx * size) + px, (result.cz * size) + pz
            # Вычисляем производные шума для curl
            h = 0.01
            nx1, nx2 = noise_gen_x.noise2(wx * curl_freq, (wz - h) * curl_freq), noise_gen_x.noise2(wx * curl_freq, (
                        wz + h) * curl_freq)
            nz1, nz2 = noise_gen_z.noise2((wx - h) * curl_freq, wz * curl_freq), noise_gen_z.noise2(
                (wx + h) * curl_freq, wz * curl_freq)

            curl_x = (nx2 - nx1) / (2 * h)
            curl_z = (nz2 - nz1) / (2 * h)

            # --- Суммируем векторы ---
            final_dx = best_dx * (1.0 - curl_strength) + curl_z * curl_strength
            final_dz = best_dz * (1.0 - curl_strength) - curl_x * curl_strength

            # Нормализуем и находим следующую клетку
            length = math.sqrt(final_dx ** 2 + final_dz ** 2)
            if length < 0.1: break  # Остановились

            next_px = int(round(px + final_dx / length))
            next_pz = int(round(pz + final_dz / length))

            if not (0 <= next_px < size and 0 <= next_pz < size) or (next_px == px and next_pz == pz):
                break  # Ушли за край или остановились

            px, pz = next_px, next_pz
            flow_map[pz, px] += 1.0

    # --- Создание русел ---
    river_threshold = water_cfg.get("river_threshold", 0.01) * num_droplets
    river_mask = flow_map > river_threshold
    if not np.any(river_mask): return

    depth = water_cfg.get("river_excavate_depth_m", -3.0)
    height_grid[river_mask] += depth  # "Копаем" русло

    result.layers["height_q"]["grid"] = height_grid.tolist()
    surface_grid = result.layers["surface"]
    nav_grid = result.layers["navigation"]

    for z, x in np.argwhere(river_mask):
        surface_grid[z][x] = const.KIND_BASE_SAND
        nav_grid[z][x] = const.NAV_WATER
        # Песчаные берега
        for dz in range(-1, 2):
            for dx in range(-1, 2):
                nx, nz = x + dx, z + dz
                if 0 <= nx < size and 0 <= nz < size and not river_mask[nz, nx]:
                    if nav_grid[nz][nx] != const.NAV_WATER:
                        surface_grid[nz][nx] = const.KIND_BASE_SAND