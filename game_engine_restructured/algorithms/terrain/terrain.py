# ==============================================================================
# Файл: game_engine_restructured/algorithms/terrain/terrain.py
# Назначение: Генерация геометрии ландшафта (карты высот).
# ВЕРСИЯ 23.0 (Стабильная): Возвращена поддержка shaping_power.
#              Код стабилизирован для работы с трехслойной системой.
# ==============================================================================

from __future__ import annotations
from typing import Any, Dict
import math
import numpy as np

from .slope import _apply_slope_limiter
from ...core.noise.fast_noise import fbm_amplitude, fbm_grid_warped


def _print_range(tag: str, arr: np.ndarray) -> None:
    mn, mx = float(np.min(arr)), float(np.max(arr))
    print(f"[DIAGNOSTIC] {tag}: min={mn:.3f} max={mx:.3f} range={mx - mn:.3f}")


def _generate_layer(
        seed: int, layer_cfg: Dict, base_coords_x: np.ndarray, base_coords_z: np.ndarray,
        cell_size: float
) -> np.ndarray:
    amp = float(layer_cfg.get("amp_m", 0.0))
    if amp <= 0:
        return np.zeros_like(base_coords_x)

    octaves = int(layer_cfg.get("octaves", 4))
    is_ridge = bool(layer_cfg.get("ridge", False))
    scale = float(layer_cfg.get("scale_tiles", 1000)) * cell_size
    freq = 1.0 / scale if scale > 0 else 0.0

    noise = fbm_grid_warped(seed=seed, coords_x=base_coords_x, coords_z=base_coords_z, freq0=freq, octaves=octaves,
                            ridge=is_ridge)

    norm_factor = max(fbm_amplitude(0.5, octaves), 1e-6)
    noise_normalized = noise / norm_factor

    # Базовый слой (is_base) всегда должен быть в диапазоне [0, 1] перед умножением на амплитуду
    if layer_cfg.get("is_base", False):
        if not is_ridge:
            noise_normalized = (noise_normalized + 1.0) * 0.5

    # --- ВОТ ОН: ПРИМЕНЕНИЕ SHAPING_POWER ---
    power = float(layer_cfg.get("shaping_power", 1.0))
    if power != 1.0:
        # Убеждаемся, что работаем с положительными значениями для возведения в степень
        np.power(np.maximum(0.0, noise_normalized), power, out=noise_normalized)

    # Для слоев, которые не являются базовыми, возвращаем диапазон [-amp, amp]
    if not layer_cfg.get("is_base", False) and not is_ridge:
        noise_normalized = (noise_normalized * 2.0) - 1.0

    return noise_normalized * amp


def generate_elevation_region(
        seed: int, scx: int, scz: int, region_size_chunks: int, chunk_size: int, preset: Any, scratch_buffers: dict,
) -> np.ndarray:
    cfg = getattr(preset, "elevation", {})
    spectral_cfg = cfg.get("spectral", {}) or {}
    ext_size = (region_size_chunks + 2) * chunk_size
    cell_size = float(getattr(preset, "cell_size", 1.0))
    base_wx = (scx * region_size_chunks - 1) * chunk_size
    base_wz = (scz * region_size_chunks - 1) * chunk_size
    z_coords_base, x_coords_base = np.mgrid[0:ext_size, 0:ext_size]
    x_coords_base = (x_coords_base.astype(np.float32) + base_wx) * cell_size
    z_coords_base = (z_coords_base.astype(np.float32) + base_wz) * cell_size
    height_grid = np.zeros((ext_size, ext_size), dtype=np.float32)

    # --- ЭТАП 1: Создание основного рельефа (3 слоя) ---
    if "continents" in spectral_cfg:
        height_grid += _generate_layer(seed, spectral_cfg["continents"], x_coords_base,
                                       z_coords_base, cell_size)

    if "large_features" in spectral_cfg:
        height_grid += _generate_layer(seed + 1, spectral_cfg["large_features"], x_coords_base, z_coords_base,
                                       cell_size)

    if "detail" in spectral_cfg:
        height_grid += _generate_layer(seed + 2, spectral_cfg["detail"], x_coords_base, z_coords_base,
                                       cell_size)

    # --- ЭТАП 2: Финальные шаги ---
    height_grid += float(cfg.get("base_height_m", 0.0))
    np.clip(height_grid, 0.0, float(cfg.get("max_height_m", 150.0)), out=height_grid)

    _print_range("height_final", height_grid)
    return height_grid.copy()

