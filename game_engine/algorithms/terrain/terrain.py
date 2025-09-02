# game_engine/algorithms/terrain/terrain.py
from __future__ import annotations
from typing import Any, List
import math

from opensimplex import OpenSimplex

from .features import fbm2d
from ...core.constants import (
    KIND_GROUND, KIND_OBSTACLE, KIND_WATER, KIND_SLOPE, KIND_WALL, KIND_ROAD, KIND_SAND,
    KIND_BRIDGE
)


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


def generate_elevation(seed: int, cx: int, cz: int, size: int, preset: Any) -> List[List[float]]:
    noise_gen = OpenSimplex(seed)
    cfg = getattr(preset, "elevation", None) or {}
    margin = 2
    working_size = size + margin * 2
    base_wx = cx * size - margin
    base_wz = cz * size - margin
    large_grid = [[0.0 for _ in range(working_size)] for _ in range(working_size)]
    scale_tiles = float(cfg.get("noise_scale_tiles", 32.0))
    freq = 1.0 / scale_tiles

    # 1. Создаем базовый, естественный рельеф с помощью шума
    for z in range(working_size):
        for x in range(working_size):
            wx, wz = base_wx + x, base_wz + z
            noise_val = fbm2d(noise_gen, float(wx), float(wz), freq, octaves=4, gain=0.5)
            large_grid[z][x] = max(0.0, min(1.0, noise_val))

    _apply_shaping_curve(large_grid, float(cfg.get("shaping_power", 1.0)))

    # 2. Масштабируем его до максимальной высоты
    max_h = float(cfg.get("max_height_m", 60.0))
    if max_h > 0:
        for z in range(working_size):
            for x in range(working_size):
                large_grid[z][x] *= max_h

    smoothed_grid = _smooth_grid(large_grid, int(cfg.get("smoothing_passes", 0)))

    # 3. А уже ПОТОМ применяем к этому рельефу логику террасирования
    terr = (cfg.get("terracing") or {})
    if terr and terr.get("enabled", False):
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

                    # Логика округления до ближайшего шага из steps_m
                    step_to_use = steps[min(idx, len(steps) - 1)]
                    if step_to_use > 0:
                        t = int(round(smoothed_grid[z][x] / step_to_use))
                        smoothed_grid[z][x] = float(t) * step_to_use
    else:
        # Если террасирование выключено, используется общая квантизация
        _quantize_heights(smoothed_grid, float(cfg.get("quantization_step_m", 0.0)))

    final_grid = _crop_grid(smoothed_grid, size, margin)
    return final_grid


def classify_terrain(
        elevation_grid: List[List[float]],
        kind_grid: List[List[str]],
        preset: Any
) -> None:
    size = len(kind_grid)
    cfg = getattr(preset, "elevation", None) or {}
    sea_level = float(cfg.get("sea_level_m", 12.0))
    protected_kinds = {KIND_WALL, KIND_ROAD, KIND_BRIDGE}

    for z in range(size):
        for x in range(size):
            if kind_grid[z][x] in protected_kinds: continue

            elev = elevation_grid[z][x]
            if elev < sea_level:
                kind_grid[z][x] = KIND_WATER
            else:
                kind_grid[z][x] = KIND_GROUND


def apply_slope_obstacles(elevation_grid, kind_grid, preset) -> None:
    size = len(kind_grid)
    cfg = getattr(preset, "slope_obstacles", None) or {}
    if not cfg.get("enabled", False): return

    thr_ratio = 0
    if "angle_threshold_deg" in cfg:
        thr_ratio = math.tan(math.radians(float(cfg["angle_threshold_deg"])))
    else:
        dh = float(cfg.get("delta_h_threshold_m", 3.0))
        thr_ratio = dh / 1.0

    def mark_land(x, z):
        if 0 <= x < size and 0 <= z < size:
            if kind_grid[z][x] not in (KIND_OBSTACLE, KIND_WATER):
                kind_grid[z][x] = KIND_SLOPE

    for z in range(size):
        for x in range(size):
            h0 = elevation_grid[z][x]
            if x + 1 < size and abs(h0 - elevation_grid[z][x + 1]) >= thr_ratio:
                mark_land(x, z)
                mark_land(x + 1, z)
            if z + 1 < size and abs(h0 - elevation_grid[z + 1][x]) >= thr_ratio:
                mark_land(x, z)
                mark_land(x, z + 1)


def apply_beaches(
        elevation_grid: List[List[float]],
        kind_grid: List[List[str]],
        preset: Any
) -> None:
    size = len(kind_grid)
    if size == 0: return

    elev_cfg = getattr(preset, "elevation", {}) or {}
    step = float(elev_cfg.get("quantization_step_m", 1.0))
    height_threshold = step * 0.5

    new_kind_grid = [row[:] for row in kind_grid]
    for z in range(size):
        for x in range(size):
            if kind_grid[z][x] != KIND_GROUND: continue
            is_beach = False
            for dx, dz in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, nz = x + dx, z + dz
                if 0 <= nx < size and 0 <= nz < size and kind_grid[nz][nx] == KIND_WATER:
                    h_ground = elevation_grid[z][x]
                    h_water = elevation_grid[nz][nx]
                    if abs(h_ground - h_water) < height_threshold:
                        is_beach = True
                        break
            if is_beach: new_kind_grid[z][x] = KIND_SAND

    for z in range(size):
        for x in range(size):
            kind_grid[z][x] = new_kind_grid[z][x]


def apply_scatter(
        seed: int, cx: int, cz: int, size: int,
        kind_grid: List[List[str]],
        preset: Any
):
    cfg = getattr(preset, "scatter", {})
    if not cfg.get("enabled", False): return

    noise_scale = float(cfg.get("noise_scale_tiles", 16.0))
    threshold = float(cfg.get("density_threshold", 0.7))
    freq = 1.0 / noise_scale

    noise_gen = OpenSimplex((seed ^ 0xABCDEFAB) & 0x7FFFFFFF)

    for z in range(size):
        for x in range(size):
            if kind_grid[z][x] in (KIND_GROUND, KIND_SAND):
                wx, wz = cx * size + x, cz * size + z
                noise_val = (noise_gen.noise2(wx * freq, wz * freq) + 1.0) / 2.0
                if noise_val > threshold:
                    kind_grid[z][x] = KIND_OBSTACLE