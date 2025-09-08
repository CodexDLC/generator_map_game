# Файл: game_engine/algorithms/terrain/terrain.py
from __future__ import annotations
from typing import Any, List, Tuple
import math

import numpy as np
from opensimplex import OpenSimplex

from .features import fbm2d
from .slope import compute_slope_mask
from ...core.constants import (
    KIND_ROAD,
    KIND_SAND,
    KIND_GROUND,
    NAV_PASSABLE,
    KIND_SLOPE,
    NAV_WATER, SURFACE_KIND_TO_ID,
)


def _apply_shaping_curve(grid: List[List[float]], power: float):
    if power == 1.0:
        return
    for z in range(len(grid)):
        for x in range(len(grid[0])):
            grid[z][x] = math.pow(grid[z][x], power)


def _smooth_grid(grid: List[List[float]], passes: int):
    if passes <= 0:
        return grid
    h, w = len(grid), len(grid[0])
    temp_grid = [row[:] for row in grid]
    for _ in range(passes):
        new_grid = [row[:] for row in temp_grid]
        for z in range(h):
            for x in range(w):
                if x == 0 or x == w - 1 or z == 0 or z == h - 1:
                    continue
                total, count = 0.0, 0
                for dz in range(-1, 2):
                    for dx in range(-1, 2):
                        total += temp_grid[z + dz][x + dx]
                        count += 1
                new_grid[z][x] = total / count
        temp_grid = new_grid
    return temp_grid


def _quantize_heights(grid: List[List[float]], step: float):
    if step <= 0:
        return
    for z in range(len(grid)):
        for x in range(len(grid[0])):
            t = int(round(grid[z][x] / step))
            grid[z][x] = float(t) * step


def _crop_grid(
    grid: List[List[float]], target_size: int, margin: int
) -> List[List[float]]:
    cropped = [[0.0] * target_size for _ in range(target_size)]
    for z in range(target_size):
        for x in range(target_size):
            cropped[z][x] = grid[z + margin][x + margin]
    return cropped


# --- НАЧАЛО ИЗМЕНЕНИЙ: Полностью переписанная функция ---
def generate_elevation(
    seed: int, cx: int, cz: int, size: int, preset: Any
) -> Tuple[List[List[float]], List[List[float]]]:
    """
    Генерирует карту высот с новой системой "терраформинга".
    """
    noise_gen = OpenSimplex(seed)
    cfg = getattr(preset, "elevation", None) or {}
    terraform_rules = cfg.get("terraform", [])

    margin = 2
    working_size = size + margin * 2
    base_wx = cx * size - margin
    base_wz = cz * size - margin

    grid = [[0.0 for _ in range(working_size)] for _ in range(working_size)]
    scale_tiles = float(cfg.get("noise_scale_tiles", 32.0))
    freq = 1.0 / scale_tiles

    # --- ЭТАП 1: Создаем "сырой" шум (0.0 - 1.0) ---
    for z in range(working_size):
        for x in range(working_size):
            wx, wz = base_wx + x, base_wz + z
            noise_val = fbm2d(
                noise_gen, float(wx), float(wz), freq, octaves=4, gain=0.5
            )
            grid[z][x] = max(0.0, min(1.0, noise_val))

    # --- ЭТАП 2: Применяем правила терраформинга ---
    if terraform_rules:
        for z in range(working_size):
            for x in range(working_size):
                noise_val = grid[z][x]

                for rule in terraform_rules:
                    # Проверяем, попадает ли шум в диапазон правила
                    if rule["noise_from"] <= noise_val < rule["noise_to"]:
                        # Нормализуем шум внутри его старого диапазона (от 0 до 1)
                        source_range = rule["noise_to"] - rule["noise_from"]
                        if source_range <= 0:
                            continue
                        t = (noise_val - rule["noise_from"]) / source_range

                        # "Растягиваем" его до нового диапазона
                        target_range = rule["remap_to_to"] - rule["remap_to_from"]
                        noise_val = rule["remap_to_from"] + t * target_range

                        # Применили правило, выходим из цикла по правилам
                        break

                grid[z][x] = noise_val


    _apply_shaping_curve(grid, float(cfg.get("shaping_power", 1.0)))

    max_h = float(cfg.get("max_height_m", 60.0))
    if max_h > 0:
        for z in range(working_size):
            for x in range(working_size):
                grid[z][x] *= max_h

    smoothed_grid = _smooth_grid(grid, int(cfg.get("smoothing_passes", 0)))
    _quantize_heights(smoothed_grid, float(cfg.get("quantization_step_m", 0.0)))

    final_grid = _crop_grid(smoothed_grid, size, margin)
    return final_grid, smoothed_grid


def classify_terrain(
    elevation_grid: List[List[float]],
    surface_grid: List[List[str]],
    nav_grid: List[List[str]],
    preset: Any,
) -> None:
    size = len(surface_grid)
    cfg = getattr(preset, "elevation", None) or {}
    sea_level = float(cfg.get("sea_level_m", 9.0))
    for z in range(size):
        for x in range(size):
            elev = elevation_grid[z][x]
            if elev < sea_level:
                surface_grid[z][x] = KIND_SAND
                nav_grid[z][x] = NAV_WATER
            else:
                surface_grid[z][x] = KIND_GROUND
                nav_grid[z][x] = NAV_PASSABLE


def apply_slope_obstacles(height_grid_with_margin, surface_grid, preset, cx: int, cz: int) -> None:
    """
    Красим клетки 'slope' там, где угол >= порога.
    height_grid_with_margin: список списков высот (метры), как правило (size+2)x(size+2)
    surface_grid: список списков int (surface-kind ids), размер size x size
    """
    s_cfg = dict(getattr(preset, "slope_obstacles", {}) or {})
    if not s_cfg.get("enabled", False):
        return

    angle = float(s_cfg.get("angle_threshold_deg", 45.0))
    band = int(s_cfg.get("band_cells", 0))
    cell = float(getattr(preset, "cell_size", 1.0))

    H = np.array(height_grid_with_margin, dtype=np.float32)
    full_mask = compute_slope_mask(H, cell, angle, band)

    size = len(surface_grid)
    # Учтём маргинальный бордюр: чаще всего H.shape = (size+2, size+2)
    if full_mask.shape[0] == size + 2 and full_mask.shape[1] == size + 2:
        mask = full_mask[1:-1, 1:-1]
    else:
        # если размеров ровно size x size — берём как есть
        mask = full_mask[:size, :size]

    slope_id = SURFACE_KIND_TO_ID.get("slope", SURFACE_KIND_TO_ID["obstacle"])
    ys, xs = np.where(mask)
    for y, x in zip(ys.tolist(), xs.tolist()):
        surface_grid[y][x] = slope_id


def apply_beaches(
    elevation_grid: List[List[float]],
    surface_grid: List[List[str]],
    nav_grid: List[List[str]],
    preset: Any,
) -> None:
    size = len(surface_grid)
    if size == 0:
        return
    elev_cfg = getattr(preset, "elevation", {}) or {}
    step = float(elev_cfg.get("quantization_step_m", 1.0))
    height_threshold = step * 0.5
    new_surface_grid = [row[:] for row in surface_grid]
    for z in range(size):
        for x in range(size):
            if surface_grid[z][x] != KIND_GROUND:
                continue
            is_beach = False
            for dx, dz in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, nz = x + dx, z + dz
                if 0 <= nx < size and 0 <= nz < size and nav_grid[nz][nx] == NAV_WATER:
                    h_ground = elevation_grid[z][x]
                    h_water = elevation_grid[nz][nx]
                    if abs(h_ground - h_water) < height_threshold:
                        is_beach = True
                        break
            if is_beach:
                new_surface_grid[z][x] = KIND_SAND
    for z in range(size):
        surface_grid[z][x] = new_surface_grid[z][x]


def generate_scatter_mask(
    seed: int, cx: int, cz: int, size: int, surface_grid: List[List[str]], preset: Any
) -> List[List[bool]]:
    cfg = getattr(preset, "scatter", {})
    obstacle_mask = [[False for _ in range(size)] for _ in range(size)]
    if not cfg.get("enabled", False):
        return obstacle_mask
    groups_cfg = cfg.get("groups", {})
    details_cfg = cfg.get("details", {})
    group_scale = float(groups_cfg.get("noise_scale_tiles", 64.0))
    group_threshold = float(groups_cfg.get("threshold", 0.5))
    group_freq = 1.0 / group_scale
    detail_scale = float(details_cfg.get("noise_scale_tiles", 8.0))
    detail_threshold = float(details_cfg.get("threshold", 0.6))
    detail_freq = 1.0 / detail_scale
    group_noise_gen = OpenSimplex((seed ^ 0xABCDEFAB) & 0x7FFFFFFF)
    detail_noise_gen = OpenSimplex((seed ^ 0x12345678) & 0x7FFFFFFF)
    for z in range(size):
        for x in range(size):
            if surface_grid[z][x] in (KIND_GROUND, KIND_SAND):
                wx, wz = cx * size + x, cz * size + z
                group_val = (
                    group_noise_gen.noise2(wx * group_freq, wz * group_freq) + 1.0
                ) / 2.0
                if group_val > group_threshold:
                    detail_val = (
                        detail_noise_gen.noise2(wx * detail_freq, wz * detail_freq)
                        + 1.0
                    ) / 2.0
                    if detail_val > detail_threshold:
                        obstacle_mask[z][x] = True
    return obstacle_mask
