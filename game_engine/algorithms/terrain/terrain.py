# game_engine/algorithms/terrain/terrain.py
from __future__ import annotations
from typing import Any, List
import math

from opensimplex import OpenSimplex

# --- ИЗМЕНЕНИЯ: Правильные пути ---
from .features import fbm2d
from ...core.constants import KIND_GROUND, KIND_OBSTACLE, KIND_WATER, KIND_SLOPE, KIND_WALL, KIND_ROAD


# (весь остальной код в этом файле не требует изменений)
# ...
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
    snap_k_h = int(cfg.get("noise_snap_k", 1))

    for z in range(working_size):
        for x in range(working_size):
            wx, wz = base_wx + x, base_wz + z
            if snap_k_h > 1:
                wx = (wx // snap_k_h) * snap_k_h
                wz = (wz // snap_k_h) * snap_k_h
            noise_val = fbm2d(noise_gen, float(wx), float(wz), freq, octaves=4, gain=0.5)
            large_grid[z][x] = max(0.0, min(1.0, noise_val))

    _apply_shaping_curve(large_grid, float(cfg.get("shaping_power", 1.0)))
    max_h = float(cfg.get("max_height_m", 50.0))
    for z in range(working_size):
        for x in range(working_size):
            large_grid[z][x] *= max_h

    smoothed_grid = _smooth_grid(large_grid, int(cfg.get("smoothing_passes", 0)))
    terr = (cfg.get("terracing") or {})
    if terr and terr.get("enabled", False):
        steps = [float(s) for s in terr.get("steps_m", [float(cfg.get("quantization_step_m", 0.0))])]
        if not steps:
            steps = [float(cfg.get("quantization_step_m", 0.0))]

        mask_cfg = (terr.get("mask") or {})
        bins = list(terr.get("bins") or [])
        smooth_cells = int(terr.get("smooth_cells", 0))
        scale_tiles = float(mask_cfg.get("noise_scale_tiles", 2048.0))
        freq_m = 1.0 / max(1.0, scale_tiles)
        octaves_m = int(mask_cfg.get("octaves", 2))
        gain_m = float(mask_cfg.get("gain", 0.5))
        snap_k = int(mask_cfg.get("snap_k", 1))
        mask_noise = OpenSimplex((seed ^ 0x9E3779B1) & 0x7fffffff)
        H, W = len(smoothed_grid), len(smoothed_grid[0])
        step_map = [[steps[0]] * W for _ in range(H)]

        for z in range(H):
            wz = base_wz + z
            for x in range(W):
                wx = base_wx + x
                if snap_k > 1:
                    wx = (wx // snap_k) * snap_k
                    wz = (wz // snap_k) * snap_k
                v = fbm2d(mask_noise, float(wx), float(wz), freq_m, octaves_m, 2.0, gain_m)
                idx = 0
                while idx < len(bins) and v > bins[idx]:
                    idx += 1
                if idx >= len(steps):
                    idx = len(steps) - 1
                step_map[z][x] = steps[idx]

        for _ in range(max(0, smooth_cells)):
            new_map = [row[:] for row in step_map]
            for z in range(1, H - 1):
                for x in range(1, W - 1):
                    neigh = (
                        step_map[z - 1][x - 1], step_map[z - 1][x], step_map[z - 1][x + 1],
                        step_map[z][x - 1], step_map[z][x], step_map[z][x + 1],
                        step_map[z + 1][x - 1], step_map[z + 1][x], step_map[z + 1][x + 1]
                    )
                    best = max(set(neigh), key=neigh.count)
                    new_map[z][x] = best
            step_map = new_map

        for z in range(H):
            for x in range(W):
                s = step_map[z][x]
                if s > 0.0:
                    t = int(round(smoothed_grid[z][x] / s))
                    smoothed_grid[z][x] = float(t) * s
    else:
        _quantize_heights(smoothed_grid, float(cfg.get("quantization_step_m", 0.0)))

    final_grid = _crop_grid(smoothed_grid, size, margin)
    return final_grid


def classify_terrain(
        elevation_grid: List[List[float]],
        kind_grid: List[List[str]],
        preset: Any
) -> None:
    """Заполняет kind_grid типами ландшафта, НЕ перезаписывая специальные тайлы."""
    size = len(kind_grid)
    cfg = getattr(preset, "elevation", None) or {}
    sea_level = float(cfg.get("sea_level_m", 20.0))
    mountain_level = float(cfg.get("mountain_level_m", 45.0))

    # --- КЛЮЧЕВОЕ ИЗМЕНЕНИЕ ---
    # Список тайлов, которые нельзя перезаписывать.
    # Добавьте сюда 'road', если дороги будут краситься до этого этапа.
    protected_kinds = {KIND_WALL, KIND_ROAD}

    for z in range(size):
        for x in range(size):
            # Если тайл уже имеет специальный тип, мы его пропускаем.
            if kind_grid[z][x] in protected_kinds:
                continue

            elev = elevation_grid[z][x]
            if elev < sea_level:
                kind_grid[z][x] = KIND_WATER
            elif elev > mountain_level:
                kind_grid[z][x] = KIND_OBSTACLE
            else:
                kind_grid[z][x] = KIND_GROUND

def apply_slope_obstacles(elevation_grid, kind_grid, preset) -> None:
    size = len(kind_grid)
    cfg = getattr(preset, "slope_obstacles", None) or {}
    if not cfg.get("enabled", False):
        return

    cell_size = float(getattr(preset, "cell_size", 1.0))
    band_cells = int(cfg.get("band_cells", 1))
    use_diagonals = bool(cfg.get("use_diagonals", True))
    ignore_water_edges = bool(cfg.get("ignore_water_edges", True))

    # порог по углу/крутизне/Δh
    if "angle_threshold_deg" in cfg:
        thr_ratio = math.tan(math.radians(float(cfg["angle_threshold_deg"])))
    elif "slope_threshold_percent" in cfg:
        thr_ratio = float(cfg["slope_threshold_percent"]) / 100.0
    else:
        dh = float(cfg.get("delta_h_threshold_m", 3.0))
        thr_ratio = dh / max(cell_size, 1e-9)
    min_dh = float(cfg.get("min_delta_h_m", 0.0))  # опционально

    def allow_edge(k0, k1) -> bool:
        if not ignore_water_edges:
            return True
        # блокируем только вода-вода; берег (вода-земля) разрешаем
        return not (k0 == KIND_WATER and k1 == KIND_WATER)

    def mark_land(x, z):
        if 0 <= x < size and 0 <= z < size:
            if kind_grid[z][x] not in (KIND_OBSTACLE, KIND_WATER):
                kind_grid[z][x] = KIND_SLOPE

    eps = 1e-6
    # осевые рёбра
    for z in range(size):
        for x in range(size):
            h0 = elevation_grid[z][x]
            k0 = kind_grid[z][x]

            if x + 1 < size:
                k1 = kind_grid[z][x + 1]
                if allow_edge(k0, k1):
                    dhx = abs(h0 - elevation_grid[z][x + 1])
                    if dhx + eps >= max(min_dh, thr_ratio * cell_size):
                        mark_land(x, z)
                        mark_land(x + 1, z)
                        for k in range(1, band_cells):
                            mark_land(x, z - k); mark_land(x, z + k)
                            mark_land(x + 1, z - k); mark_land(x + 1, z + k)

            if z + 1 < size:
                k1 = kind_grid[z + 1][x]
                if allow_edge(k0, k1):
                    dhz = abs(h0 - elevation_grid[z + 1][x])
                    if dhz + eps >= max(min_dh, thr_ratio * cell_size):
                        mark_land(x, z)
                        mark_land(x, z + 1)
                        for k in range(1, band_cells):
                            mark_land(x - k, z); mark_land(x + k, z)
                            mark_land(x - k, z + 1); mark_land(x + k, z + 1)

    # диагонали
    if use_diagonals:
        run_d = cell_size * math.sqrt(2.0)
        for z in range(size - 1):
            for x in range(size - 1):
                k00 = kind_grid[z][x]; k11 = kind_grid[z + 1][x + 1]
                if allow_edge(k00, k11):
                    dhd = abs(elevation_grid[z][x] - elevation_grid[z + 1][x + 1])
                    if dhd + eps >= max(min_dh, thr_ratio * run_d):
                        mark_land(x, z); mark_land(x + 1, z + 1)

                k01 = kind_grid[z][x + 1]; k10 = kind_grid[z + 1][x]
                if allow_edge(k01, k10):
                    dhd = abs(elevation_grid[z][x + 1] - elevation_grid[z + 1][x])
                    if dhd + eps >= max(min_dh, thr_ratio * run_d):
                        mark_land(x + 1, z); mark_land(x, z + 1)