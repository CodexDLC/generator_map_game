# ==============================================================================
# Файл: game_engine_restructured/algorithms/terrain/terrain.py
# Назначение: Генерация геометрии ландшафта (карты высот).
# ВЕРСИЯ 11.1: Исправлены опечатки и потенциальные проблемы, обнаруженные
#              статическим анализатором кода.
# ==============================================================================
from __future__ import annotations
from typing import Any, Dict
import numpy as np
import math
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

def _generate_layer(
        seed: int,
        layer_cfg: Dict,
        base_coords_x: np.ndarray,
        base_coords_z: np.ndarray,
        cell_size: float,
        scratch_buffer: np.ndarray
) -> np.ndarray:
    """
    Универсальная функция для генерации одного слоя рельефа.
    Поддерживает анизотропию, послойный warp и сглаживание.
    """
    amp = float(layer_cfg.get("amp_m", 0.0))
    if amp <= 0:
        return np.zeros_like(base_coords_x)

    # --- Шаг 1: Применяем послойный Domain Warp ---
    warp_cfg = layer_cfg.get("warp", {})
    warp_strength = float(warp_cfg.get("strength_m", 0.0))

    coords_x, coords_z = np.copy(base_coords_x), np.copy(base_coords_z)

    if warp_strength > 0:
        warp_scale = float(warp_cfg.get("scale_tiles", 1000)) * cell_size
        warp_freq = 1.0 / warp_scale if warp_scale > 0 else 0

        ext_size = base_coords_x.shape[0]
        # ИСПРАВЛЕНО: Убраны возможные опечатки. Эти строки вычисляют
        # стартовые пиксельные координаты региона для бесшовной генерации шума.
        base_wx = int(round(float(base_coords_x[0, 0]) / cell_size))
        base_wz = int(round(float(base_coords_z[0, 0]) / cell_size))

        warp_x_noise = fbm_grid(seed ^ 0x12345678, base_wx, base_wz, ext_size, cell_size, warp_freq, 2) / fbm_amplitude(
            0.5, 2)
        warp_z_noise = fbm_grid(seed ^ 0x87654321, base_wx, base_wz, ext_size, cell_size, warp_freq, 2) / fbm_amplitude(
            0.5, 2)

        coords_x += warp_x_noise * warp_strength
        coords_z += warp_z_noise * warp_strength

    # --- Шаг 2: Применяем анизотропное масштабирование ---
    orientation = math.radians(float(layer_cfg.get("orientation_deg", 0.0)))
    aspect = float(layer_cfg.get("aspect", 1.0))

    scale_parallel = float(layer_cfg.get("scale_tiles_parallel", layer_cfg.get("scale_tiles", 1000))) * cell_size
    scale_perp = scale_parallel / aspect if aspect > 0 else scale_parallel

    if orientation != 0 or aspect != 1.0:
        cr, sr = math.cos(orientation), math.sin(orientation)
        rotated_x = (coords_x * cr - coords_z * sr) / scale_parallel
        rotated_z = (coords_x * sr + coords_z * cr) / scale_perp
        final_coords_x, final_coords_z = rotated_x, rotated_z
        freq0 = 1.0
    else:
        final_coords_x, final_coords_z = coords_x, coords_z
        freq0 = 1.0 / scale_parallel

    # --- Шаг 3: Генерируем шум на подготовленных координатах ---
    octaves = int(layer_cfg.get("octaves", 3))
    noise = fbm_grid_warped(
        seed=seed, coords_x=final_coords_x, coords_z=final_coords_z,
        freq0=freq0,
        octaves=octaves,
        ridge=bool(layer_cfg.get("ridge", False))
    )

    # Нормализуем результат в зависимости от типа шума
    is_base_layer = layer_cfg.get("is_base", False)
    if is_base_layer:
        min_val, max_val = np.min(noise), np.max(noise)
        if (max_val - min_val) > 1e-6:
            noise = (noise - min_val) / (max_val - min_val)
    else:
        norm_factor = fbm_amplitude(0.5, octaves)
        if norm_factor > 1e-6:
            noise /= norm_factor

    # --- Шаг 4: Применяем сглаживание и степенную кривую ---
    smoothing_sigma_pre_shape = float(layer_cfg.get("smoothing_sigma_pre_shape", 0.0))
    if smoothing_sigma_pre_shape > 0:
        gaussian_filter(noise, sigma=smoothing_sigma_pre_shape, output=scratch_buffer, mode='reflect')
        noise = np.copy(scratch_buffer)

    shaping_power = float(layer_cfg.get("shaping_power", 1.0))
    if shaping_power != 1.0:
        if is_base_layer:
            _apply_shaping_curve(noise, shaping_power)
        else:
            signs = np.sign(noise)
            shaped_noise = np.power(np.abs(noise), shaping_power)
            noise = shaped_noise * signs

    smoothing_sigma_post_shape = float(layer_cfg.get("smoothing_sigma_post_shape", 0.0))
    if smoothing_sigma_post_shape > 0:
        gaussian_filter(noise, sigma=smoothing_sigma_post_shape, output=scratch_buffer, mode='reflect')
        noise = np.copy(scratch_buffer)

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

    # Создаем базовую сетку мировых координат
    z_coords_base, x_coords_base = np.mgrid[0:ext_size, 0:ext_size]
    x_coords_base = (x_coords_base.astype(np.float32) + base_wx) * cell_size
    z_coords_base = (z_coords_base.astype(np.float32) + base_wz) * cell_size

    height_grid = np.zeros((ext_size, ext_size), dtype=np.float32)

    layers_to_generate = [
        ("continents", True),
        ("large_features", False),
        ("erosion", False),
        ("ground_details", False)
    ]

    for i, (layer_name, is_base) in enumerate(layers_to_generate):
        if layer_name in spectral_cfg:
            layer_cfg = dict(spectral_cfg[layer_name])
            layer_cfg["is_base"] = is_base

            print(f"  -> Generating layer: {layer_name}...")
            height_grid += _generate_layer(
                seed=seed + i,
                layer_cfg=layer_cfg,
                base_coords_x=x_coords_base,
                base_coords_z=z_coords_base,
                cell_size=cell_size,
                scratch_buffer=scratch_buffers['a']
            )

    # --- ЭТАП 5: Финальная постобработка (опционально) ---
    smoothing_passes = int(cfg.get("smoothing_passes", 0))
    if smoothing_passes > 0:
        sigma = 0.6 * smoothing_passes
        gaussian_filter(height_grid, sigma=sigma, output=scratch_buffers['b'], mode='reflect')
        height_grid = np.copy(scratch_buffers['b'])

    height_grid += float(cfg.get("base_height_m", 0.0))
    np.clip(height_grid, 0, float(cfg.get("max_height_m", 150.0)), out=height_grid)

    _print_range("height_final", height_grid)

    return height_grid.copy()