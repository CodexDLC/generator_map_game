# ==============================================================================
# Файл: game_engine_restructured/algorithms/terrain/terrain.py
# Назначение: Генерация геометрии ландшафта (карты высот).
# ВЕРСИЯ 9.0: Финальная версия с корректной структурой и рабочей логикой Domain Warping.
# ==============================================================================
from __future__ import annotations
from typing import Any, Dict
import numpy as np
from scipy.ndimage import gaussian_filter

from ...core.noise.fast_noise import fbm_grid, fbm_amplitude, fbm_grid_warped


# ==============================================================================
# --- БЛОК 1: Вспомогательные утилиты (без изменений) ---
# ==============================================================================

def _apply_shaping_curve(grid: np.ndarray, power: float) -> None:
    if power != 1.0:
        np.power(grid, power, out=grid)


def _print_range(tag: str, arr: np.ndarray) -> None:
    mn, mx = float(np.min(arr)), float(np.max(arr))
    print(f"[CHECK] {tag}: min={mn:.2f} max={mx:.2f} rng={mx - mn:.2f}")


# ==============================================================================
# --- БЛОК 2: Функции для генерации отдельных слоев рельефа ---
# ==============================================================================

def _generate_base_layer(
        seed: int,
        layer_cfg: Dict,
        coords_x: np.ndarray,
        coords_z: np.ndarray,
        cell_size: float
) -> np.ndarray:
    """
    Генерирует базовый слой рельефа, используя переданные (возможно, искаженные) координаты.
    """
    amp = float(layer_cfg.get("amp_m", 0.0))
    if amp <= 0:
        return np.zeros_like(coords_x)

    noise = fbm_grid_warped(
        seed=seed, coords_x=coords_x, coords_z=coords_z,
        freq0=1.0 / (float(layer_cfg.get("scale_tiles", 1000)) * cell_size),
        octaves=int(layer_cfg.get("octaves", 3)),
        ridge=bool(layer_cfg.get("ridge", False))
    )

    min_val, max_val = np.min(noise), np.max(noise)
    if (max_val - min_val) > 1e-6:
        noise = (noise - min_val) / (max_val - min_val)

    shaping_power = float(layer_cfg.get("shaping_power", 1.0))
    _apply_shaping_curve(noise, shaping_power)

    return noise * amp


def _generate_additive_layer(
        seed: int,
        layer_cfg: Dict,
        coords_x: np.ndarray,
        coords_z: np.ndarray,
        cell_size: float
) -> np.ndarray:
    """
    Генерирует дополнительный слой рельефа, используя переданные координаты.
    """
    amp = float(layer_cfg.get("amp_m", 0.0))
    if amp <= 0:
        return np.zeros_like(coords_x)

    octaves = int(layer_cfg.get("octaves", 4))
    noise = fbm_grid_warped(
        seed=seed, coords_x=coords_x, coords_z=coords_z,
        freq0=1.0 / (float(layer_cfg.get("scale_tiles", 200)) * cell_size),
        octaves=octaves,
        ridge=bool(layer_cfg.get("ridge", False))
    )

    norm_factor = fbm_amplitude(0.5, octaves)
    if norm_factor > 1e-6:
        noise /= norm_factor

    shaping_power = float(layer_cfg.get("shaping_power", 1.0))
    if shaping_power != 1.0:
        signs = np.sign(noise)
        shaped_noise = np.power(np.abs(noise), shaping_power)
        noise = shaped_noise * signs

    return noise * amp


# ==============================================================================
# --- БЛОК 3: Главная функция-оркестратор ---
# ==============================================================================

def generate_elevation_region(
        seed: int, scx: int, scz: int,
        region_size_chunks: int, chunk_size: int,
        preset: Any, scratch_buffers: dict
) -> np.ndarray:
    # --- ЭТАП 0: Инициализация ---
    cfg = getattr(preset, "elevation", {})
    spectral_cfg = cfg.get("spectral", {}) or {}
    ext_size = (region_size_chunks + 2) * chunk_size
    cell_size = float(getattr(preset, "cell_size", 1.0))
    base_wx = (scx * region_size_chunks - 1) * chunk_size
    base_wz = (scz * region_size_chunks - 1) * chunk_size

    # --- ЭТАП 0.5: Domain Warping (Искажение координат) ---
    warp_cfg = cfg.get("warp", {})
    warp_strength = float(warp_cfg.get("strength_m", 0.0))

    z_coords, x_coords = np.mgrid[0:ext_size, 0:ext_size]
    x_coords = (x_coords.astype(np.float32) + base_wx) * cell_size
    z_coords = (z_coords.astype(np.float32) + base_wz) * cell_size

    if warp_strength > 0:
        print("  -> Applying domain warp...")
        warp_scale = float(warp_cfg.get("scale_tiles", 1000)) * cell_size
        warp_freq = 1.0 / warp_scale if warp_scale > 0 else 0

        warp_x_noise = fbm_grid(
            seed=seed ^ 0x12345678, x0_px=base_wx, z0_px=base_wz, size=ext_size, mpp=cell_size,
            freq0=warp_freq, octaves=2)
        warp_x_noise /= fbm_amplitude(0.5, 2)

        warp_z_noise = fbm_grid(
            seed=seed ^ 0x87654321, x0_px=base_wx, z0_px=base_wz, size=ext_size, mpp=cell_size,
            freq0=warp_freq, octaves=2)
        warp_z_noise /= fbm_amplitude(0.5, 2)

        x_coords += warp_x_noise * warp_strength
        z_coords += warp_z_noise * warp_strength

    height_grid = np.zeros((ext_size, ext_size), dtype=np.float32)

    # --- ЭТАП 1: Генерация макрорельефа ---
    height_grid += _generate_base_layer(
        seed=seed, layer_cfg=spectral_cfg.get("continents", {}),
        coords_x=x_coords, coords_z=z_coords, cell_size=cell_size
    )

    # --- ЭТАП 2: Наложение среднего рельефа ---
    height_grid += _generate_additive_layer(
        seed=seed + 1, layer_cfg=spectral_cfg.get("hills", {}),
        coords_x=x_coords, coords_z=z_coords, cell_size=cell_size
    )

    # --- ЭТАП 3: Наложение микрорельефа ---
    height_grid += _generate_additive_layer(
        seed=seed + 2, layer_cfg=spectral_cfg.get("detail", {}),
        coords_x=x_coords, coords_z=z_coords, cell_size=cell_size
    )

    # --- ЭТАП 4: Финальная постобработка ---
    smoothing_passes = int(cfg.get("smoothing_passes", 0))
    if smoothing_passes > 0:
        sigma = 0.6 * smoothing_passes
        gaussian_filter(height_grid, sigma=sigma, output=scratch_buffers['b'], mode='reflect')
        height_grid = np.copy(scratch_buffers['b'])

    height_grid += float(cfg.get("base_height_m", 0.0))
    np.clip(height_grid, 0, float(cfg.get("max_height_m", 150.0)), out=height_grid)

    _print_range("height_final", height_grid)

    return height_grid.copy()