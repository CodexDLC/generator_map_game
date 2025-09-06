# game_engine/algorithms/terrain/terrain.py
from __future__ import annotations
from typing import Any, List, Tuple
import math

from opensimplex import OpenSimplex

from .features import fbm2d
from ...core.constants import KIND_ROAD, KIND_SAND, NAV_OBSTACLE, KIND_GROUND, NAV_PASSABLE, KIND_SLOPE, NAV_WATER


def _apply_shaping_curve(grid: List[List[float]], power: float):
    if power == 1.0: return
    for z in range(len(grid)):
        for x in range(len(grid[0])):
            grid[z][x] = math.pow(grid[z][x], power)


def _smooth_grid(grid: List[List[float]], passes: int):
    if passes <= 0: return grid
    h, w = len(grid), len(grid[0])
    temp_grid = [row[:] for row in grid]
    for _ in range(passes):
        new_grid = [row[:] for row in temp_grid]
        for z in range(h):
            for x in range(w):
                if x == 0 or x == w - 1 or z == 0 or z == h - 1: continue
                total, count = 0.0, 0
                for dz in range(-1, 2):
                    for dx in range(-1, 2):
                        total += temp_grid[z + dz][x + dx]
                        count += 1
                new_grid[z][x] = total / count
        temp_grid = new_grid
    return temp_grid


def _quantize_heights(grid: List[List[float]], step: float):
    if step <= 0: return
    for z in range(len(grid)):
        for x in range(len(grid[0])):
            t = int(round(grid[z][x] / step))
            grid[z][x] = float(t) * step


def _crop_grid(grid: List[List[float]], target_size: int, margin: int) -> List[List[float]]:
    cropped = [[0.0] * target_size for _ in range(target_size)]
    for z in range(target_size):
        for x in range(target_size):
            cropped[z][x] = grid[z + margin][x + margin]
    return cropped


def generate_elevation(seed: int, cx: int, cz: int, size: int, preset: Any) -> Tuple[
    List[List[float]], List[List[float]]]:
    """
    Генерирует карту высот.
    Возвращает ДВЕ карты: (финальная_обрезанная, рабочая_с_полями)
    """
    noise_gen = OpenSimplex(seed)
    cfg = getattr(preset, "elevation", None) or {}

    # Устанавливаем размер полей/отступов. 2 клетки - хороший баланс.
    margin = 2
    working_size = size + margin * 2

    # Рассчитываем мировые координаты левого верхнего угла БОЛЬШОЙ карты
    base_wx = cx * size - margin
    base_wz = cz * size - margin

    large_grid = [[0.0 for _ in range(working_size)] for _ in range(working_size)]
    scale_tiles = float(cfg.get("noise_scale_tiles", 32.0))
    freq = 1.0 / scale_tiles

    # 1. Создаем базовый, естественный рельеф с помощью шума (без изменений)
    for z in range(working_size):
        for x in range(working_size):
            wx, wz = base_wx + x, base_wz + z
            noise_val = fbm2d(noise_gen, float(wx), float(wz), freq, octaves=4, gain=0.5)
            large_grid[z][x] = max(0.0, min(1.0, noise_val))

    _apply_shaping_curve(large_grid, float(cfg.get("shaping_power", 1.0)))

    # 2. Масштабируем до максимальной высоты (без изменений)
    max_h = float(cfg.get("max_height_m", 60.0))
    if max_h > 0:
        for z in range(working_size):
            for x in range(working_size):
                large_grid[z][x] *= max_h

    smoothed_grid = _smooth_grid(large_grid, int(cfg.get("smoothing_passes", 0)))

    # 3. Применяем логику террасирования (без изменений)
    terr = (cfg.get("terracing") or {})
    if terr and terr.get("enabled", False):
        # ... (внутренняя логика террасирования остается прежней) ...
        steps = [float(s) for s in terr.get("steps_m", [])]
        if steps:
            mask_cfg = (terr.get("mask") or {})
            bins = list(terr.get("bins") or [])
            scale_tiles_mask = float(mask_cfg.get("noise_scale_tiles", 2048.0))
            freq_m = 1.0 / max(1.0, scale_tiles_mask)
            octaves_m = int(mask_cfg.get("octaves", 2))
            gain_m = float(mask_cfg.get("gain", 0.5))

            mask_noise = OpenSimplex((seed ^ 0x9E3779B1) & 0x7FFFFFFF)
            H, W = len(smoothed_grid), len(smoothed_grid[0])

            for z in range(H):
                for x in range(W):
                    wx, wz = base_wx + x, base_wz + z
                    noise_val = fbm2d(mask_noise, float(wx), float(wz), freq_m, octaves_m, 2.0, gain_m)

                    idx = 0
                    while idx < len(bins) and noise_val > bins[idx]:
                        idx += 1

                    step_to_use = steps[min(idx, len(steps) - 1)]
                    if step_to_use > 0:
                        t = int(round(smoothed_grid[z][x] / step_to_use))
                        smoothed_grid[z][x] = float(t) * step_to_use
    else:
        _quantize_heights(smoothed_grid, float(cfg.get("quantization_step_m", 0.0)))

    # Создаем финальную, обрезанную карту
    final_grid = _crop_grid(smoothed_grid, size, margin)

    # Возвращаем ОБЕ карты
    return final_grid, smoothed_grid


def classify_terrain(
        elevation_grid: List[List[float]],
        surface_grid: List[List[str]], # <-- Мы это уже исправляли, все верно
        nav_grid: List[List[str]],     # <-- Мы это уже исправляли, все верно
        preset: Any
) -> None:
    size = len(surface_grid)
    cfg = getattr(preset, "elevation", None) or {}
    sea_level = float(cfg.get("sea_level_m", 9.0))
    for z in range(size):
        for x in range(size):
            elev = elevation_grid[z][x]
            if elev < sea_level:
                surface_grid[z][x] = KIND_SAND
                nav_grid[z][x] = NAV_OBSTACLE
            else:
                surface_grid[z][x] = KIND_GROUND
                nav_grid[z][x] = NAV_PASSABLE


def apply_slope_obstacles(
        elevation_grid_with_margin: List[List[float]],
        surface_grid: List[List[str]],
        preset: Any
) -> None:
    target_size = len(surface_grid)
    margin = (len(elevation_grid_with_margin) - target_size) // 2
    cfg = getattr(preset, "slope_obstacles", None) or {}
    if not cfg.get("enabled", False): return

    thr_ratio = math.tan(math.radians(float(cfg.get("angle_threshold_deg", 55.0))))
    # --- НОВОЕ: Читаем ширину полосы склона из пресета ---
    band_cells = int(cfg.get("band_cells", 2))

    protected_surfaces = {KIND_ROAD}
    NEI8 = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))

    # --- ЭТАП 1: Находим все самые крайние клетки обрывов ---
    cliff_edges = [[False for _ in range(target_size)] for _ in range(target_size)]
    for z in range(target_size):
        for x in range(target_size):
            if surface_grid[z][x] in protected_surfaces:
                continue

            h0 = elevation_grid_with_margin[z + margin][x + margin]
            is_cliff_edge = False
            for dx, dz in NEI8:
                nx, nz = x + margin + dx, z + margin + dz
                h_neighbor = elevation_grid_with_margin[nz][nx]
                if h0 - h_neighbor >= thr_ratio:
                    is_cliff_edge = True
                    break
            if is_cliff_edge:
                cliff_edges[z][x] = True

    # --- ЭТАП 2: "Раздуваем" края обрывов вглубь, создавая полосу склонов ---
    for z in range(target_size):
        for x in range(target_size):
            if not cliff_edges[z][x]:
                continue

            # Помечаем саму клетку обрыва как склон
            surface_grid[z][x] = KIND_SLOPE

            # Ищем направление "вверх" (к центру возвышенности)
            h0 = elevation_grid_with_margin[z + margin][x + margin]
            grad_x, grad_z = 0, 0
            for dx, dz in NEI8:
                nx, nz = x + margin + dx, z + margin + dz
                h_neighbor = elevation_grid_with_margin[nz][nx]
                if h_neighbor > h0:
                    grad_x += dx
                    grad_z += dz

            # Нормализуем вектор направления
            length = math.hypot(grad_x, grad_z)
            if length > 0:
                ux, uz = grad_x / length, grad_z / length
                # "Рисуем" полосу склонов вглубь от обрыва
                for i in range(1, band_cells + 1):
                    bx = round(x + i * ux)
                    bz = round(z + i * uz)
                    if 0 <= bx < target_size and 0 <= bz < target_size:
                        if surface_grid[bz][bx] not in protected_surfaces:
                            surface_grid[bz][bx] = KIND_SLOPE


def apply_beaches(
        elevation_grid: List[List[float]],
        surface_grid: List[List[str]],  # <-- ИЗМЕНЕНИЕ: kind_grid -> surface_grid
        nav_grid: List[List[str]],  # <-- Добавили nav_grid
        preset: Any
) -> None:
    size = len(surface_grid)
    if size == 0: return

    elev_cfg = getattr(preset, "elevation", {}) or {}
    step = float(elev_cfg.get("quantization_step_m", 1.0))
    height_threshold = step * 0.5

    new_surface_grid = [row[:] for row in surface_grid]
    for z in range(size):
        for x in range(size):
            if surface_grid[z][x] != KIND_GROUND: continue

            is_beach = False
            for dx, dz in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, nz = x + dx, z + dz
                # --- ИЗМЕНЕНИЕ: Проверяем воду в nav_grid ---
                if 0 <= nx < size and 0 <= nz < size and nav_grid[nz][nx] == NAV_WATER:
                    h_ground = elevation_grid[z][x]
                    h_water = elevation_grid[nz][nx]
                    if abs(h_ground - h_water) < height_threshold:
                        is_beach = True
                        break
            if is_beach: new_surface_grid[z][x] = KIND_SAND

    for z in range(size):
        surface_grid[z][x] = new_surface_grid[z][x]


def generate_scatter_mask(
        seed: int, cx: int, cz: int, size: int,
        surface_grid: List[List[str]], # <-- ИЗМЕНЕНИЕ: kind_grid -> surface_grid
        preset: Any
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
            # --- ИЗМЕНЕНИЕ: Проверяем поверхность по surface_grid ---
            if surface_grid[z][x] in (KIND_GROUND, KIND_SAND):
                wx, wz = cx * size + x, cz * size + z
                group_val = (group_noise_gen.noise2(wx * group_freq, wz * group_freq) + 1.0) / 2.0
                if group_val > group_threshold:
                    detail_val = (detail_noise_gen.noise2(wx * detail_freq, wz * detail_freq) + 1.0) / 2.0
                    if detail_val > detail_threshold:
                        obstacle_mask[z][x] = True

    return obstacle_mask