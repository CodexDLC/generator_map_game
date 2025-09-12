# Файл: game_engine_restructured/algorithms/terrain/terrain.py
from __future__ import annotations
from typing import Any
import numpy as np
from opensimplex import OpenSimplex

from .features import fbm2d
from .slope import compute_slope_mask
from ...core import constants as const
from ...core.constants import (
    SURFACE_ID_TO_KIND, NAV_ID_TO_KIND,  # пригодится при экспорте
    surface_fill, surface_set, nav_fill
)

# ----------------- utils -----------------

def _apply_shaping_curve(grid: np.ndarray, power: float):
    if power == 1.0:
        return
    np.power(grid, power, out=grid)

def _smooth_grid(grid: np.ndarray, passes: int, scratch_buffer: np.ndarray) -> np.ndarray:
    if passes <= 0:
        return grid
    from scipy.ndimage import gaussian_filter
    sigma = 0.6 * passes
    gaussian_filter(grid, sigma=sigma, output=scratch_buffer, mode='reflect')
    return scratch_buffer

def _quantize_heights(grid: np.ndarray, step: float):
    if step <= 0:
        return
    np.round(grid / step, out=grid)
    grid *= step

# ----------------- main -----------------

def generate_elevation_region(
    seed: int, scx: int, scz: int,
    region_size_chunks: int, chunk_size: int,
    preset: Any, scratch_buffers: dict
) -> np.ndarray:
    """
    Генерирует рельеф для всего EXT-региона (core + фартук) одним полотном.
    Возвращает float32 матрицу высот (та же ссылка, что scratch_buffers['a']).
    """
    cfg = getattr(preset, "elevation", {})
    spectral_cfg = cfg.get("spectral", {})
    warp_cfg     = cfg.get("warp", {})
    border_chunks = 1

    ext_region_size = region_size_chunks + 2 * border_chunks
    ext_px = ext_region_size * chunk_size

    height_grid = scratch_buffers['a']
    height_grid.fill(0.0)

    noise_gen   = OpenSimplex(seed)
    warp_x_gen  = OpenSimplex(seed ^ 0xCAFEF00D)
    warp_z_gen  = OpenSimplex(seed ^ 0xDEADBEEF)

    base_wx = (scx * region_size_chunks - border_chunks) * chunk_size
    base_wz = (scz * region_size_chunks - border_chunks) * chunk_size

    wx_1d = base_wx + np.arange(ext_px, dtype=np.float32)
    wz_1d = base_wz + np.arange(ext_px, dtype=np.float32)
    wx_grid, wz_grid = np.meshgrid(wx_1d, wz_1d, indexing="xy")

    # --- warp ---
    warp_scale    = float(warp_cfg.get("scale_tiles", 1.0))
    warp_strength = float(warp_cfg.get("strength_m", 0.0))
    if warp_scale > 0 and warp_strength > 0:
        warp_freq = 1.0 / warp_scale
        warp_buf  = scratch_buffers['b']
        for z in range(ext_px):
            for x in range(ext_px):
                warp_buf[z, x] = warp_x_gen.noise2(wx_grid[z, x] * warp_freq, wz_grid[z, x] * warp_freq)
        wx_grid += warp_buf * warp_strength
        for z in range(ext_px):
            for x in range(ext_px):
                warp_buf[z, x] = warp_z_gen.noise2(wx_grid[z, x] * warp_freq, wz_grid[z, x] * warp_freq)
        wz_grid += warp_buf * warp_strength

    # --- спектральные слои ---
    total_amp = sum(float(l.get("amp_m", 0.0)) for l in spectral_cfg.values()) or 1.0
    layer_buf = scratch_buffers['b']

    for layer_cfg in spectral_cfg.values():
        scale   = float(layer_cfg.get("scale_tiles", 1.0))
        amp     = float(layer_cfg.get("amp_m", 0.0))
        if scale <= 0 or amp <= 0:
            continue
        freq    = 1.0 / scale
        octaves = int(layer_cfg.get("octaves", 1))
        ridge   = bool(layer_cfg.get("ridge", False))

        for z in range(ext_px):
            for x in range(ext_px):
                layer_buf[z, x] = fbm2d(noise_gen, wx_grid[z, x], wz_grid[z, x], freq, octaves, ridge=ridge)

        height_grid += layer_buf * amp

    # --- постобработка ---
    height_grid /= total_amp
    _apply_shaping_curve(height_grid, float(cfg.get("shaping_power", 1.0)))
    height_grid *= total_amp

    smoothed = _smooth_grid(height_grid, int(cfg.get("smoothing_passes", 0)), scratch_buffers['b'])
    _quantize_heights(smoothed, float(cfg.get("quantization_step_m", 0.0)))

    max_h = float(cfg.get("max_height_m", 150.0))

    def _assert_range(name, arr):
        mn = float(arr.min());
        mx = float(arr.max());
        rng = mx - mn
        print(f"[CHECK] {name}: min={mn:.4f} max={mx:.4f} rng={rng:.6f}")
        if rng < 1e-5:
            raise RuntimeError(f"{name}: диапазон ~0 (всё затёрто)")

    _assert_range("height_before_clip", smoothed)

    max_h = float(cfg.get("max_height_m", 150.0))
    sea = float(cfg.get("sea_level_m", 40.0))  # если в пресете там лежит
    if not (max_h > sea + 10.0):
        raise ValueError(f"Некорректные параметры: max_height_m={max_h} <= sea_level_m+10 ({sea}+10)")



    np.clip(smoothed, None, max_h, out=smoothed)
    return smoothed

def classify_terrain(elevation_grid: np.ndarray,
                     surface_grid: np.ndarray,
                     nav_grid: np.ndarray,
                     preset: Any) -> None:
    """Инициализация слоёв: всё — земля и проходимо."""
    surface_fill(surface_grid, const.KIND_BASE_DIRT)
    nav_fill(nav_grid, const.NAV_PASSABLE)

def apply_slope_obstacles(height_grid_with_margin: np.ndarray,
                          surface_grid: np.ndarray,
                          preset: Any) -> None:
    """Ставим скальные/непроходимые участки по уклону."""
    s_cfg = dict(getattr(preset, "slope_obstacles", {}) or {})
    if not s_cfg.get("enabled", False):
        return
    angle = float(s_cfg.get("angle_threshold_deg", 45.0))
    band  = int(s_cfg.get("band_cells", 3))
    cell  = float(getattr(preset, "cell_size", 1.0))

    mask = compute_slope_mask(height_grid_with_margin, cell, angle, band)
    surface_set(surface_grid, mask, const.KIND_BASE_ROCK)
