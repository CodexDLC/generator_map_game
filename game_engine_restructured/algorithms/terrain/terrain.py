# Файл: game_engine_restructured/algorithms/terrain/terrain.py
from __future__ import annotations
from typing import Any
import numpy as np
from opensimplex import OpenSimplex

from .features import fbm2d
from .slope import compute_slope_mask
from ...core import constants as const
from ...core.constants import (
    # Эти маппинги могут пригодиться при экспорте; здесь не используются напрямую
    SURFACE_ID_TO_KIND, NAV_ID_TO_KIND,
    # Безопасные хелперы записи: принимают kind-строки ИЛИ числовые ID,
    # а в массив кладут всегда числовые ID.
    surface_fill, surface_set, nav_fill
)

# ----------------- утилиты -----------------

def _apply_shaping_curve(grid: np.ndarray, power: float) -> None:
    """Нелинейная форма рельефа (pow), in-place."""
    if power == 1.0:
        return
    np.power(grid, power, out=grid)

def _smooth_grid(grid: np.ndarray, passes: int, scratch_buffer: np.ndarray) -> np.ndarray:
    """Сглаживание через Gaussian в выделенный буфер."""
    if passes <= 0:
        return grid
    from scipy.ndimage import gaussian_filter
    sigma = 0.6 * passes
    gaussian_filter(grid, sigma=sigma, output=scratch_buffer, mode='reflect')
    return scratch_buffer

def _quantize_heights(grid: np.ndarray, step: float) -> None:
    """Квантование высоты по шагу (если > 0), in-place."""
    if step <= 0:
        return
    np.round(grid / step, out=grid)
    grid *= step

def _print_range(tag: str, arr: np.ndarray) -> None:
    """Компактная диагностика диапазона (совместимо с NumPy 2.x)."""
    mn = float(np.min(arr))
    mx = float(np.max(arr))
    rng = mx - mn
    print(f"[CHECK] {tag}: min={mn:.4f} max={mx:.4f} rng={rng:.6f}")

# ----------------- генерация рельефа -----------------

def generate_elevation_region(
    seed: int, scx: int, scz: int,
    region_size_chunks: int, chunk_size: int,
    preset: Any, scratch_buffers: dict
) -> np.ndarray:
    """
    Генерирует рельеф для всего EXT-региона (core + фартук) одним полотном.
    ВАЖНО: возвращает массив, который НЕ шарит память с scratch-буферами,
    чтобы последующие этапы (климат и т.п.), использующие scratch['a'/'b'],
    не перезаписывали высоту.
    """
    cfg = getattr(preset, "elevation", {})
    spectral_cfg = cfg.get("spectral", {}) or {}
    warp_cfg     = cfg.get("warp", {}) or {}
    border_chunks = 1

    ext_region_size = region_size_chunks + 2 * border_chunks
    ext_px = ext_region_size * chunk_size

    # base полотно — scratch['a']
    height_grid = scratch_buffers['a']
    height_grid.fill(0.0)

    # шумы
    noise_gen   = OpenSimplex(seed)
    warp_x_gen  = OpenSimplex(seed ^ 0xCAFEF00D)
    warp_z_gen  = OpenSimplex(seed ^ 0xDEADBEEF)

    # мировые координаты ячеек
    base_wx = (scx * region_size_chunks - border_chunks) * chunk_size
    base_wz = (scz * region_size_chunks - border_chunks) * chunk_size

    wx_1d = base_wx + np.arange(ext_px, dtype=np.float32)
    wz_1d = base_wz + np.arange(ext_px, dtype=np.float32)
    # NB: indexing="xy" — X по столбцам, Y/Z по строкам
    wx_grid, wz_grid = np.meshgrid(wx_1d, wz_1d, indexing="xy")

    # --- warp (искажение координат) ---
    warp_scale    = float(warp_cfg.get("scale_tiles", 1.0))
    warp_strength = float(warp_cfg.get("strength_m", 0.0))
    if warp_scale > 0.0 and warp_strength > 0.0:
        warp_freq = 1.0 / warp_scale
        warp_buf  = scratch_buffers['b']
        # смещаем X
        for z in range(ext_px):
            for x in range(ext_px):
                warp_buf[z, x] = warp_x_gen.noise2(wx_grid[z, x] * warp_freq, wz_grid[z, x] * warp_freq)
        wx_grid += warp_buf * warp_strength
        # смещаем Z
        for z in range(ext_px):
            for x in range(ext_px):
                warp_buf[z, x] = warp_z_gen.noise2(wx_grid[z, x] * warp_freq, wz_grid[z, x] * warp_freq)
        wz_grid += warp_buf * warp_strength

    # --- спектральные слои ---
    # порядок, если он важен, можно зафиксировать списком ключей
    ordered_layers = []
    for k in ("continents", "hills", "detail"):
        if k in spectral_cfg:
            ordered_layers.append(spectral_cfg[k])
    # добавим всё остальное (если есть)
    for v in spectral_cfg.values():
        if v not in ordered_layers:
            ordered_layers.append(v)

    total_amp = sum(float(l.get("amp_m", 0.0)) for l in ordered_layers) or 1.0
    layer_buf = scratch_buffers['b']

    for layer_cfg in ordered_layers:
        scale   = float(layer_cfg.get("scale_tiles", 1.0))
        amp     = float(layer_cfg.get("amp_m", 0.0))
        if scale <= 0.0 or amp <= 0.0:
            continue
        freq    = 1.0 / scale
        octaves = int(layer_cfg.get("octaves", 1))
        ridge   = bool(layer_cfg.get("ridge", False))

        # считаем слой в layer_buf
        for z in range(ext_px):
            for x in range(ext_px):
                layer_buf[z, x] = fbm2d(
                    noise_gen,
                    wx_grid[z, x], wz_grid[z, x],
                    freq, octaves, ridge=ridge
                )

        height_grid += layer_buf * amp

    # --- постобработка ---
    # нормализация на суммарную амплитуду
    height_grid /= total_amp
    _apply_shaping_curve(height_grid, float(cfg.get("shaping_power", 1.0)))
    height_grid *= total_amp

    # сглаживание в scratch['b']
    smoothed = _smooth_grid(height_grid, int(cfg.get("smoothing_passes", 0)), scratch_buffers['b'])
    _quantize_heights(smoothed, float(cfg.get("quantization_step_m", 0.0)))

    max_h = float(cfg.get("max_height_m", 150.0))
    sea   = float(cfg.get("sea_level_m", 40.0))
    if not (max_h > sea + 10.0):
        raise ValueError(f"elevation.max_height_m={max_h} должен быть хотя бы на 10м выше sea_level_m={sea}")

    _print_range("height_before_clip", smoothed)
    np.clip(smoothed, None, max_h, out=smoothed)

    # ВАЖНО: отрываем высоту от scratch-буферов
    # чтобы последующие этапы могли свободно использовать scratch['a'/'b']
    height_out = smoothed.copy()  # отдельная память (float32), ~31 МБ на регион  (2848^2)
    return height_out

# ----------------- классификация покрытия и препятствий -----------------

def classify_terrain(elevation_grid: np.ndarray,
                     surface_grid: np.ndarray,
                     nav_grid: np.ndarray,
                     preset: Any) -> None:
    """
    Инициализация слоёв: всё — земля и проходимо.
    Пишем ТОЛЬКО числовые ID (через helpers из constants).
    """
    surface_fill(surface_grid, const.KIND_BASE_DIRT)
    nav_fill(nav_grid, const.NAV_PASSABLE)

def apply_slope_obstacles(height_grid_with_margin: np.ndarray,
                          surface_grid: np.ndarray,
                          preset: Any) -> None:
    """
    Ставим скальные участки по уклону. Пишем ID, не строки.
    """
    s_cfg = dict(getattr(preset, "slope_obstacles", {}) or {})
    if not s_cfg.get("enabled", False):
        return
    angle = float(s_cfg.get("angle_threshold_deg", 45.0))
    band  = int(s_cfg.get("band_cells", 3))
    cell  = float(getattr(preset, "cell_size", 1.0))

    mask = compute_slope_mask(height_grid_with_margin, cell, angle, band)
    surface_set(surface_grid, mask, const.KIND_BASE_ROCK)
