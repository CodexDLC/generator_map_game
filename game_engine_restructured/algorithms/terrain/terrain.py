# Файл: game_engine/algorithms/terrain/terrain.py
from __future__ import annotations
from typing import Any, List, Tuple
import math

import numpy as np
from opensimplex import OpenSimplex

from .features import fbm2d
from .slope import compute_slope_mask
from ...core import constants as const
from ...core.constants import NAV_PASSABLE


def _apply_shaping_curve(grid: np.ndarray, power: float):
    if power == 1.0:
        return
    sign = np.sign(grid)
    normalized_abs = np.abs(grid)
    shaped_abs = np.power(normalized_abs, power)
    np.copyto(grid, shaped_abs * sign)


def _smooth_grid(grid: np.ndarray, passes: int) -> np.ndarray:
    if passes <= 0:
        return grid

    smoothed = grid.copy()
    for _ in range(passes):
        temp = np.pad(smoothed, pad_width=1, mode='edge')
        blurred = (temp[:-2, :-2] + temp[:-2, 1:-1] + temp[:-2, 2:] +
                   temp[1:-1, :-2] + temp[1:-1, 1:-1] + temp[1:-1, 2:] +
                   temp[2:, :-2] + temp[2:, 1:-1] + temp[2:, 2:]) / 9.0
        smoothed = blurred
    return smoothed


def _quantize_heights(grid: np.ndarray, step: float):
    if step <= 0:
        return
    np.round(grid / step, out=grid)
    grid *= step

# --- ИЗМЕНЕНИЕ: Функция _apply_terraform_rules полностью удалена ---

def generate_elevation(
        seed: int, cx: int, cz: int, size: int, preset: Any
) -> Tuple[List[List[float]], np.ndarray]:
    cfg = getattr(preset, "elevation", {})
    spectral_cfg = cfg.get("spectral", {})
    warp_cfg = cfg.get("warp", {})

    noise_gen = OpenSimplex(seed)
    warp_noise_x = OpenSimplex(seed ^ 0xCAFEF00D)
    warp_noise_z = OpenSimplex(seed ^ 0xDEADBEEF)

    margin = 1
    working_size = size + margin * 2
    base_wx = cx * size - margin
    base_wz = cz * size - margin

    height_grid = np.zeros((working_size, working_size), dtype=np.float32)

    total_max_amp = sum(float(layer_cfg.get("amp_m", 0.0)) for layer_cfg in spectral_cfg.values())
    if total_max_amp == 0: total_max_amp = 1.0

    for z_idx in range(working_size):
        for x_idx in range(working_size):
            wx, wz = float(base_wx + x_idx), float(base_wz + z_idx)

            warp_scale = float(warp_cfg.get("scale_tiles", 1.0))
            warp_strength = float(warp_cfg.get("strength_m", 0.0))

            warped_wx, warped_wz = wx, wz
            if warp_scale > 0 and warp_strength > 0:
                warp_freq = 1.0 / warp_scale
                offset_x = warp_noise_x.noise2(wx * warp_freq, wz * warp_freq) * warp_strength
                offset_z = warp_noise_z.noise2(wx * warp_freq, wz * warp_freq) * warp_strength
                warped_wx += offset_x
                warped_wz += offset_z

            final_height = 0.0
            for layer_cfg in spectral_cfg.values():
                scale = float(layer_cfg.get("scale_tiles", 1.0))
                amp = float(layer_cfg.get("amp_m", 0.0))
                if scale <= 0 or amp <= 0: continue

                freq = 1.0 / scale
                octaves = int(layer_cfg.get("octaves", 1))
                ridge = bool(layer_cfg.get("ridge", False))

                layer_noise = fbm2d(
                    noise_gen, warped_wx, warped_wz, freq, octaves=octaves, ridge=ridge
                )
                final_height += layer_noise * amp

            height_grid[z_idx, x_idx] = final_height

    if total_max_amp > 0:
        normalized_grid = height_grid / total_max_amp
        _apply_shaping_curve(normalized_grid, float(cfg.get("shaping_power", 1.0)))
        height_grid = normalized_grid * total_max_amp

    # --- ИЗМЕНЕНИЕ: Вызов терраформинга здесь удален ---

    height_grid = _smooth_grid(height_grid, int(cfg.get("smoothing_passes", 0)))
    _quantize_heights(height_grid, float(cfg.get("quantization_step_m", 0.0)))

    max_h = float(cfg.get("max_height_m", 150.0))
    np.clip(height_grid, None, max_h, out=height_grid)

    final_grid_list = height_grid[margin:-margin, margin:-margin].tolist()
    return final_grid_list, height_grid


def classify_terrain(
        elevation_grid: List[List[float]],
        surface_grid: List[List[str]],
        nav_grid: List[List[str]],
        preset: Any,
) -> None:
    size = len(surface_grid)
    for z in range(size):
        for x in range(size):
            surface_grid[z][x] = const.KIND_BASE_DIRT
            nav_grid[z][x] = NAV_PASSABLE


def apply_slope_obstacles(height_grid_with_margin: np.ndarray, surface_grid: List[List[str]], preset: Any) -> None:
    s_cfg = dict(getattr(preset, "slope_obstacles", {}) or {})
    if not s_cfg.get("enabled", False):
        return

    angle = float(s_cfg.get("angle_threshold_deg", 45.0))
    band = int(s_cfg.get("band_cells", 0))
    cell = float(getattr(preset, "cell_size", 1.0))

    H = height_grid_with_margin
    gz, gx = np.gradient(H, cell)

    tangent_slope = np.sqrt(gx ** 2 + gz ** 2)
    threshold = math.tan(math.radians(angle))

    mask = tangent_slope >= threshold

    if band > 0:
        try:
            from scipy.ndimage import binary_dilation
            mask = binary_dilation(mask, iterations=band)
        except ImportError:
            print("!!! WARNING: `scipy` not installed. Cannot perform slope band dilation.")

    margin = (mask.shape[0] - len(surface_grid)) // 2
    if margin > 0:
        mask = mask[margin:-margin, margin:-margin]

    for z, x in np.argwhere(mask):
        surface_grid[z][x] = const.KIND_BASE_ROCK